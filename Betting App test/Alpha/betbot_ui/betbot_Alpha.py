from flask import Flask, render_template, request, jsonify, Response
import requests
import ollama
import json
import time
import threading

app = Flask(__name__)

API_KEY  = "1682af281eb149eca5f0b502c32612b5"
MODEL    = "llama3.2"
BASE_URL = "https://api.football-data.org/v4"
HEADERS  = {"X-Auth-Token": API_KEY}

LIGAS = {
    "CL":  "Champions League",
    "PL":  "Premier League",
    "PD":  "La Liga",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "FL1": "Ligue 1",
    "CLI": "Copa Libertadores",
    "EC":  "Eurocopa",
}

EQUIPO_LIGA = {}

# ─── API ──────────────────────────────────────────────────────────────────────

def api_get(path, params={}):
    try:
        time.sleep(5)
        r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=12)
        if r.status_code == 429:
            time.sleep(65)
            r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=12)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

def res_icono(winner, team_id, home_id, away_id):
    if winner == "DRAW": return "E"
    if (winner == "HOME_TEAM" and team_id == home_id) or \
       (winner == "AWAY_TEAM" and team_id == away_id): return "V"
    return "D"

def buscar_equipo(nombre):
    nombre_lower = nombre.lower()
    encontrados  = []
    for codigo in LIGAS:
        data = api_get(f"competitions/{codigo}/teams")
        if not data: continue
        for t in data.get("teams", []):
            campos = [(t.get("name") or "").lower(),
                      (t.get("shortName") or "").lower(),
                      (t.get("tla") or "").lower()]
            if any(nombre_lower in c for c in campos):
                t["_liga_codigo"] = codigo
                encontrados.append(t)
    vistos, unicos = set(), []
    for e in encontrados:
        if e["id"] not in vistos:
            vistos.add(e["id"])
            unicos.append(e)
    if not unicos: return None
    equipo = unicos[0]
    EQUIPO_LIGA[equipo["id"]] = equipo.get("_liga_codigo", "")
    return equipo

def posicion_en_tabla(team_id):
    liga = EQUIPO_LIGA.get(team_id)
    if not liga: return None
    data = api_get(f"competitions/{liga}/standings")
    if not data: return None
    for tabla in data.get("standings", []):
        if tabla.get("type") != "TOTAL": continue
        for row in tabla.get("table", []):
            if row.get("team", {}).get("id") == team_id:
                return {
                    "posicion": row.get("position", "?"),
                    "puntos":   row.get("points", 0),
                    "pj":       row.get("playedGames", 0),
                    "dg":       row.get("goalDifference", 0),
                    "liga":     LIGAS.get(liga, liga),
                }
    return None

def goleadores_equipo(team_id, top=3):
    liga = EQUIPO_LIGA.get(team_id)
    if not liga: return []
    data = api_get(f"competitions/{liga}/scorers", {"limit": 20})
    if not data: return []
    result = []
    for s in data.get("scorers", []):
        if s.get("team", {}).get("id") == team_id:
            result.append({"nombre": s.get("player", {}).get("name", "?"),
                           "goles": s.get("goals", 0)})
        if len(result) >= top: break
    return result

def ultimos_partidos(team_id, limit=8):
    data = api_get(f"teams/{team_id}/matches", {"status": "FINISHED", "limit": limit})
    if not data: return []
    partidos = []
    for m in data.get("matches", [])[-limit:]:
        home     = m["homeTeam"]
        away     = m["awayTeam"]
        ft       = m.get("score", {}).get("fullTime", {})
        gl       = ft.get("home") or 0
        gv       = ft.get("away") or 0
        es_local = home["id"] == team_id
        gf       = gl if es_local else gv
        gc       = gv if es_local else gl
        winner   = m.get("score", {}).get("winner", "DRAW")
        partidos.append({
            "fecha":        m["utcDate"][:10],
            "rival":        away["name"] if es_local else home["name"],
            "condicion":    "LOCAL" if es_local else "VISITA",
            "gf": gf, "gc": gc,
            "resultado":    res_icono(winner, team_id, home["id"], away["id"]),
            "competicion":  m.get("competition", {}).get("name", "?"),
            "ambos_anotan": gf > 0 and gc > 0,
            "total_goles":  gf + gc,
        })
    return list(reversed(partidos))

def calcular_stats(partidos):
    n       = len(partidos) or 1
    locales = [p for p in partidos if p["condicion"] == "LOCAL"]
    visitas = [p for p in partidos if p["condicion"] == "VISITA"]
    def pg(l): return round(sum(p["gf"] for p in l) / len(l), 2) if l else 0.0
    def pc(l): return round(sum(p["gc"] for p in l) / len(l), 2) if l else 0.0
    forma = ""
    for p in partidos:
        if p["resultado"]=="V": forma+="W"
        elif p["resultado"]=="E": forma+="D"
        else: forma+="L"
    ambos = sum(1 for p in partidos if p["ambos_anotan"])
    mas25 = sum(1 for p in partidos if p["total_goles"] > 2)
    tg    = sum(p["total_goles"] for p in partidos)
    racha = 0
    ur    = partidos[0]["resultado"] if partidos else ""
    for p in partidos:
        if p["resultado"] == ur: racha += 1
        else: break
    return {
        "goles_favor":          round(sum(p["gf"] for p in partidos)/n, 2),
        "goles_contra":         round(sum(p["gc"] for p in partidos)/n, 2),
        "victorias":            forma.count("W"),
        "empates":              forma.count("D"),
        "derrotas":             forma.count("L"),
        "forma":                forma,
        "gf_local":             pg(locales), "gc_local": pc(locales),
        "gf_visita":            pg(visitas), "gc_visita": pc(visitas),
        "partidos_local":       len(locales),
        "partidos_visita":      len(visitas),
        "pct_ambos_anotan":     round(ambos/n*100),
        "pct_mas_2_5":          round(mas25/n*100),
        "promedio_total_goles": round(tg/n, 2),
        "racha_actual":         racha,
        "ultimo_resultado":     ur,
    }

def head_to_head(id1, id2):
    data = api_get("matches", {"competitions": ",".join(LIGAS.keys())})
    if not data: return []
    h2h = []
    for m in data.get("matches", []):
        hid = m["homeTeam"]["id"]
        aid = m["awayTeam"]["id"]
        if {hid, aid} == {id1, id2} and m["status"] == "FINISHED":
            ft     = m.get("score", {}).get("fullTime", {})
            gl     = ft.get("home") or 0
            gv     = ft.get("away") or 0
            winner = m.get("score", {}).get("winner", "DRAW")
            gan    = m["homeTeam"]["name"] if winner=="HOME_TEAM" else \
                     m["awayTeam"]["name"] if winner=="AWAY_TEAM" else "Empate"
            h2h.append({"fecha": m["utcDate"][:10],
                         "local": m["homeTeam"]["name"],
                         "visita": m["awayTeam"]["name"],
                         "gl": gl, "gv": gv, "ganador": gan, "total": gl+gv})
    return h2h[:6]

def partido_en_vivo(id1, id2):
    data = api_get("matches", {"status": "IN_PLAY,PAUSED,EXTRA_TIME,PENALTY_SHOOTOUT"})
    if not data: return None
    for m in data.get("matches", []):
        if {m["homeTeam"]["id"], m["awayTeam"]["id"]} == {id1, id2}:
            return m
    return None

def proximos_partidos(id1, id2):
    data = api_get("matches", {"status": "SCHEDULED,TIMED"})
    if not data: return []
    out = []
    for m in data.get("matches", []):
        if {m["homeTeam"]["id"], m["awayTeam"]["id"]} == {id1, id2}:
            out.append({"fecha": m["utcDate"][:10],
                        "hora":  m["utcDate"][11:16]+" UTC",
                        "comp":  m.get("competition",{}).get("name","?"),
                        "local": m["homeTeam"]["name"],
                        "visita":m["awayTeam"]["name"]})
    return out

def predecir_con_ollama(nl, sl, tl, gl, nv, sv, tv, gv_data, h2h, vivo):
    def ts(t):
        if not t: return "No disponible"
        return f"Pos #{t['posicion']} en {t['liga']} | {t['puntos']} pts | GD: {t['dg']:+d}"
    def gs(g):
        if not g: return "No disponible"
        return ", ".join(f"{x['nombre']} ({x['goles']}g)" for x in g)
    h2h_t = ""
    if h2h:
        for p in h2h:
            h2h_t += f"  {p['fecha']}: {p['local']} {p['gl']}-{p['gv']} {p['visita']} -> {p['ganador']}\n"
        gg = [p["total"] for p in h2h]
        h2h_t += f"  Prom goles H2H: {round(sum(gg)/len(gg),2)}\n"
    else:
        h2h_t = "  Sin datos"
    vivo_t = ""
    if vivo:
        ft = vivo.get("score",{}).get("fullTime",{})
        vivo_t = f"\nPARTIDO EN VIVO: {nl} {ft.get('home',0)} - {ft.get('away',0)} {nv}\n"

    prompt = f"""
Eres un analista deportivo experto en apuestas de futbol.{vivo_t}

EQUIPO LOCAL: {nl}
Tabla: {ts(tl)} | Goleadores: {gs(gl)}
Forma: {sl['forma']} ({sl['victorias']}V/{sl['empates']}E/{sl['derrotas']}D)
Como LOCAL: GF {sl['gf_local']} GC {sl['gc_local']} ({sl['partidos_local']} partidos)
Como VISITA: GF {sl['gf_visita']} GC {sl['gc_visita']} ({sl['partidos_visita']} partidos)
Ambos anotan: {sl['pct_ambos_anotan']}% | +2.5 goles: {sl['pct_mas_2_5']}% | Prom goles/p: {sl['promedio_total_goles']}

EQUIPO VISITANTE: {nv}
Tabla: {ts(tv)} | Goleadores: {gs(gv_data)}
Forma: {sv['forma']} ({sv['victorias']}V/{sv['empates']}E/{sv['derrotas']}D)
Como LOCAL: GF {sv['gf_local']} GC {sv['gc_local']} ({sv['partidos_local']} partidos)
Como VISITA: GF {sv['gf_visita']} GC {sv['gc_visita']} ({sv['partidos_visita']} partidos)
Ambos anotan: {sv['pct_ambos_anotan']}% | +2.5 goles: {sv['pct_mas_2_5']}% | Prom goles/p: {sv['promedio_total_goles']}

HISTORIAL DIRECTO:
{h2h_t}

Las 3 probabilidades DEBEN sumar exactamente 100. Responde SOLO JSON puro:
{{
  "prob_local": <0-100>,
  "prob_empate": <0-100>,
  "prob_visitante": <0-100>,
  "ganador": "<{nl} o {nv} o Empate>",
  "confianza": "<baja|media|alta>",
  "nivel_riesgo": "<bajo|medio|alto>",
  "goles_esperados_local": <entero>,
  "goles_esperados_visitante": <entero>,
  "apuesta_1x2": "<descripcion>",
  "apuesta_ambos_anotan": "<Si|No>",
  "apuesta_total_goles": "<Mas de 2.5|Menos de 2.5|Mas de 1.5>",
  "apuesta_segura": "<descripcion de la apuesta mas segura>",
  "razon_apuesta_segura": "<1-2 oraciones>",
  "analisis": "<5-7 oraciones de analisis>"
}}
"""
    resp = ollama.chat(model=MODEL, format="json",
                       messages=[{"role":"user","content":prompt}])
    raw  = resp["message"]["content"].strip()
    raw  = raw.replace("```json","").replace("```","").strip()
    s    = raw.find("{"); e = raw.rfind("}")+1
    if s != -1 and e > s: raw = raw[s:e]
    return json.loads(raw)

# ─── RUTAS FLASK ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", ligas=LIGAS)

@app.route("/analizar", methods=["POST"])
def analizar():
    def generate():
        def emit(tipo, data):
            yield f"data: {json.dumps({'type': tipo, 'data': data})}\n\n"

        data_req   = request.get_json()
        nombre_l   = data_req.get("local", "").strip()
        nombre_v   = data_req.get("visita", "").strip()

        try:
            yield from emit("status", f"Buscando {nombre_l}...")
            eq_local = buscar_equipo(nombre_l)
            if not eq_local:
                yield from emit("error", f"No se encontró '{nombre_l}'")
                return
            yield from emit("status", f"Encontrado: {eq_local['name']}")

            yield from emit("status", f"Buscando {nombre_v}...")
            eq_visita = buscar_equipo(nombre_v)
            if not eq_visita:
                yield from emit("error", f"No se encontró '{nombre_v}'")
                return
            yield from emit("status", f"Encontrado: {eq_visita['name']}")

            id_l = eq_local["id"]
            id_v = eq_visita["id"]

            yield from emit("status", "Verificando partido en vivo...")
            vivo = partido_en_vivo(id_l, id_v)

            yield from emit("status", "Buscando próximos partidos...")
            proximos = proximos_partidos(id_l, id_v)

            yield from emit("status", f"Obteniendo partidos de {eq_local['name']}...")
            p_local = ultimos_partidos(id_l, 8)

            yield from emit("status", f"Obteniendo partidos de {eq_visita['name']}...")
            p_visita = ultimos_partidos(id_v, 8)

            if not p_local or not p_visita:
                yield from emit("error", "No se pudieron obtener los partidos")
                return

            sl = calcular_stats(p_local)
            sv = calcular_stats(p_visita)

            yield from emit("status", "Obteniendo posiciones en tabla...")
            tl = posicion_en_tabla(id_l)
            tv = posicion_en_tabla(id_v)

            yield from emit("status", "Obteniendo goleadores...")
            gl = goleadores_equipo(id_l)
            gv_data = goleadores_equipo(id_v)

            yield from emit("status", "Buscando historial directo...")
            h2h = head_to_head(id_l, id_v)

            yield from emit("teams", {
                "local":  {"nombre": eq_local["name"],  "stats": sl, "tabla": tl, "goleadores": gl,  "partidos": p_local},
                "visita": {"nombre": eq_visita["name"], "stats": sv, "tabla": tv, "goleadores": gv_data, "partidos": p_visita},
                "h2h":    h2h,
                "vivo":   vivo,
                "proximos": proximos,
            })

            yield from emit("status", "Analizando con IA (llama3.2)... esto puede tardar un momento")
            resultado = predecir_con_ollama(
                eq_local["name"],  sl, tl, gl,
                eq_visita["name"], sv, tv, gv_data,
                h2h, vivo
            )
            yield from emit("prediccion", resultado)
            yield from emit("done", "ok")

        except Exception as e:
            yield from emit("error", str(e))

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
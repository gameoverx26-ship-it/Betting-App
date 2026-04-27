import requests
import ollama
import json
import sys
import time

API_KEY = "1682af281eb149eca5f0b502c32612b5"
MODEL   = "llama3.2"

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

# Mapa equipo_id -> codigo de liga (se llena al buscar)
EQUIPO_LIGA = {}


def sep(char="─", n=72):
    print(char * n)

def barra(pct, ancho=30):
    lleno = round(pct / 100 * ancho)
    return "█" * lleno + "░" * (ancho - lleno)

def res_icono(winner, team_id, home_id, away_id):
    if winner == "DRAW":
        return "E"
    if (winner == "HOME_TEAM" and team_id == home_id) or \
       (winner == "AWAY_TEAM" and team_id == away_id):
        return "V"
    return "D"


def api_get(path, params={}):
    try:
        time.sleep(6)
        r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=12)
        if r.status_code == 429:
            print("  [!] Limite de requests. Esperando 65 seg...")
            time.sleep(65)
            r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=12)
        if r.status_code == 403:
            print("  [!] Sin permisos para este endpoint.")
            return None
        if r.status_code != 200:
            print(f"  [!] Error HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        print(f"  [!] Error de conexion: {e}")
        return None


# ─── BUSCAR EQUIPO ────────────────────────────────────────────────────────────

def buscar_equipo(nombre):
    nombre_lower = nombre.lower()
    encontrados  = []

    for codigo in LIGAS:
        data = api_get(f"competitions/{codigo}/teams")
        if not data:
            continue
        for t in data.get("teams", []):
            campos = [
                (t.get("name")      or "").lower(),
                (t.get("shortName") or "").lower(),
                (t.get("tla")       or "").lower(),
            ]
            if any(nombre_lower in c for c in campos):
                t["_liga_codigo"] = codigo
                encontrados.append(t)

    if not encontrados:
        return None

    vistos, unicos = set(), []
    for e in encontrados:
        if e["id"] not in vistos:
            vistos.add(e["id"])
            unicos.append(e)

    if len(unicos) == 1:
        EQUIPO_LIGA[unicos[0]["id"]] = unicos[0].get("_liga_codigo", "")
        return unicos[0]

    print(f"\n  Se encontraron {len(unicos)} equipos para '{nombre}':")
    for i, t in enumerate(unicos[:6], 1):
        print(f"    {i}. {t['name']} ({t.get('area', {}).get('name', '?')})")
    try:
        sel = int(input("  Selecciona el numero: ").strip()) - 1
        equipo = unicos[sel]
    except Exception:
        equipo = unicos[0]
    EQUIPO_LIGA[equipo["id"]] = equipo.get("_liga_codigo", "")
    return equipo


# ─── POSICION EN TABLA ────────────────────────────────────────────────────────

def posicion_en_tabla(team_id):
    liga = EQUIPO_LIGA.get(team_id)
    if not liga:
        return None
    data = api_get(f"competitions/{liga}/standings")
    if not data:
        return None
    for tabla in data.get("standings", []):
        if tabla.get("type") != "TOTAL":
            continue
        for row in tabla.get("table", []):
            if row.get("team", {}).get("id") == team_id:
                return {
                    "posicion":  row.get("position", "?"),
                    "puntos":    row.get("points", 0),
                    "pj":        row.get("playedGames", 0),
                    "victorias": row.get("won", 0),
                    "empates":   row.get("draw", 0),
                    "derrotas":  row.get("lost", 0),
                    "gf":        row.get("goalsFor", 0),
                    "gc":        row.get("goalsAgainst", 0),
                    "dg":        row.get("goalDifference", 0),
                    "liga":      LIGAS.get(liga, liga),
                }
    return None


# ─── GOLEADORES ───────────────────────────────────────────────────────────────

def goleadores_equipo(team_id, top=3):
    liga = EQUIPO_LIGA.get(team_id)
    if not liga:
        return []
    data = api_get(f"competitions/{liga}/scorers", {"limit": 20})
    if not data:
        return []
    result = []
    for s in data.get("scorers", []):
        if s.get("team", {}).get("id") == team_id:
            result.append({
                "nombre": s.get("player", {}).get("name", "?"),
                "goles":  s.get("goals", 0),
            })
        if len(result) >= top:
            break
    return result


# ─── ULTIMOS PARTIDOS ─────────────────────────────────────────────────────────

def ultimos_partidos(team_id, limit=8):
    data = api_get(f"teams/{team_id}/matches", {
        "status": "FINISHED",
        "limit":  limit,
    })
    if not data:
        return []

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
        rival    = away["name"] if es_local else home["name"]
        winner   = m.get("score", {}).get("winner", "DRAW")
        ambos    = gf > 0 and gc > 0

        partidos.append({
            "fecha":        m["utcDate"][:10],
            "rival":        rival,
            "condicion":    "LOCAL" if es_local else "VISITA",
            "gf":           gf,
            "gc":           gc,
            "resultado":    res_icono(winner, team_id, home["id"], away["id"]),
            "competicion":  m.get("competition", {}).get("name", "?"),
            "home_id":      home["id"],
            "away_id":      away["id"],
            "winner":       winner,
            "team_id":      team_id,
            "ambos_anotan": ambos,
            "total_goles":  gf + gc,
        })

    return list(reversed(partidos))


# ─── CALCULAR ESTADISTICAS ────────────────────────────────────────────────────

def calcular_stats(partidos):
    n = len(partidos) or 1

    locales = [p for p in partidos if p["condicion"] == "LOCAL"]
    visitas = [p for p in partidos if p["condicion"] == "VISITA"]

    def prom_gf(lista): return round(sum(p["gf"] for p in lista) / len(lista), 2) if lista else 0.0
    def prom_gc(lista): return round(sum(p["gc"] for p in lista) / len(lista), 2) if lista else 0.0

    forma = ""
    for p in partidos:
        if   p["resultado"] == "V": forma += "W"
        elif p["resultado"] == "E": forma += "D"
        else:                       forma += "L"

    ambos_anotan = sum(1 for p in partidos if p["ambos_anotan"])
    mas_2_5      = sum(1 for p in partidos if p["total_goles"] > 2)
    total_goles  = sum(p["total_goles"] for p in partidos)

    racha       = 0
    ultimo_res  = partidos[0]["resultado"] if partidos else ""
    for p in partidos:
        if p["resultado"] == ultimo_res: racha += 1
        else: break

    return {
        "goles_favor":          round(sum(p["gf"] for p in partidos) / n, 2),
        "goles_contra":         round(sum(p["gc"] for p in partidos) / n, 2),
        "victorias":            forma.count("W"),
        "empates":              forma.count("D"),
        "derrotas":             forma.count("L"),
        "forma":                forma,
        "gf_local":             prom_gf(locales),
        "gc_local":             prom_gc(locales),
        "gf_visita":            prom_gf(visitas),
        "gc_visita":            prom_gc(visitas),
        "partidos_local":       len(locales),
        "partidos_visita":      len(visitas),
        "pct_ambos_anotan":     round(ambos_anotan / n * 100),
        "pct_mas_2_5":          round(mas_2_5 / n * 100),
        "promedio_total_goles": round(total_goles / n, 2),
        "racha_actual":         racha,
        "ultimo_resultado":     ultimo_res,
    }


# ─── HEAD TO HEAD ─────────────────────────────────────────────────────────────

def head_to_head(id1, id2):
    data = api_get("matches", {"competitions": ",".join(LIGAS.keys())})
    if not data:
        return []
    h2h = []
    for m in data.get("matches", []):
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]
        if {home_id, away_id} == {id1, id2} and m["status"] == "FINISHED":
            ft     = m.get("score", {}).get("fullTime", {})
            gl     = ft.get("home") or 0
            gv     = ft.get("away") or 0
            winner = m.get("score", {}).get("winner", "DRAW")
            gan    = m["homeTeam"]["name"] if winner == "HOME_TEAM" else \
                     m["awayTeam"]["name"] if winner == "AWAY_TEAM" else "Empate"
            h2h.append({
                "fecha":   m["utcDate"][:10],
                "local":   m["homeTeam"]["name"],
                "visita":  m["awayTeam"]["name"],
                "gl": gl, "gv": gv,
                "ganador": gan,
                "total":   gl + gv,
            })
    return h2h[:6]


# ─── VIVO Y PROXIMOS ─────────────────────────────────────────────────────────

def partido_en_vivo(id1, id2):
    data = api_get("matches", {"status": "IN_PLAY,PAUSED,EXTRA_TIME,PENALTY_SHOOTOUT"})
    if not data:
        return None
    for m in data.get("matches", []):
        if {m["homeTeam"]["id"], m["awayTeam"]["id"]} == {id1, id2}:
            return m
    return None


def proximos_partidos(id1, id2):
    data = api_get("matches", {"status": "SCHEDULED,TIMED"})
    if not data:
        return []
    proximos = []
    for m in data.get("matches", []):
        if {m["homeTeam"]["id"], m["awayTeam"]["id"]} == {id1, id2}:
            proximos.append({
                "fecha":  m["utcDate"][:10],
                "hora":   m["utcDate"][11:16] + " UTC",
                "comp":   m.get("competition", {}).get("name", "?"),
                "stage":  m.get("stage", ""),
                "local":  m["homeTeam"]["name"],
                "visita": m["awayTeam"]["name"],
            })
    return proximos


# ─── MOSTRAR ─────────────────────────────────────────────────────────────────

def mostrar_tabla(nombre, partidos, stats, tabla, goleadores):
    print(f"\n{'='*72}")
    print(f"  {nombre.upper()}")
    print(f"{'='*72}")

    if tabla:
        print(f"\n  Tabla  : #{tabla['posicion']} en {tabla['liga']}  |  "
              f"{tabla['puntos']} pts  |  PJ {tabla['pj']}  |  GD {tabla['dg']:+d}")

    if goleadores:
        gstr = "  |  ".join(f"{g['nombre']} ({g['goles']}g)" for g in goleadores)
        print(f"  Goles  : {gstr}")

    print(f"\n  Como LOCAL   -> GF: {stats['gf_local']:.2f}  GC: {stats['gc_local']:.2f}"
          f"  ({stats['partidos_local']} partidos)")
    print(f"  Como VISITA  -> GF: {stats['gf_visita']:.2f}  GC: {stats['gc_visita']:.2f}"
          f"  ({stats['partidos_visita']} partidos)")
    print(f"\n  Ambos anotan : {stats['pct_ambos_anotan']}% de partidos  |  "
          f"+2.5 goles: {stats['pct_mas_2_5']}%  |  "
          f"Prom total: {stats['promedio_total_goles']} goles/partido")

    if stats['racha_actual'] >= 2:
        iconos = {"V": "[WIN]", "E": "[EMP]", "D": "[DER]"}
        print(f"  Racha  : {stats['racha_actual']} {iconos.get(stats['ultimo_resultado'],'')} consecutivos")

    print(f"\n  {'FECHA':<12} {'RIVAL':<22} {'COND':<7} {'RES':<4} {'GF':>3} {'GC':>3}  COMPETICION")
    sep()
    for p in partidos:
        res_sym = "V" if p["resultado"]=="V" else "E" if p["resultado"]=="E" else "D"
        print(
            f"  {p['fecha']:<12} {p['rival'][:20]:<22} {p['condicion']:<7} "
            f"{res_sym:<4} {p['gf']:>3} {p['gc']:>3}  {p['competicion'][:22]}"
        )
    sep()
    print(f"  {'PROMEDIO':.<46} {stats['goles_favor']:>4} {stats['goles_contra']:>4}")
    print(f"  Forma  : {' - '.join(list(stats['forma']))}   "
          f"{stats['victorias']}V / {stats['empates']}E / {stats['derrotas']}D")


def mostrar_h2h(h2h):
    if not h2h:
        print("\n  Sin historial directo reciente.\n")
        return
    print(f"\n  HISTORIAL DIRECTO (ultimos {len(h2h)} partidos)")
    sep()
    goles_h2h = [p["total"] for p in h2h]
    prom = round(sum(goles_h2h) / len(goles_h2h), 2) if goles_h2h else 0
    for p in h2h:
        print(f"  {p['fecha']}   {p['local'][:18]:>18} {p['gl']} - {p['gv']} "
              f"{p['visita'][:18]:<18}   {p['ganador']}")
    sep()
    print(f"  Promedio de goles en H2H: {prom} por partido")


def mostrar_en_vivo(m):
    ft   = m.get("score", {}).get("fullTime", {})
    comp = m.get("competition", {}).get("name", "?")
    print(f"\n  [EN VIVO] {comp}")
    print(f"  {m['homeTeam']['name']} {ft.get('home',0)} - {ft.get('away',0)} {m['awayTeam']['name']}")
    sep()


def mostrar_proximo(proximos):
    if not proximos:
        return
    p = proximos[0]
    print(f"\n  Proximo: {p['fecha']} {p['hora']} | {p['comp']}")
    print(f"  {p['local']} vs {p['visita']}")
    sep()


def mostrar_prediccion(resultado, nombre_local, nombre_visita):
    pl  = resultado.get("prob_local", 0)
    pe  = resultado.get("prob_empate", 0)
    pv  = resultado.get("prob_visitante", 0)
    gan = resultado.get("ganador", "?")
    con = resultado.get("confianza", "media").upper()
    gl  = resultado.get("goles_esperados_local", "?")
    gv  = resultado.get("goles_esperados_visitante", "?")

    apuesta_1x2    = resultado.get("apuesta_1x2", "?")
    apuesta_ambos  = resultado.get("apuesta_ambos_anotan", "?")
    apuesta_goles  = resultado.get("apuesta_total_goles", "?")
    apuesta_segura = resultado.get("apuesta_segura", "?")
    razon_segura   = resultado.get("razon_apuesta_segura", "")
    nivel_riesgo   = resultado.get("nivel_riesgo", "medio").upper()

    print(f"\n\n{'='*72}")
    print(f"  PREDICCION  --  {nombre_local.upper()} vs {nombre_visita.upper()}")
    print(f"{'='*72}")
    print(f"\n  Resultado probable : {gan.upper()}")
    print(f"  Marcador esperado  : {nombre_local} {gl} - {gv} {nombre_visita}")
    print(f"  Confianza: {con}   |   Riesgo: {nivel_riesgo}\n")

    label_l = f"  Victoria {nombre_local[:18]}"
    label_e = "  Empate"
    label_v = f"  Victoria {nombre_visita[:18]}"
    ancho   = max(len(label_l), len(label_e), len(label_v)) + 1

    print(f"{label_l:<{ancho}}  {pl:>5.1f}%  {barra(pl)}")
    print(f"{label_e:<{ancho}}  {pe:>5.1f}%  {barra(pe)}")
    print(f"{label_v:<{ancho}}  {pv:>5.1f}%  {barra(pv)}")

    print(f"\n{'─'*72}")
    print(f"  APUESTAS RECOMENDADAS")
    print(f"{'─'*72}")
    print(f"  1X2 (resultado)    : {apuesta_1x2}")
    print(f"  Ambos anotan       : {apuesta_ambos}")
    print(f"  Total goles        : {apuesta_goles}")
    print(f"\n  *** APUESTA MAS SEGURA : {apuesta_segura}")
    if razon_segura:
        print(f"      Razon            : {razon_segura}")

    print(f"\n{'─'*72}")
    print(f"  ANALISIS ({MODEL}):\n")
    for oracion in resultado.get("analisis", "Sin analisis.").replace("\n", " ").split(". "):
        oracion = oracion.strip()
        if oracion:
            print(f"    * {oracion}{'.' if not oracion.endswith('.') else ''}")

    print(f"\n{'='*72}")
    print("  ADVERTENCIA: Solo referencia. Apuesta con responsabilidad.")
    print(f"{'='*72}\n")


# ─── OLLAMA ───────────────────────────────────────────────────────────────────

def predecir_con_ollama(
    nombre_local,  stats_local,  tabla_local,  goles_local,
    nombre_visita, stats_visita, tabla_visita, goles_visita,
    h2h, partido_vivo
):
    contexto_vivo = ""
    if partido_vivo:
        ft = partido_vivo.get("score", {}).get("fullTime", {})
        contexto_vivo = (
            f"\nPARTIDO EN VIVO AHORA: "
            f"{nombre_local} {ft.get('home',0)} - {ft.get('away',0)} {nombre_visita}\n"
        )

    h2h_texto = ""
    if h2h:
        for p in h2h:
            h2h_texto += f"  {p['fecha']}: {p['local']} {p['gl']}-{p['gv']} {p['visita']} -> {p['ganador']}\n"
        goles_h2h = [p["total"] for p in h2h]
        h2h_texto += f"  Promedio goles H2H: {round(sum(goles_h2h)/len(goles_h2h),2)}\n"
    else:
        h2h_texto = "  Sin datos disponibles"

    def tabla_str(t):
        if not t:
            return "No disponible"
        return f"Pos #{t['posicion']} en {t['liga']} | {t['puntos']} pts | GD: {t['dg']:+d}"

    def goleadores_str(g):
        if not g:
            return "No disponible"
        return ", ".join(f"{x['nombre']} ({x['goles']} goles)" for x in g)

    prompt = f"""
Eres un analista deportivo experto en apuestas de futbol. Analiza con precision los datos estadisticos.
{contexto_vivo}

EQUIPO LOCAL: {nombre_local}
Posicion en tabla : {tabla_str(tabla_local)}
Goleadores        : {goleadores_str(goles_local)}
Forma reciente    : {stats_local['forma']} ({stats_local['victorias']}V/{stats_local['empates']}E/{stats_local['derrotas']}D)
Como LOCAL        : GF {stats_local['gf_local']} / GC {stats_local['gc_local']} prom ({stats_local['partidos_local']} partidos)
Como VISITA       : GF {stats_local['gf_visita']} / GC {stats_local['gc_visita']} prom ({stats_local['partidos_visita']} partidos)
Ambos anotan      : {stats_local['pct_ambos_anotan']}% de sus partidos
Mas de 2.5 goles  : {stats_local['pct_mas_2_5']}% de sus partidos
Prom goles/p      : {stats_local['promedio_total_goles']}

EQUIPO VISITANTE: {nombre_visita}
Posicion en tabla : {tabla_str(tabla_visita)}
Goleadores        : {goleadores_str(goles_visita)}
Forma reciente    : {stats_visita['forma']} ({stats_visita['victorias']}V/{stats_visita['empates']}E/{stats_visita['derrotas']}D)
Como LOCAL        : GF {stats_visita['gf_local']} / GC {stats_visita['gc_local']} prom ({stats_visita['partidos_local']} partidos)
Como VISITA       : GF {stats_visita['gf_visita']} / GC {stats_visita['gc_visita']} prom ({stats_visita['partidos_visita']} partidos)
Ambos anotan      : {stats_visita['pct_ambos_anotan']}% de sus partidos
Mas de 2.5 goles  : {stats_visita['pct_mas_2_5']}% de sus partidos
Prom goles/p      : {stats_visita['promedio_total_goles']}

HISTORIAL DIRECTO:
{h2h_texto}

INSTRUCCIONES:
- Analiza el rendimiento del equipo LOCAL jugando en casa, y del VISITANTE jugando fuera.
- Considera las posiciones en la tabla para la diferencia de nivel.
- Evalua si estadisticamente ambos equipos tienden a anotar.
- La apuesta segura debe ser la que tenga mayor respaldo estadistico, no la mas obvia.
- Las 3 probabilidades DEBEN sumar exactamente 100.

Responde UNICAMENTE con este JSON, sin texto adicional, sin backticks:
{{
  "prob_local": <numero 0-100>,
  "prob_empate": <numero 0-100>,
  "prob_visitante": <numero 0-100>,
  "ganador": "<{nombre_local} o {nombre_visita} o Empate>",
  "confianza": "<baja|media|alta>",
  "nivel_riesgo": "<bajo|medio|alto>",
  "goles_esperados_local": <entero>,
  "goles_esperados_visitante": <entero>,
  "apuesta_1x2": "<1 victoria local | X empate | 2 victoria visitante>",
  "apuesta_ambos_anotan": "<Si | No>",
  "apuesta_total_goles": "<Mas de 2.5 | Menos de 2.5 | Mas de 1.5>",
  "apuesta_segura": "<descripcion clara de la apuesta mas segura segun los datos>",
  "razon_apuesta_segura": "<1-2 oraciones explicando por que es la mas segura estadisticamente>",
  "analisis": "<5-7 oraciones de analisis basado en los datos estadisticos>"
}}
"""

    print("\n  Analizando con Ollama (llama3.2)... ", end="", flush=True)
    resp = ollama.chat(
        model=MODEL,
        format="json",
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp["message"]["content"].strip()
    print("listo")

    raw   = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*72}")
    print("  BETBOT  --  Predictor de Partidos con IA")
    print("  football-data.org v4  +  Ollama llama3.2")
    print(f"{'='*72}\n")

    if len(API_KEY) < 10:
        print("  Pon tu API key en la linea 4 del archivo.")
        sys.exit(1)

    test = api_get("competitions/CL")
    if test is None:
        print("  No se pudo conectar. Verifica tu API key.")
        sys.exit(1)
    print("  Conectado a football-data.org\n")

    print("  Ligas disponibles:")
    for codigo, nombre in LIGAS.items():
        print(f"    {codigo:>4}  {nombre}")

    print()
    nombre_local  = input("  Equipo LOCAL:      ").strip()
    nombre_visita = input("  Equipo VISITANTE:  ").strip()

    if not nombre_local or not nombre_visita:
        print("  Debes ingresar ambos equipos.")
        sys.exit(1)

    # ── Buscar equipos
    print(f"\n  Buscando '{nombre_local}'...")
    equipo_local = buscar_equipo(nombre_local)
    if not equipo_local:
        print(f"  No se encontro '{nombre_local}'. Prueba en ingles (ej: Bayern, Arsenal).")
        sys.exit(1)
    print(f"  Encontrado: {equipo_local['name']}")

    print(f"\n  Buscando '{nombre_visita}'...")
    equipo_visita = buscar_equipo(nombre_visita)
    if not equipo_visita:
        print(f"  No se encontro '{nombre_visita}'.")
        sys.exit(1)
    print(f"  Encontrado: {equipo_visita['name']}")

    id_local  = equipo_local["id"]
    id_visita = equipo_visita["id"]

    # ── Partido en vivo
    print("\n  Verificando partidos en vivo...")
    vivo = partido_en_vivo(id_local, id_visita)
    if vivo:
        mostrar_en_vivo(vivo)
    else:
        print("  No hay partido en vivo entre estos equipos ahora mismo.")

    # ── Proximos
    proximos = proximos_partidos(id_local, id_visita)
    if proximos:
        mostrar_proximo(proximos)

    # ── Partidos recientes
    print(f"\n  Obteniendo partidos de {equipo_local['name']}...")
    partidos_local = ultimos_partidos(id_local, 8)

    print(f"  Obteniendo partidos de {equipo_visita['name']}...")
    partidos_visita = ultimos_partidos(id_visita, 8)

    if not partidos_local or not partidos_visita:
        print("  No se pudieron obtener los partidos. Intenta de nuevo.")
        sys.exit(1)

    stats_local  = calcular_stats(partidos_local)
    stats_visita = calcular_stats(partidos_visita)

    # ── Posicion en tabla
    print(f"  Obteniendo tabla de {equipo_local['name']}...")
    tabla_local  = posicion_en_tabla(id_local)

    print(f"  Obteniendo tabla de {equipo_visita['name']}...")
    tabla_visita = posicion_en_tabla(id_visita)

    # ── Goleadores
    print(f"  Obteniendo goleadores de {equipo_local['name']}...")
    goles_local  = goleadores_equipo(id_local)

    print(f"  Obteniendo goleadores de {equipo_visita['name']}...")
    goles_visita = goleadores_equipo(id_visita)

    # ── H2H
    print("  Buscando historial directo...")
    h2h = head_to_head(id_local, id_visita)

    # ── Mostrar stats
    mostrar_tabla(equipo_local["name"],  partidos_local,  stats_local,  tabla_local,  goles_local)
    mostrar_tabla(equipo_visita["name"], partidos_visita, stats_visita, tabla_visita, goles_visita)
    mostrar_h2h(h2h)

    # ── Prediccion
    try:
        resultado = predecir_con_ollama(
            equipo_local["name"],  stats_local,  tabla_local,  goles_local,
            equipo_visita["name"], stats_visita, tabla_visita, goles_visita,
            h2h, vivo
        )
        mostrar_prediccion(resultado, equipo_local["name"], equipo_visita["name"])
    except json.JSONDecodeError as e:
        print(f"\n  Ollama no devolvio JSON valido: {e}")
        print("  Intenta de nuevo.")
    except Exception as e:
        print(f"\n  Error con Ollama: {e}")
        print("  Asegurate de que Ollama este corriendo: ollama serve")

    print()


if __name__ == "__main__":
    main()
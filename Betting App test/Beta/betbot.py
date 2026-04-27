import requests
import ollama
import json
import sys
import time

API_KEY = "1682af281eb149eca5f0b502c32612b5"
print("API: ", API_KEY)
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


def sep(char="─", n=68):
    print(char * n)

def barra(pct, ancho=28):
    lleno = round(pct / 100 * ancho)
    return "#" * lleno + "." * (ancho - lleno)

def res_icono(winner, team_id, home_id, away_id):
    if winner == "DRAW":
        return "E"
    if (winner == "HOME_TEAM" and team_id == home_id) or \
       (winner == "AWAY_TEAM" and team_id == away_id):
        return "V"
    return "D"


def api_get(path, params={}):
    try:
        time.sleep(7)
        r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=10)
        if r.status_code == 429:
            print("Limite de requests alcanzado. Esperando 60 segundos...")
            time.sleep(60)
            r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=10)
        if r.status_code == 403:
            print("API Key invalida o sin permisos para esta liga.")
            return None
        if r.status_code != 200:
            print(f"Error HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        print(f"Error de conexion: {e}")
        return None


def buscar_equipo(nombre):
    nombre_lower = nombre.lower()
    encontrados = []

    for codigo in LIGAS:
        data = api_get(f"competitions/{codigo}/teams")
        if not data:
            continue
        for t in data.get("teams", []):
            campos = [
                (t.get("name") or "").lower(),
                (t.get("shortName") or "").lower(),
                (t.get("tla") or "").lower(),
            ]
            if any(nombre_lower in c for c in campos):
                encontrados.append(t)

    if not encontrados:
        return None

    vistos = set()
    unicos = []
    for e in encontrados:
        if e["id"] not in vistos:
            vistos.add(e["id"])
            unicos.append(e)

    if len(unicos) == 1:
        return unicos[0]

    print(f"\nSe encontraron {len(unicos)} equipos para '{nombre}':")
    for i, t in enumerate(unicos[:6], 1):
        print(f"  {i}. {t['name']} ({t.get('area', {}).get('name', '?')})")
    try:
        sel = int(input("Selecciona el numero: ").strip()) - 1
        return unicos[sel]
    except:
        return unicos[0]


def ultimos_partidos(team_id, limit=5):
    data = api_get(f"teams/{team_id}/matches", {
        "status": "FINISHED",
        "limit":  limit,
    })
    if not data:
        return []

    partidos = []
    for m in data.get("matches", [])[-limit:]:
        home   = m["homeTeam"]
        away   = m["awayTeam"]
        ft     = m.get("score", {}).get("fullTime", {})
        gl     = ft.get("home") or 0
        gv     = ft.get("away") or 0
        es_local = home["id"] == team_id
        gf     = gl if es_local else gv
        gc     = gv if es_local else gl
        rival  = away["name"] if es_local else home["name"]
        winner = m.get("score", {}).get("winner", "DRAW")

        partidos.append({
            "fecha":       m["utcDate"][:10],
            "rival":       rival,
            "condicion":   "LOCAL" if es_local else "VISITA",
            "gf":          gf,
            "gc":          gc,
            "resultado":   res_icono(winner, team_id, home["id"], away["id"]),
            "competicion": m.get("competition", {}).get("name", "?"),
            "home_id":     home["id"],
            "away_id":     away["id"],
            "winner":      winner,
            "team_id":     team_id,
        })

    return list(reversed(partidos))


def calcular_promedios(partidos):
    n        = len(partidos) or 1
    gf_total = sum(p["gf"] for p in partidos)
    gc_total = sum(p["gc"] for p in partidos)

    forma = ""
    for p in partidos:
        if p["resultado"] == "V":   forma += "W"
        elif p["resultado"] == "E": forma += "D"
        else:                       forma += "L"

    return {
        "goles_favor":  round(gf_total / n, 2),
        "goles_contra": round(gc_total / n, 2),
        "victorias":    forma.count("W"),
        "empates":      forma.count("D"),
        "derrotas":     forma.count("L"),
        "forma":        forma,
        "gf_total":     gf_total,
        "gc_total":     gc_total,
    }


def head_to_head(id1, id2):
    data = api_get("matches", {
        "competitions": ",".join(LIGAS.keys()),
    })
    if not data:
        return []

    h2h = []
    for m in data.get("matches", []):
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]
        ids = {home_id, away_id}
        if ids == {id1, id2} and m["status"] == "FINISHED":
            ft     = m.get("score", {}).get("fullTime", {})
            gl     = ft.get("home") or 0
            gv     = ft.get("away") or 0
            winner = m.get("score", {}).get("winner", "DRAW")
            if winner == "HOME_TEAM":   gan = m["homeTeam"]["name"]
            elif winner == "AWAY_TEAM": gan = m["awayTeam"]["name"]
            else:                       gan = "Empate"
            h2h.append({
                "fecha":   m["utcDate"][:10],
                "local":   m["homeTeam"]["name"],
                "visita":  m["awayTeam"]["name"],
                "gl":      gl,
                "gv":      gv,
                "ganador": gan,
            })

    return h2h[:5]


def partido_en_vivo(id1, id2):
    data = api_get("matches", {"status": "IN_PLAY,PAUSED,EXTRA_TIME,PENALTY_SHOOTOUT"})
    if not data:
        return None
    for m in data.get("matches", []):
        ids = {m["homeTeam"]["id"], m["awayTeam"]["id"]}
        if {id1, id2} == ids:
            return m
    return None


def proximos_partidos(id1, id2):
    data = api_get("matches", {"status": "SCHEDULED,TIMED"})
    if not data:
        return []
    proximos = []
    for m in data.get("matches", []):
        ids = {m["homeTeam"]["id"], m["awayTeam"]["id"]}
        if {id1, id2} == ids:
            proximos.append({
                "fecha":  m["utcDate"][:10],
                "hora":   m["utcDate"][11:16] + " UTC",
                "comp":   m.get("competition", {}).get("name", "?"),
                "stage":  m.get("stage", ""),
                "local":  m["homeTeam"]["name"],
                "visita": m["awayTeam"]["name"],
            })
    return proximos


def mostrar_tabla(nombre, partidos, prom):
    print(f"\nUltimos {len(partidos)} partidos - {nombre.upper()}")
    sep()
    print(f"  {'FECHA':<12} {'RIVAL':<22} {'COND':<7} {'RES':<4} {'GF':>3} {'GC':>3}  COMPETICION")
    sep()
    for p in partidos:
        print(
            f"  {p['fecha']:<12} {p['rival'][:20]:<22} {p['condicion']:<7} "
            f"{p['resultado']:<4} {p['gf']:>3} {p['gc']:>3}  {p['competicion'][:22]}"
        )
    sep()
    print(f"  {'PROMEDIO':<46} {prom['goles_favor']:>3} {prom['goles_contra']:>3}")
    print(f"\n  Forma: {' - '.join(list(prom['forma']))}   {prom['victorias']}V / {prom['empates']}E / {prom['derrotas']}D")
    sep()


def mostrar_h2h(h2h):
    if not h2h:
        print("\nSin historial directo reciente.\n")
        return
    print(f"\nHistorial directo (ultimos {len(h2h)} partidos)")
    sep()
    for p in h2h:
        print(f"  {p['fecha']}   {p['local'][:16]:>16} {p['gl']} - {p['gv']} {p['visita'][:16]:<16}   {p['ganador']}")
    sep()


def mostrar_en_vivo(m):
    ft   = m.get("score", {}).get("fullTime", {})
    gl   = ft.get("home") or 0
    gv   = ft.get("away") or 0
    comp = m.get("competition", {}).get("name", "?")
    print(f"\nPARTIDO EN VIVO - {comp}")
    print(f"{m['homeTeam']['name']} {gl} - {gv} {m['awayTeam']['name']}")
    sep()


def mostrar_proximo(proximos):
    if not proximos:
        return
    p = proximos[0]
    print(f"\nProximo enfrentamiento: {p['fecha']} {p['hora']} | {p['comp']} | {p['stage']}")
    print(f"{p['local']} vs {p['visita']}")
    sep()


def mostrar_prediccion(resultado, nombre_local, nombre_visita):
    pl  = resultado.get("prob_local", 0)
    pe  = resultado.get("prob_empate", 0)
    pv  = resultado.get("prob_visitante", 0)
    gan = resultado.get("ganador", "?")
    con = resultado.get("confianza", "media").upper()
    gl  = resultado.get("goles_esperados_local", "?")
    gv  = resultado.get("goles_esperados_visitante", "?")

    print(f"\n\nPREDICCION - {nombre_local.upper()} vs {nombre_visita.upper()}")
    sep("=")
    print(f"\nResultado probable:  {gan.upper()}")
    print(f"Marcador esperado:   {nombre_local} {gl} - {gv} {nombre_visita}")
    print(f"Confianza:           {con}\n")

    label_l = f"Victoria {nombre_local[:16]}"
    label_e = "Empate"
    label_v = f"Victoria {nombre_visita[:16]}"
    ancho   = max(len(label_l), len(label_e), len(label_v)) + 2

    print(f"{label_l:<{ancho}}  {pl:>5.1f}%  {barra(pl)}")
    print(f"{label_e:<{ancho}}  {pe:>5.1f}%  {barra(pe)}")
    print(f"{label_v:<{ancho}}  {pv:>5.1f}%  {barra(pv)}")

    print(f"\nAnalisis ({MODEL}):\n")
    for oracion in resultado.get("analisis", "Sin analisis.").replace("\n", " ").split(". "):
        oracion = oracion.strip()
        if oracion:
            print(f"  - {oracion}{'.' if not oracion.endswith('.') else ''}")
    sep("=")


def predecir_con_ollama(nombre_local, prom_local, nombre_visita, prom_visita, h2h, partido_vivo):
    contexto_vivo = ""
    if partido_vivo:
        ft = partido_vivo.get("score", {}).get("fullTime", {})
        contexto_vivo = f"\nPARTIDO EN VIVO ahora: {nombre_local} {ft.get('home', 0)} - {ft.get('away', 0)} {nombre_visita}\n"

    h2h_texto = ""
    if h2h:
        for p in h2h:
            h2h_texto += f"  {p['fecha']}: {p['local']} {p['gl']}-{p['gv']} {p['visita']} -> {p['ganador']}\n"
    else:
        h2h_texto = "  Sin datos disponibles"

    prompt = f"""
Eres un analista deportivo experto en estadisticas de futbol.
Analiza los datos y predice el resultado.
{contexto_vivo}
EQUIPO LOCAL: {nombre_local}
Forma: {prom_local['forma']}
Balance: {prom_local['victorias']}V / {prom_local['empates']}E / {prom_local['derrotas']}D
Goles a favor promedio: {prom_local['goles_favor']}
Goles en contra promedio: {prom_local['goles_contra']}

EQUIPO VISITANTE: {nombre_visita}
Forma: {prom_visita['forma']}
Balance: {prom_visita['victorias']}V / {prom_visita['empates']}E / {prom_visita['derrotas']}D
Goles a favor promedio: {prom_visita['goles_favor']}
Goles en contra promedio: {prom_visita['goles_contra']}

HISTORIAL DIRECTO:
{h2h_texto}

IMPORTANTE: Responde SOLO con el JSON. Nada mas. Ni una palabra antes ni despues. Solo el JSON puro:
{{
  "prob_local": <0-100>,
  "prob_empate": <0-100>,
  "prob_visitante": <0-100>,
  "ganador": "<nombre del equipo o Empate>",
  "confianza": "<baja|media|alta>",
  "goles_esperados_local": <entero>,
  "goles_esperados_visitante": <entero>,
  "analisis": "<4-6 oraciones basadas en los datos>"
}}
Las tres probabilidades deben sumar exactamente 100.
"""

    print("\nAnalizando con Ollama... ", end="", flush=True)
    resp = ollama.chat(
        model=MODEL,
        format="json",
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp["message"]["content"].strip()
    print("listo")

    # Limpieza robusta
    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)


def main():
    sep("=")
    print("  MATCH ORACLE - Predictor de Partidos")
    print("  football-data.org v4 + Ollama")
    sep("=")   
    if len(API_KEY) < 10:
     print("Pon tu API key en la linea 7 del archivo.")
     print("Registrate gratis en: https://www.football-data.org/client/register")
     sys.exit(1)

    test = api_get("competitions/CL")
    if test is None:
        print("No se pudo conectar. Verifica tu API key.")
        sys.exit(1)
    print("Conectado a football-data.org\n")

    print("Ligas disponibles:")
    for codigo, nombre in LIGAS.items():
        print(f"  {codigo:>4}  {nombre}")

    print()
    nombre_local  = input("Equipo LOCAL:      ").strip()
    nombre_visita = input("Equipo VISITANTE:  ").strip()

    if not nombre_local or not nombre_visita:
        print("Debes ingresar ambos equipos.")
        sys.exit(1)

    print(f"\nBuscando '{nombre_local}'...")
    equipo_local = buscar_equipo(nombre_local)
    if not equipo_local:
        print(f"No se encontro '{nombre_local}'. Prueba en ingles (ej: Bayern, Arsenal).")
        sys.exit(1)
    print(f"Encontrado: {equipo_local['name']}")

    print(f"\nBuscando '{nombre_visita}'...")
    equipo_visita = buscar_equipo(nombre_visita)
    if not equipo_visita:
        print(f"No se encontro '{nombre_visita}'.")
        sys.exit(1)
    print(f"Encontrado: {equipo_visita['name']}")

    id_local  = equipo_local["id"]
    id_visita = equipo_visita["id"]

    print("\nVerificando partidos en vivo...")
    vivo = partido_en_vivo(id_local, id_visita)
    if vivo:
        mostrar_en_vivo(vivo)
    else:
        print("No hay partido en vivo entre estos equipos ahora mismo.")

    proximos = proximos_partidos(id_local, id_visita)
    if proximos:
        mostrar_proximo(proximos)

    print(f"\nObteniendo partidos de {equipo_local['name']}...")
    partidos_local = ultimos_partidos(id_local, 5)

    print(f"Obteniendo partidos de {equipo_visita['name']}...")
    partidos_visita = ultimos_partidos(id_visita, 5)

    if not partidos_local or not partidos_visita:
        print("No se pudieron obtener los partidos. Intenta de nuevo.")
        sys.exit(1)

    prom_local  = calcular_promedios(partidos_local)
    prom_visita = calcular_promedios(partidos_visita)

    print("Buscando historial directo...")
    h2h = head_to_head(id_local, id_visita)

    mostrar_tabla(equipo_local["name"],  partidos_local,  prom_local)
    mostrar_tabla(equipo_visita["name"], partidos_visita, prom_visita)
    mostrar_h2h(h2h)

    try:
        resultado = predecir_con_ollama(
            equipo_local["name"],  prom_local,
            equipo_visita["name"], prom_visita,
            h2h, vivo
        )
        mostrar_prediccion(resultado, equipo_local["name"], equipo_visita["name"])
    except json.JSONDecodeError:
        print("Ollama no devolvio JSON valido. Intenta de nuevo.")
    except Exception as e:
        print(f"Error con Ollama: {e}")
        print("Asegurate de que Ollama este corriendo: ollama serve")

    print()


if __name__ == "__main__":
    main()
import os
import re
import csv
import io
import json
import urllib.request
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, g, flash, session, send_file)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "prode-mundial-2026")

# Códigos ISO para flagcdn.com (gb-sct / gb-eng para Escocia e Inglaterra)
FLAG_CODES = {
    "Argentina": "ar",    "Argelia": "dz",       "Australia": "au",
    "Austria": "at",      "Arabia Saudita": "sa", "Alemania": "de",
    "Bélgica": "be",      "Bosnia": "ba",         "Brasil": "br",
    "Canadá": "ca",       "Cabo Verde": "cv",     "Colombia": "co",
    "Corea del Sur": "kr","Costa de Marfil": "ci","Croacia": "hr",
    "Curazao": "cw",      "Ecuador": "ec",        "EE.UU.": "us",
    "Egipto": "eg",       "Escocia": "gb-sct",    "España": "es",
    "Francia": "fr",      "Ghana": "gh",          "Haití": "ht",
    "Inglaterra": "gb-eng","Irak": "iq",          "Irán": "ir",
    "Japón": "jp",        "Jordania": "jo",       "Marruecos": "ma",
    "México": "mx",       "Nueva Zelanda": "nz",  "Noruega": "no",
    "Países Bajos": "nl", "Panamá": "pa",         "Paraguay": "py",
    "Portugal": "pt",     "Qatar": "qa",          "Rep. Checa": "cz",
    "República Checa": "cz","Rep. Dem. Congo": "cd","Senegal": "sn",
    "Sudáfrica": "za",    "Suecia": "se",         "Suiza": "ch",
    "Túnez": "tn",        "Turquía": "tr",        "Uruguay": "uy",
    "Uzbekistán": "uz",
}

SIGLAS = {
    "Argentina": "ARG",  "Argelia": "ALG",    "Australia": "AUS",
    "Austria": "AUT",    "Arabia Saudita": "KSA", "Alemania": "ALE",
    "Bélgica": "BEL",    "Bosnia": "BIH",     "Brasil": "BRA",
    "Canadá": "CAN",     "Cabo Verde": "CPV", "Colombia": "COL",
    "Corea del Sur": "COR","Costa de Marfil": "CIV","Croacia": "CRO",
    "Curazao": "CUW",    "Ecuador": "ECU",    "EE.UU.": "USA",
    "Egipto": "EGY",     "Escocia": "SCO",    "España": "ESP",
    "Francia": "FRA",    "Ghana": "GHA",      "Haití": "HAI",
    "Inglaterra": "ING", "Irak": "IRQ",       "Irán": "IRN",
    "Japón": "JPN",      "Jordania": "JOR",   "Marruecos": "MAR",
    "México": "MEX",     "Nueva Zelanda": "NZL","Noruega": "NOR",
    "Países Bajos": "NED","Panamá": "PAN",    "Paraguay": "PAR",
    "Portugal": "POR",   "Qatar": "QAT",      "Rep. Checa": "CZE",
    "República Checa": "CZE","Rep. Dem. Congo": "COD","Senegal": "SEN",
    "Sudáfrica": "RSA",  "Suecia": "SUE",     "Suiza": "SUI",
    "Túnez": "TUN",      "Turquía": "TUR",    "Uruguay": "URU",
    "Uzbekistán": "UZB",
}
app.jinja_env.globals["siglas"] = SIGLAS

def lote_label(partido):
    """Devuelve etiqueta de fase legible: 'Jornada 1 – Grupos' para grupos, fase tal cual para el resto."""
    fase = (partido.get("fase") or "Grupos").strip()
    if fase == "Grupos":
        lote = partido.get("lote") or 1
        return f"Jornada {lote} – Grupos"
    return fase
app.jinja_env.globals["lote_label"] = lote_label

# Traduce nombres de football-data.org (inglés) → nombres usados en la DB (español)
NOMBRES_API = {
    "Mexico":"México", "South Africa":"Sudáfrica", "South Korea":"Corea del Sur",
    "Czechia":"Rep. Checa", "Czech Republic":"Rep. Checa",
    "Canada":"Canadá", "Bosnia and Herzegovina":"Bosnia",
    "Switzerland":"Suiza", "Brazil":"Brasil", "Morocco":"Marruecos",
    "Haiti":"Haití", "Scotland":"Escocia", "USA":"EE.UU.",
    "United States":"EE.UU.", "Australia":"Australia", "Turkey":"Turquía",
    "Germany":"Alemania", "Curaçao":"Curazao", "Curacao":"Curazao",
    "Ivory Coast":"Costa de Marfil", "Côte d'Ivoire":"Costa de Marfil",
    "Ecuador":"Ecuador", "Netherlands":"Países Bajos",
    "Japan":"Japón", "Sweden":"Suecia", "Tunisia":"Túnez",
    "Belgium":"Bélgica", "Egypt":"Egipto", "Iran":"Irán",
    "New Zealand":"Nueva Zelanda", "Spain":"España", "Cape Verde":"Cabo Verde",
    "Saudi Arabia":"Arabia Saudita", "Uruguay":"Uruguay", "France":"Francia",
    "Senegal":"Senegal", "Iraq":"Irak", "Norway":"Noruega",
    "Argentina":"Argentina", "Algeria":"Argelia", "Austria":"Austria",
    "Jordan":"Jordania", "Portugal":"Portugal",
    "DR Congo":"Rep. Dem. Congo", "Congo DR":"Rep. Dem. Congo",
    "Uzbekistan":"Uzbekistán", "Colombia":"Colombia",
    "England":"Inglaterra", "Croatia":"Croacia", "Ghana":"Ghana",
    "Panama":"Panamá", "Paraguay":"Paraguay", "Qatar":"Qatar",
}

def bandera_img(nombre, size=24):
    code = FLAG_CODES.get(nombre)
    if not code:
        return ""
    return (f'<img src="https://flagcdn.com/w40/{code}.png" '
            f'width="{size}" height="{round(size*0.67)}" '
            f'alt="{nombre}" style="vertical-align:middle;border-radius:2px;">')

app.jinja_env.globals["bandera_img"] = bandera_img
app.jinja_env.globals["banderas"]    = FLAG_CODES  # por si algún template usa banderas.get()

ADMIN_PASSWORD      = os.environ.get("ADMIN_PASSWORD", "gipa2026")
DATABASE_URL        = os.environ.get("DATABASE_URL")        # Render lo setea automáticamente
FOOTBALL_DATA_KEY   = os.environ.get("FOOTBALL_DATA_KEY", "")
FECHA_CIERRE        = "2026-06-15"   # referencia histórica (ya no cierra automáticamente)
_FECHA_LIMITE_ORD   = 615            # partidos del 15/06 o antes quedan bloqueados

def pronosticos_abiertos():
    return True  # el cierre lo controla el admin publicando/ocultando lotes

def partido_bloqueado(p):
    """True si el partido ya tiene resultado O su fecha es anterior al 16/06."""
    if p.get("goles_local") is not None:
        return True
    return _fecha_ord(p.get("fecha") or "") <= _FECHA_LIMITE_ORD

# SQLite (local)
DB = os.path.join(os.path.dirname(__file__), "prode.db")

# ── Google Sheets (opcional) ───────────────────────────────────────
GOOGLE_SHEET_ID  = os.environ.get("GOOGLE_SHEET_ID", "")
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
# ──────────────────────────────────────────────────────────────────

# ─────────────────── DB abstraction (SQLite ↔ PostgreSQL) ─────────

def get_db():
    if "db" not in g:
        if DATABASE_URL:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            g.db = conn
            g.db_type = "pg"
        else:
            import sqlite3
            conn = sqlite3.connect(DB)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
            g.db_type = "sqlite"
    return g.db

def db_type():
    get_db()
    return g.db_type

def placeholder():
    return "%s" if db_type() == "pg" else "?"

def fetchall(cur):
    if db_type() == "pg":
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]

def fetchone(cur):
    if db_type() == "pg":
        if cur.description is None:
            return None
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    row = cur.fetchone()
    return dict(row) if row else None

def db_execute(sql, params=()):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(sql, params)
    return cur

def db_commit():
    get_db().commit()

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

# ── Schema ────────────────────────────────────────────────────────

def init_db():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS partidos (
                id             SERIAL PRIMARY KEY,
                fase           TEXT    DEFAULT 'Grupos',
                equipo_local   TEXT    NOT NULL,
                equipo_visit   TEXT    NOT NULL,
                fecha          TEXT,
                goles_local    INTEGER,
                goles_visit    INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pronosticos (
                id          SERIAL PRIMARY KEY,
                timestamp   TEXT    NOT NULL,
                nombre      TEXT    NOT NULL,
                partido_id  INTEGER NOT NULL REFERENCES partidos(id),
                goles_local INTEGER NOT NULL DEFAULT 0,
                goles_visit INTEGER NOT NULL DEFAULT 0,
                puntos      INTEGER,
                UNIQUE(nombre, partido_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                nombre TEXT PRIMARY KEY,
                avatar TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lotes (
                numero    INTEGER PRIMARY KEY,
                nombre    TEXT    NOT NULL,
                fechas    TEXT,
                publicado INTEGER DEFAULT 0
            )
        """)
        # Agregar columna lote si la tabla ya existe sin ella
        cur.execute(
            "ALTER TABLE partidos ADD COLUMN IF NOT EXISTS lote INTEGER DEFAULT 1"
        )
        conn.commit()
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(DB)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS partidos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                fase           TEXT    DEFAULT 'Grupos',
                equipo_local   TEXT    NOT NULL,
                equipo_visit   TEXT    NOT NULL,
                fecha          TEXT,
                goles_local    INTEGER,
                goles_visit    INTEGER,
                lote           INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS pronosticos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                nombre      TEXT    NOT NULL,
                partido_id  INTEGER NOT NULL REFERENCES partidos(id),
                goles_local INTEGER NOT NULL DEFAULT 0,
                goles_visit INTEGER NOT NULL DEFAULT 0,
                puntos      INTEGER,
                UNIQUE(nombre, partido_id)
            );
            CREATE TABLE IF NOT EXISTS usuarios (
                nombre TEXT PRIMARY KEY,
                avatar TEXT
            );
            CREATE TABLE IF NOT EXISTS lotes (
                numero    INTEGER PRIMARY KEY,
                nombre    TEXT    NOT NULL,
                fechas    TEXT,
                publicado INTEGER DEFAULT 0
            );
        """)
        # Agregar columna lote a tabla existente si no tiene la columna
        try:
            conn.execute("ALTER TABLE partidos ADD COLUMN lote INTEGER DEFAULT 1")
            conn.commit()
        except Exception:
            pass  # ya existe
        conn.commit()
        conn.close()

# ── Puntos ────────────────────────────────────────────────────────

def calcular_puntos(pl, pv, rl, rv):
    if pl == rl and pv == rv:
        return 3
    def res(a, b): return "L" if a > b else ("E" if a == b else "V")
    return 1 if res(pl, pv) == res(rl, rv) else 0

# ── Rutas públicas ────────────────────────────────────────────────

@app.route("/")
def index():
    lote_max = 99
    try:
        lote_row = fetchone(db_execute(
            "SELECT COALESCE(MAX(numero), 99) AS m FROM lotes WHERE publicado=1"))
        lote_max = lote_row["m"] if (lote_row and lote_row["m"] is not None) else 99
        ph = placeholder()
        if lote_max < 99:
            # Mostrar solo el lote activo (el publicado más alto)
            partidos = fetchall(db_execute(
                f"SELECT * FROM partidos WHERE lote = {ph} ORDER BY fecha, id", (lote_max,)))
        else:
            partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))
    except Exception:
        partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))
    for partido in partidos:
        partido["bloqueado"] = partido_bloqueado(partido)

    # Pre-cargar predicciones existentes si viene ?nombre=X en la URL
    nombre_param = request.args.get("nombre", "").strip()
    previos = {}
    if nombre_param:
        ph = placeholder()
        rows = fetchall(db_execute(
            f"SELECT partido_id, goles_local, goles_visit FROM pronosticos WHERE nombre={ph}",
            (nombre_param,)))
        previos = {r["partido_id"]: r for r in rows}

    # Usuarios que ya cargaron el lote activo no aparecen en el desplegable
    todos_usuarios = [r["nombre"] for r in fetchall(db_execute(
        "SELECT DISTINCT nombre FROM pronosticos ORDER BY nombre"))]
    try:
        ph = placeholder()
        ya_cargaron = {r["nombre"] for r in fetchall(db_execute(f"""
            SELECT DISTINCT pr.nombre
            FROM pronosticos pr
            JOIN partidos pa ON pa.id = pr.partido_id
            WHERE pa.lote = {ph}
        """, (lote_max,)))}
    except Exception:
        ya_cargaron = set()
    usuarios_existentes = [u for u in todos_usuarios if u not in ya_cargaron]

    return render_template("index.html", partidos=partidos,
                           abierto=pronosticos_abiertos(), fecha_cierre=FECHA_CIERRE,
                           nombre_param=nombre_param, previos=previos,
                           usuarios_existentes=usuarios_existentes)

@app.route("/pronostico", methods=["POST"])
def pronostico():
    if not pronosticos_abiertos():
        flash("Los pronósticos están cerrados desde el 16 de junio.")
        return redirect(url_for("index"))
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("Ingresá tu nombre para guardar los pronósticos.")
        return redirect(url_for("index"))

    p = placeholder()
    for key in request.form:
        if not key.startswith("local_"):
            continue
        pid = int(key.split("_", 1)[1])
        # No guardar si el partido está bloqueado (resultado cargado o fecha < 16/06)
        partido = fetchone(db_execute(f"SELECT * FROM partidos WHERE id={p}", (pid,)))
        if partido and partido_bloqueado(partido):
            continue
        gl  = int(request.form.get(f"local_{pid}", 0) or 0)
        gv  = int(request.form.get(f"visit_{pid}", 0) or 0)
        ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(f"""
            INSERT INTO pronosticos (timestamp, nombre, partido_id, goles_local, goles_visit)
            VALUES ({p},{p},{p},{p},{p})
            ON CONFLICT(nombre, partido_id) DO UPDATE SET
                goles_local = EXCLUDED.goles_local,
                goles_visit = EXCLUDED.goles_visit,
                timestamp   = EXCLUDED.timestamp,
                puntos      = NULL
        """, (ts, nombre, pid, gl, gv))

    db_commit()
    return redirect(url_for("mis_pronosticos", nombre=nombre))

@app.route("/mis-pronosticos/<nombre>")
def mis_pronosticos(nombre):
    p = placeholder()
    partidos  = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))
    pron_rows = fetchall(db_execute(
        f"SELECT * FROM pronosticos WHERE nombre={p}", (nombre,)))
    pron = {r["partido_id"]: r for r in pron_rows}
    usuario = fetchone(db_execute(f"SELECT avatar FROM usuarios WHERE nombre={p}", (nombre,)))
    avatar  = usuario["avatar"] if usuario and usuario.get("avatar") else None
    return render_template("mis_pronosticos.html",
                           nombre=nombre, partidos=partidos, pronosticos=pron, avatar=avatar)


@app.route("/perfil/<nombre>", methods=["GET", "POST"])
def perfil(nombre):
    p = placeholder()
    if request.method == "POST":
        avatar_data = request.form.get("avatar_data", "").strip()
        if avatar_data and avatar_data.startswith("data:image"):
            # Limitar a ~200KB
            if len(avatar_data) <= 204800:
                db_execute(f"""
                    INSERT INTO usuarios (nombre, avatar) VALUES ({p},{p})
                    ON CONFLICT(nombre) DO UPDATE SET avatar=EXCLUDED.avatar
                """, (nombre, avatar_data))
                db_commit()
                flash("Foto de perfil actualizada.")
            else:
                flash("La imagen es demasiado grande. Usá una foto más pequeña.")
        return redirect(url_for("mis_pronosticos", nombre=nombre))
    usuario = fetchone(db_execute(f"SELECT avatar FROM usuarios WHERE nombre={p}", (nombre,)))
    avatar  = usuario["avatar"] if usuario and usuario.get("avatar") else None
    return render_template("perfil.html", nombre=nombre, avatar=avatar)

def _avatares():
    """Devuelve dict {nombre: avatar_data_url} para todos los usuarios con foto."""
    return {r["nombre"]: r["avatar"] for r in fetchall(
        db_execute("SELECT nombre, avatar FROM usuarios WHERE avatar IS NOT NULL"))}


@app.route("/tabla")
def tabla():
    rows = fetchall(db_execute("""
        SELECT nombre,
               COUNT(*)                                       AS jugados,
               SUM(CASE WHEN puntos=3 THEN 1 ELSE 0 END)     AS exactos,
               SUM(CASE WHEN puntos=1 THEN 1 ELSE 0 END)     AS resultados,
               COALESCE(SUM(puntos), 0)                       AS total
        FROM   pronosticos
        WHERE  puntos IS NOT NULL
        GROUP  BY nombre
        ORDER  BY total DESC, exactos DESC
    """))
    return render_template("tabla.html", tabla=rows, avatares=_avatares())

def _fecha_ord(fecha_str):
    """Convierte '14/06 Grupo A' → número comparable 614. Sin fecha → 9999."""
    try:
        parte = fecha_str.split()[0]          # '14/06'
        d, m  = parte.split("/")
        return int(m) * 100 + int(d)
    except Exception:
        return 9999

@app.route("/todos")
def todos():
    try:
        lote_row = fetchone(db_execute(
            "SELECT COALESCE(MAX(numero), 99) AS m FROM lotes WHERE publicado=1"))
        lote_max = lote_row["m"] if (lote_row and lote_row["m"] is not None) else 99
    except Exception:
        lote_max = 99

    nombres = [r["nombre"] for r in fetchall(db_execute(
        "SELECT DISTINCT nombre FROM pronosticos ORDER BY nombre"))]

    try:
        ph = placeholder()
        todos_partidos = fetchall(db_execute(
            f"SELECT * FROM partidos WHERE lote <= {ph} ORDER BY fecha, id", (lote_max,)))
    except Exception:
        todos_partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))

    for p in todos_partidos:
        p["fase_label"] = lote_label(p)

    ph = placeholder()
    prons = {}
    for n in nombres:
        prons[n] = {str(r["partido_id"]): {
            "goles_local": r["goles_local"],
            "goles_visit": r["goles_visit"],
            "puntos": r["puntos"]
        } for r in fetchall(db_execute(f"SELECT * FROM pronosticos WHERE nombre={ph}", (n,)))}

    # Anti-copia: predicciones del lote actual ocultas hasta que todos completen
    pred_visible_max = lote_max
    todos_completo   = True
    faltantes        = []
    lote_actual_nombre = ""
    try:
        ph = placeholder()
        n_row = fetchone(db_execute(
            f"SELECT COUNT(*) AS cnt FROM partidos WHERE lote = {ph}", (lote_max,)))
        n_partidos_lote = n_row["cnt"] if n_row else 0
        if n_partidos_lote > 0 and nombres:
            ph = placeholder()
            lnrow = fetchone(db_execute(
                f"SELECT nombre FROM lotes WHERE numero = {ph}", (lote_max,)))
            lote_actual_nombre = lnrow["nombre"] if lnrow else f"Lote {lote_max}"
            ph = placeholder()
            completions = fetchall(db_execute(f"""
                SELECT pr.nombre, COUNT(*) AS pred_count
                FROM pronosticos pr
                JOIN partidos pa ON pa.id = pr.partido_id
                WHERE pa.lote = {ph}
                GROUP BY pr.nombre
            """, (lote_max,)))
            done = {r["nombre"]: r["pred_count"] for r in completions}
            faltantes = [n for n in nombres if done.get(n, 0) < n_partidos_lote]
            todos_completo = len(faltantes) == 0
            if not todos_completo:
                pred_visible_max = lote_max - 1
    except Exception:
        pass

    return render_template("todos.html",
                           partidos_json=todos_partidos, nombres=nombres,
                           pronosticos=prons, avatares=_avatares(),
                           pred_visible_max=pred_visible_max,
                           todos_completo=todos_completo,
                           faltantes=faltantes,
                           lote_actual_nombre=lote_actual_nombre)

# ── Admin ─────────────────────────────────────────────────────────

def _do_sync_resultados():
    """Trae partidos terminados de football-data.org y actualiza DB. Retorna mensaje."""
    if not FOOTBALL_DATA_KEY:
        return None
    try:
        req = urllib.request.Request(
            "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED",
            headers={"X-Auth-Token": FOOTBALL_DATA_KEY}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        p = placeholder()
        actualizados = 0
        sin_mapeo = []
        sin_partido = []
        terminados = [m for m in data.get("matches", [])
                      if m.get("score", {}).get("winner") is not None]

        for m in terminados:
            ft = m.get("score", {}).get("fullTime", {})
            gl = ft.get("home")
            gv = ft.get("away")
            if gl is None or gv is None:
                continue
            home_en = m.get("homeTeam", {}).get("name", "")
            away_en = m.get("awayTeam", {}).get("name", "")
            home_es = NOMBRES_API.get(home_en, "")
            away_es = NOMBRES_API.get(away_en, "")
            if not home_es or not away_es:
                sin_mapeo.append(f"{home_en} vs {away_en}")
                continue
            partido = fetchone(db_execute(
                f"SELECT * FROM partidos WHERE equipo_local={p} AND equipo_visit={p}",
                (home_es, away_es)))
            if not partido:
                sin_partido.append(f"{home_es} vs {away_es}")
                continue
            if partido["goles_local"] == gl and partido["goles_visit"] == gv:
                continue
            db_execute(
                f"UPDATE partidos SET goles_local={p}, goles_visit={p} WHERE id={p}",
                (gl, gv, partido["id"]))
            for pron in fetchall(db_execute(
                    f"SELECT * FROM pronosticos WHERE partido_id={p}", (partido["id"],))):
                pts = calcular_puntos(pron["goles_local"], pron["goles_visit"], gl, gv)
                db_execute(f"UPDATE pronosticos SET puntos={p} WHERE id={p}", (pts, pron["id"]))
            actualizados += 1

        db_commit()
        msg = f"Auto-sync: {actualizados} partido(s) actualizado(s) de {len(terminados)} terminado(s)."
        if sin_mapeo:
            msg += f" Sin mapeo: {', '.join(sin_mapeo[:3])}."
        if sin_partido:
            msg += f" No encontrados en DB: {', '.join(sin_partido[:3])}."
        return msg
    except Exception as e:
        return f"Error al sincronizar: {e}"


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            flash("Contraseña incorrecta.")
    if not session.get("admin"):
        return render_template("admin_login.html")
    # Auto-sync al abrir el panel
    msg = _do_sync_resultados()
    if msg:
        flash(msg)
    partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))
    participantes = [r["nombre"] for r in fetchall(db_execute(
        "SELECT DISTINCT nombre FROM pronosticos ORDER BY nombre"))]
    try:
        lotes = fetchall(db_execute("SELECT * FROM lotes ORDER BY numero"))
    except Exception:
        lotes = []
    return render_template("admin.html", partidos=partidos,
                           participantes=participantes, lotes=lotes,
                           equipos_lista=sorted(FLAG_CODES.keys()))

@app.route("/admin/partido", methods=["POST"])
def admin_partido():
    if not session.get("admin"): return redirect(url_for("admin"))
    p = placeholder()
    db_execute(
        f"INSERT INTO partidos (fase, equipo_local, equipo_visit, fecha) VALUES ({p},{p},{p},{p})",
        (request.form["fase"], request.form["local"],
         request.form["visitante"], request.form["fecha"]))
    db_commit()
    return redirect(url_for("admin"))

@app.route("/admin/resultado", methods=["POST"])
def admin_resultado():
    if not session.get("admin"): return redirect(url_for("admin"))
    p   = placeholder()
    pid = int(request.form["partido_id"])
    gl  = int(request.form["goles_local"])
    gv  = int(request.form["goles_visit"])
    db_execute(
        f"UPDATE partidos SET goles_local={p}, goles_visit={p} WHERE id={p}", (gl, gv, pid))
    for pron in fetchall(db_execute(
            f"SELECT * FROM pronosticos WHERE partido_id={p}", (pid,))):
        pts = calcular_puntos(pron["goles_local"], pron["goles_visit"], gl, gv)
        db_execute(f"UPDATE pronosticos SET puntos={p} WHERE id={p}", (pts, pron["id"]))
    db_commit()
    return redirect(url_for("admin"))

@app.route("/admin/borrar-partido/<int:pid>", methods=["POST"])
def borrar_partido(pid):
    if not session.get("admin"): return redirect(url_for("admin"))
    p = placeholder()
    db_execute(f"DELETE FROM pronosticos WHERE partido_id={p}", (pid,))
    db_execute(f"DELETE FROM partidos WHERE id={p}", (pid,))
    db_commit()
    return redirect(url_for("admin"))

@app.route("/admin/publicar-lote/<int:n>", methods=["POST"])
def publicar_lote(n):
    if not session.get("admin"): return redirect(url_for("admin"))
    p = placeholder()
    db_execute(f"UPDATE lotes SET publicado=1 WHERE numero={p}", (n,))
    db_commit()
    lote_row = fetchone(db_execute(f"SELECT nombre FROM lotes WHERE numero={p}", (n,)))
    nombre_lote = lote_row["nombre"] if lote_row else f"Lote {n}"
    flash(f"✅ Publicado: {nombre_lote}")
    return redirect(url_for("admin"))

@app.route("/admin/despublicar-lote/<int:n>", methods=["POST"])
def despublicar_lote(n):
    if not session.get("admin"): return redirect(url_for("admin"))
    p = placeholder()
    db_execute(f"UPDATE lotes SET publicado=0 WHERE numero={p}", (n,))
    db_commit()
    lote_row = fetchone(db_execute(f"SELECT nombre FROM lotes WHERE numero={p}", (n,)))
    nombre_lote = lote_row["nombre"] if lote_row else f"Lote {n}"
    flash(f"🔒 Ocultado: {nombre_lote}")
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

# ── Reporte estadísticas ──────────────────────────────────────────

def _reporte_data():
    g_row = fetchone(db_execute("""
        SELECT COUNT(DISTINCT pa.id)                               AS partidos_jugados,
               COUNT(DISTINCT pr.nombre)                           AS participantes,
               COUNT(*)                                            AS total_prons,
               SUM(CASE WHEN pr.puntos=3 THEN 1 ELSE 0 END)       AS total_exactos,
               SUM(CASE WHEN pr.puntos=1 THEN 1 ELSE 0 END)       AS total_resultados,
               SUM(CASE WHEN pr.puntos=0 THEN 1 ELSE 0 END)       AS total_fallidos
        FROM pronosticos pr
        JOIN partidos pa ON pa.id = pr.partido_id
        WHERE pr.puntos IS NOT NULL
    """)) or {}
    partidos_stats = fetchall(db_execute("""
        SELECT pa.id, pa.equipo_local, pa.equipo_visit,
               pa.goles_local, pa.goles_visit, pa.fase,
               COUNT(*)                                            AS total,
               SUM(CASE WHEN pr.puntos=3 THEN 1 ELSE 0 END)       AS exactos,
               SUM(CASE WHEN pr.puntos=1 THEN 1 ELSE 0 END)       AS resultados,
               SUM(CASE WHEN pr.puntos=0 THEN 1 ELSE 0 END)       AS fallidos
        FROM pronosticos pr
        JOIN partidos pa ON pa.id = pr.partido_id
        WHERE pr.puntos IS NOT NULL
        GROUP BY pa.id, pa.equipo_local, pa.equipo_visit,
                 pa.goles_local, pa.goles_visit, pa.fase
    """))
    for p in partidos_stats:
        t = p["total"] or 1
        p["pct_exacto"]    = round(p["exactos"]    * 100 / t, 1)
        p["pct_resultado"] = round(p["resultados"] * 100 / t, 1)
        p["pct_fallido"]   = round(p["fallidos"]   * 100 / t, 1)
        p["label"] = f"{p['equipo_local']} vs {p['equipo_visit']}"
    partidos_stats.sort(key=lambda x: x["pct_exacto"], reverse=True)
    usuarios_stats = fetchall(db_execute("""
        SELECT nombre,
               COUNT(*)                                            AS jugados,
               SUM(CASE WHEN puntos=3 THEN 1 ELSE 0 END)          AS exactos,
               SUM(CASE WHEN puntos=1 THEN 1 ELSE 0 END)          AS resultados,
               SUM(CASE WHEN puntos=0 THEN 1 ELSE 0 END)          AS fallidos,
               COALESCE(SUM(puntos), 0)                            AS total
        FROM pronosticos
        WHERE puntos IS NOT NULL
        GROUP BY nombre
        ORDER BY total DESC, exactos DESC
    """))

    # ── Evolución de posiciones por partido jugado ────────────────
    evo_rows = fetchall(db_execute("""
        SELECT pa.id AS partido_id,
               pa.equipo_local, pa.equipo_visit,
               COALESCE(pa.fecha, '') AS fecha,
               pr.nombre, pr.puntos
        FROM partidos pa
        JOIN pronosticos pr ON pr.partido_id = pa.id
        WHERE pr.puntos IS NOT NULL
        ORDER BY pa.id
    """))
    evo_labels, evo_users, evo_ranks = [], [], {}
    if evo_rows:
        pid_pts, pid_info, pid_order = {}, {}, []
        for row in evo_rows:
            pid = row["partido_id"]
            if pid not in pid_pts:
                pid_pts[pid] = {}
                pid_info[pid] = {"local": row["equipo_local"],
                                 "visit": row["equipo_visit"],
                                 "fecha": row["fecha"]}
                pid_order.append(pid)
            pid_pts[pid][row["nombre"]] = row["puntos"]

        def _day(info):
            m = re.match(r"(\d{1,2}/\d{1,2})", str(info["fecha"]))
            return m.group(1) if m else "S/F"

        # Agrupar partidos por día y ordenar cronológicamente (DD/MM)
        day_pids = {}
        for pid in pid_order:
            day = _day(pid_info[pid])
            day_pids.setdefault(day, []).append(pid)

        def _day_key(d):
            try:
                dd, mm = d.split("/")
                return (int(mm), int(dd))
            except Exception:
                return (99, 99)

        day_order = sorted(day_pids.keys(), key=_day_key)

        evo_users = sorted({r["nombre"] for r in evo_rows})
        cumulative = {u: 0 for u in evo_users}
        evo_ranks  = {u: [] for u in evo_users}
        for day in day_order:
            for pid in day_pids[day]:
                for u, pts in pid_pts[pid].items():
                    cumulative[u] = cumulative.get(u, 0) + pts
            order = sorted(evo_users, key=lambda u: (-cumulative[u], u))
            for u in evo_users:
                evo_ranks[u].append(order.index(u) + 1)
            evo_labels.append(day)

    return g_row, partidos_stats, usuarios_stats, evo_labels, evo_users, evo_ranks

def _render_reporte(**extra):
    g, partidos_stats, usuarios_stats, evo_labels, evo_users, evo_ranks = _reporte_data()
    return render_template("admin_reporte.html",
                           g=g,
                           partidos_stats=partidos_stats,
                           usuarios_stats=usuarios_stats,
                           evo_labels=evo_labels,
                           evo_users=evo_users,
                           evo_ranks=evo_ranks,
                           **extra)

@app.route("/reporte")
def reporte():
    return _render_reporte()

@app.route("/admin/reporte")
def admin_reporte():
    if not session.get("admin"): return redirect(url_for("admin"))
    return _render_reporte()

# ── Export CSV ────────────────────────────────────────────────────

@app.route("/admin/export-csv")
def export_csv():
    if not session.get("admin"): return redirect(url_for("admin"))
    rows = fetchall(db_execute("""
        SELECT p.nombre, pa.equipo_local, pa.equipo_visit, pa.fase,
               p.goles_local AS pred_local, p.goles_visit AS pred_visit,
               pa.goles_local AS real_local, pa.goles_visit AS real_visit,
               p.puntos, p.timestamp
        FROM pronosticos p
        JOIN partidos pa ON pa.id = p.partido_id
        ORDER BY p.nombre, pa.fecha, pa.id
    """))
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["Nombre","Local","Visitante","Fase",
                "Pred.Local","Pred.Visit","Real.Local","Real.Visit","Puntos","Timestamp"])
    for r in rows:
        w.writerow([r.get(k) for k in
                    ["nombre","equipo_local","equipo_visit","fase",
                     "pred_local","pred_visit","real_local","real_visit","puntos","timestamp"]])
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"prode_{datetime.now().strftime('%Y%m%d')}.csv"
    )

# ── Google Sheets sync ────────────────────────────────────────────

@app.route("/admin/sync-sheets")
def sync_sheets():
    if not session.get("admin"): return redirect(url_for("admin"))
    if not GOOGLE_SHEET_ID or not os.path.exists(CREDENTIALS_FILE):
        flash("Google Sheets no configurado. Completá GOOGLE_SHEET_ID y credentials.json.")
        return redirect(url_for("admin"))
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc    = gspread.authorize(creds)
        sh    = gc.open_by_key(GOOGLE_SHEET_ID)

        try:    ws_t = sh.worksheet("Tabla")
        except: ws_t = sh.add_worksheet("Tabla", 100, 10)
        trows = fetchall(db_execute("""
            SELECT nombre, COUNT(*) jugados,
                   SUM(CASE WHEN puntos=3 THEN 1 ELSE 0 END) exactos,
                   SUM(CASE WHEN puntos=1 THEN 1 ELSE 0 END) resultados,
                   COALESCE(SUM(puntos),0) total
            FROM pronosticos WHERE puntos IS NOT NULL
            GROUP BY nombre ORDER BY total DESC, exactos DESC
        """))
        ws_t.clear()
        ws_t.append_row(["#","Nombre","Puntos","Exactos","Resultados","Jugados"])
        for i, r in enumerate(trows, 1):
            ws_t.append_row([i, r["nombre"], r["total"],
                              r["exactos"], r["resultados"], r["jugados"]])

        try:    ws_p = sh.worksheet("Pronósticos")
        except: ws_p = sh.add_worksheet("Pronósticos", 1000, 10)
        prons = fetchall(db_execute("""
            SELECT p.nombre, pa.equipo_local, pa.equipo_visit, pa.fase,
                   p.goles_local, p.goles_visit,
                   pa.goles_local real_l, pa.goles_visit real_v, p.puntos
            FROM pronosticos p JOIN partidos pa ON pa.id=p.partido_id
            ORDER BY p.nombre, pa.fecha, pa.id
        """))
        ws_p.clear()
        ws_p.append_row(["Nombre","Local","Visitante","Fase",
                          "Pred.L","Pred.V","Real.L","Real.V","Puntos"])
        for r in prons:
            ws_p.append_row([r.get(k) for k in
                              ["nombre","equipo_local","equipo_visit","fase",
                               "goles_local","goles_visit","real_l","real_v","puntos"]])
        flash("✅ Sincronizado con Google Sheets correctamente.")
    except Exception as e:
        flash(f"Error al sincronizar: {e}")
    return redirect(url_for("admin"))


@app.route("/admin/sync-resultados")
def sync_resultados():
    if not session.get("admin"): return redirect(url_for("admin"))
    if not FOOTBALL_DATA_KEY:
        flash("Configurá la variable FOOTBALL_DATA_KEY en Render para usar esta función.")
        return redirect(url_for("admin"))
    msg = _do_sync_resultados()
    if msg:
        flash(msg)
    return redirect(url_for("admin"))


@app.route("/admin/borrar-usuario/<nombre>", methods=["POST"])
def borrar_usuario(nombre):
    if not session.get("admin"): return redirect(url_for("admin"))
    p = placeholder()
    db_execute(f"DELETE FROM pronosticos WHERE nombre={p}", (nombre,))
    db_commit()
    flash(f"Usuario '{nombre}' eliminado correctamente.")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    print("Prode disponible en:  http://localhost:5000")
    print("Tabla de posiciones:  http://localhost:5000/tabla")
    print("Panel admin en:       http://localhost:5000/admin")
    app.run(debug=True, port=5000)

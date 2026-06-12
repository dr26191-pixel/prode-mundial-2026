import os
import csv
import io
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, g, flash, session, send_file)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "prode-mundial-2026")

BANDERAS = {
    "Argentina": "🇦🇷", "Argelia": "🇩🇿", "Australia": "🇦🇺", "Austria": "🇦🇹",
    "Arabia Saudita": "🇸🇦", "Alemania": "🇩🇪", "Bélgica": "🇧🇪", "Bosnia": "🇧🇦",
    "Brasil": "🇧🇷", "Canadá": "🇨🇦", "Cabo Verde": "🇨🇻", "Colombia": "🇨🇴",
    "Corea del Sur": "🇰🇷", "Costa de Marfil": "🇨🇮", "Croacia": "🇭🇷",
    "Curazao": "🇨🇼", "Ecuador": "🇪🇨", "EE.UU.": "🇺🇸", "Egipto": "🇪🇬",
    "Escocia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "España": "🇪🇸", "Francia": "🇫🇷", "Ghana": "🇬🇭",
    "Haití": "🇭🇹", "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Irak": "🇮🇶", "Irán": "🇮🇷",
    "Japón": "🇯🇵", "Jordania": "🇯🇴", "Marruecos": "🇲🇦", "México": "🇲🇽",
    "Nueva Zelanda": "🇳🇿", "Noruega": "🇳🇴", "Países Bajos": "🇳🇱",
    "Panamá": "🇵🇦", "Paraguay": "🇵🇾", "Portugal": "🇵🇹", "Qatar": "🇶🇦",
    "Rep. Checa": "🇨🇿", "República Checa": "🇨🇿", "Rep. Dem. Congo": "🇨🇩",
    "Senegal": "🇸🇳", "Sudáfrica": "🇿🇦", "Suecia": "🇸🇪", "Suiza": "🇨🇭",
    "Túnez": "🇹🇳", "Turquía": "🇹🇷", "Uruguay": "🇺🇾", "Uzbekistán": "🇺🇿",
}
app.jinja_env.globals["banderas"] = BANDERAS

ADMIN_PASSWORD  = os.environ.get("ADMIN_PASSWORD", "gipa2026")
DATABASE_URL    = os.environ.get("DATABASE_URL")   # Render lo setea automáticamente

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
                goles_visit    INTEGER
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
        """)
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
    cur = db_execute("SELECT * FROM partidos ORDER BY fecha, id")
    partidos = fetchall(cur)
    return render_template("index.html", partidos=partidos)

@app.route("/pronostico", methods=["POST"])
def pronostico():
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("Ingresá tu nombre para guardar los pronósticos.")
        return redirect(url_for("index"))

    p = placeholder()
    for key in request.form:
        if not key.startswith("local_"):
            continue
        pid = int(key.split("_", 1)[1])
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
    return render_template("mis_pronosticos.html",
                           nombre=nombre, partidos=partidos, pronosticos=pron)

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
    return render_template("tabla.html", tabla=rows)

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
    ver_todos = request.args.get("todos") == "1"
    hoy  = datetime.now()
    hoy_ord = hoy.month * 100 + hoy.day

    todos_partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))

    if ver_todos:
        partidos = todos_partidos
    else:
        partidos = [p for p in todos_partidos if _fecha_ord(p.get("fecha") or "") <= hoy_ord]

    nombres  = [r["nombre"] for r in fetchall(db_execute(
        "SELECT DISTINCT nombre FROM pronosticos ORDER BY nombre"))]
    p = placeholder()
    prons = {}
    for n in nombres:
        prons[n] = {r["partido_id"]: r for r in fetchall(
            db_execute(f"SELECT * FROM pronosticos WHERE nombre={p}", (n,)))}
    return render_template("todos.html",
                           partidos=partidos, nombres=nombres, pronosticos=prons,
                           ver_todos=ver_todos, total_partidos=len(todos_partidos))

# ── Admin ─────────────────────────────────────────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            flash("Contraseña incorrecta.")
    if not session.get("admin"):
        return render_template("admin_login.html")
    partidos = fetchall(db_execute("SELECT * FROM partidos ORDER BY fecha, id"))
    return render_template("admin.html", partidos=partidos)

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

@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

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


init_db()

if __name__ == "__main__":
    print("Prode disponible en:  http://localhost:5000")
    print("Tabla de posiciones:  http://localhost:5000/tabla")
    print("Panel admin en:       http://localhost:5000/admin")
    app.run(debug=True, port=5000)

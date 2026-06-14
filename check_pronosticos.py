#!/usr/bin/env python3
"""
check_pronosticos.py — Diagnóstico de integridad de pronósticos.

Chequea:
  1. Cantidad de pronósticos por usuario
  2. Duplicados (nombre, partido_id) — no debería haber ninguno
  3. Pronósticos con el mismo score en el mismo partido para varios usuarios
     (posible indicio de copia, aunque puede ser coincidencia)
  4. Constraint UNIQUE real en la tabla

Ejecutar: python check_pronosticos.py
"""
import os
DATABASE_URL = os.environ.get("DATABASE_URL")

def run():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        print("=" * 60)
        print("1. PRONÓSTICOS POR USUARIO")
        print("=" * 60)
        cur.execute("""
            SELECT nombre, COUNT(*) AS total,
                   COUNT(puntos) AS con_puntos
            FROM pronosticos
            GROUP BY nombre
            ORDER BY nombre
        """)
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]} pronósticos ({r[2]} con puntos calculados)")

        print("\n" + "=" * 60)
        print("2. DUPLICADOS (nombre, partido_id) — debería dar 0")
        print("=" * 60)
        cur.execute("""
            SELECT nombre, partido_id, COUNT(*) AS cant
            FROM pronosticos
            GROUP BY nombre, partido_id
            HAVING COUNT(*) > 1
        """)
        dups = cur.fetchall()
        if dups:
            print(f"  ⚠️  ENCONTRADOS {len(dups)} duplicados:")
            for r in dups:
                print(f"     {r[0]} | partido {r[1]} | {r[2]} veces")
        else:
            print("  ✅ Sin duplicados")

        print("\n" + "=" * 60)
        print("3. PARTIDOS CON TODOS LOS USUARIOS EN EL MISMO SCORE")
        print("   (sospechoso si hay 3+ usuarios con exactamente el mismo pronóstico)")
        print("=" * 60)
        cur.execute("""
            SELECT partido_id, goles_local, goles_visit,
                   COUNT(DISTINCT nombre) AS usuarios,
                   STRING_AGG(nombre, ', ' ORDER BY nombre) AS names
            FROM pronosticos
            GROUP BY partido_id, goles_local, goles_visit
            HAVING COUNT(DISTINCT nombre) >= 3
            ORDER BY usuarios DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        if rows:
            # Get partido info
            for r in rows:
                cur.execute("SELECT equipo_local, equipo_visit FROM partidos WHERE id=%s", (r[0],))
                p = cur.fetchone()
                match = f"{p[0]} vs {p[1]}" if p else f"partido {r[0]}"
                print(f"  {match}: {r[1]}-{r[2]} → {r[3]} usuarios: {r[4]}")
        else:
            print("  ✅ Ningún caso con 3+ usuarios con idéntico score")

        print("\n" + "=" * 60)
        print("4. CONSTRAINT UNIQUE EN LA TABLA")
        print("=" * 60)
        cur.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'pronosticos'
        """)
        for r in cur.fetchall():
            print(f"  {r[1]}: {r[0]}")

        print("\n" + "=" * 60)
        print("5. ÚLTIMAS 10 INSERCIONES")
        print("=" * 60)
        cur.execute("""
            SELECT nombre, partido_id, goles_local, goles_visit, timestamp
            FROM pronosticos
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        for r in cur.fetchall():
            print(f"  {r[4]} | {r[0]} | partido {r[1]}: {r[2]}-{r[3]}")

        conn.close()

    else:
        import sqlite3
        DB = os.path.join(os.path.dirname(__file__), "prode.db")
        conn = sqlite3.connect(DB)

        print("=" * 60)
        print("1. PRONÓSTICOS POR USUARIO")
        print("=" * 60)
        for r in conn.execute("""
            SELECT nombre, COUNT(*) AS total, COUNT(puntos) AS con_puntos
            FROM pronosticos GROUP BY nombre ORDER BY nombre
        """):
            print(f"  {r[0]}: {r[1]} pronósticos ({r[2]} con puntos)")

        print("\n2. DUPLICADOS")
        dups = list(conn.execute("""
            SELECT nombre, partido_id, COUNT(*) FROM pronosticos
            GROUP BY nombre, partido_id HAVING COUNT(*) > 1
        """))
        print("  ✅ Sin duplicados" if not dups else f"  ⚠️ {len(dups)} duplicados encontrados")
        for r in dups:
            print(f"     {r[0]} | partido {r[1]} | {r[2]} veces")

        print("\n3. PARTIDOS CON 3+ USUARIOS CON MISMO SCORE")
        for r in conn.execute("""
            SELECT partido_id, goles_local, goles_visit, COUNT(DISTINCT nombre)
            FROM pronosticos
            GROUP BY partido_id, goles_local, goles_visit
            HAVING COUNT(DISTINCT nombre) >= 3
        """):
            p = conn.execute("SELECT equipo_local, equipo_visit FROM partidos WHERE id=?", (r[0],)).fetchone()
            print(f"  {p[0] if p else r[0]} vs {p[1] if p else '?'}: {r[1]}-{r[2]} ({r[3]} usuarios)")

        print("\n4. ÚLTIMAS 10 INSERCIONES")
        for r in conn.execute("""
            SELECT nombre, partido_id, goles_local, goles_visit, timestamp
            FROM pronosticos ORDER BY timestamp DESC LIMIT 10
        """):
            print(f"  {r[4]} | {r[0]} | partido {r[1]}: {r[2]}-{r[3]}")

        conn.close()

if __name__ == "__main__":
    run()

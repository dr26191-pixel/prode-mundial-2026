#!/usr/bin/env python3
"""Diagnóstico: muestra lote y fecha de los partidos en cuestión."""
import os
DATABASE_URL = os.environ.get("DATABASE_URL")

BUSCAR = [("Ghana", "Panamá"), ("Uzbekistán", "Colombia")]

def run():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for local, visit in BUSCAR:
            cur.execute(
                "SELECT id, equipo_local, equipo_visit, fecha, lote FROM partidos "
                "WHERE equipo_local=%s AND equipo_visit=%s", (local, visit))
            row = cur.fetchone()
            print(f"{local} vs {visit}: {row}")
        # También mostrar cuántos partidos hay por lote
        cur.execute("SELECT lote, COUNT(*) FROM partidos GROUP BY lote ORDER BY lote")
        print("\nPartidos por lote:")
        for r in cur.fetchall():
            print(f"  Lote {r[0]}: {r[1]} partidos")
        conn.close()
    else:
        import sqlite3
        DB = os.path.join(os.path.dirname(__file__), "prode.db")
        conn = sqlite3.connect(DB)
        for local, visit in BUSCAR:
            cur = conn.execute(
                "SELECT id, equipo_local, equipo_visit, fecha, lote FROM partidos "
                "WHERE equipo_local=? AND equipo_visit=?", (local, visit))
            print(f"{local} vs {visit}: {cur.fetchone()}")
        print("\nPartidos por lote:")
        for r in conn.execute("SELECT lote, COUNT(*) FROM partidos GROUP BY lote ORDER BY lote"):
            print(f"  Lote {r[0]}: {r[1]} partidos")
        conn.close()

if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
add_missing_matches.py — Agrega los 2 partidos faltantes de Jornada 1.

Ghana vs Panamá    (17/06 Grupo L)
Uzbekistán vs Colombia (17/06 Grupo K)

No toca datos existentes ni pronósticos de usuarios.
Ejecutar en Render Shell: python add_missing_matches.py
"""
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

NUEVOS = [
    ("Grupos", "Ghana",      "Panamá",    "17/06 Grupo L", 1),
    ("Grupos", "Uzbekistán", "Colombia",  "17/06 Grupo K", 1),
]

def run():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        added = 0
        for fase, local, visit, fecha, lote in NUEVOS:
            cur.execute(
                "SELECT id FROM partidos WHERE equipo_local=%s AND equipo_visit=%s",
                (local, visit))
            if cur.fetchone():
                print(f"  YA EXISTE: {local} vs {visit} — saltando.")
                continue
            cur.execute(
                "INSERT INTO partidos (fase, equipo_local, equipo_visit, fecha, lote) "
                "VALUES (%s,%s,%s,%s,%s)",
                (fase, local, visit, fecha, lote))
            print(f"  AGREGADO: {local} vs {visit} ({fecha}, lote {lote})")
            added += 1
        conn.commit()
        conn.close()
        print(f"\nListo: {added} partido(s) agregado(s).")
    else:
        import sqlite3
        DB = os.path.join(os.path.dirname(__file__), "prode.db")
        conn = sqlite3.connect(DB)
        added = 0
        for fase, local, visit, fecha, lote in NUEVOS:
            cur = conn.execute(
                "SELECT id FROM partidos WHERE equipo_local=? AND equipo_visit=?",
                (local, visit))
            if cur.fetchone():
                print(f"  YA EXISTE: {local} vs {visit} — saltando.")
                continue
            conn.execute(
                "INSERT INTO partidos (fase, equipo_local, equipo_visit, fecha, lote) "
                "VALUES (?,?,?,?,?)",
                (fase, local, visit, fecha, lote))
            print(f"  AGREGADO: {local} vs {visit} ({fecha}, lote {lote})")
            added += 1
        conn.commit()
        conn.close()
        print(f"\nListo: {added} partido(s) agregado(s).")

if __name__ == "__main__":
    run()

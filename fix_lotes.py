#!/usr/bin/env python3
"""
fix_lotes.py — Corrige los lotes mal asignados por fechas incorrectas.

Problema detectado:
  - Ghana vs Panamá     tiene '18/06 Grupo L' → lote 2  (debería ser '17/06', lote 1)
  - Uzbekistán vs Colombia tiene '18/06 Grupo K' → lote 2  (debería ser '17/06', lote 1)
  - Lote 3 tiene 26 partidos (2 de Jornada 2 cayeron ahí por fecha incorrecta)

Este script:
  1. Muestra todos los partidos fuera de rango en cada lote
  2. Corrige fecha y lote de los que están mal
  3. No toca pronósticos de usuarios (se referencian por partido_id)

Ejecutar: python fix_lotes.py
"""
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# Rangos de fecha_ord correctos
# lote 1: dia*1 + mes*100 → ≤617 (hasta 17/06)
# lote 2: 618-623 (18/06–23/06)
# lote 3: 624-627 (24/06–27/06)

def fecha_ord(s):
    try:
        d, m = s.split()[0].split("/")
        return int(m) * 100 + int(d)
    except Exception:
        return 9999

def lote_correcto(fecha_str):
    o = fecha_ord(fecha_str)
    if o <= 617: return 1
    if o <= 623: return 2
    return 3

def run():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Correcciones fijas conocidas
        FIXES = [
            ("Ghana",      "Panamá",    "17/06 Grupo L", 1),
            ("Uzbekistán", "Colombia",  "17/06 Grupo K", 1),
        ]
        fixed = 0
        for local, visit, nueva_fecha, nuevo_lote in FIXES:
            cur.execute(
                "UPDATE partidos SET fecha=%s, lote=%s "
                "WHERE equipo_local=%s AND equipo_visit=%s",
                (nueva_fecha, nuevo_lote, local, visit))
            if cur.rowcount:
                print(f"  CORREGIDO: {local} vs {visit} → {nueva_fecha}, lote {nuevo_lote}")
                fixed += 1

        # Detectar y corregir cualquier otro partido con lote incorrecto según su fecha
        cur.execute("SELECT id, equipo_local, equipo_visit, fecha, lote FROM partidos WHERE lote <= 3")
        rows = cur.fetchall()
        for pid, local, visit, fecha, lote_actual in rows:
            if fecha is None:
                continue
            esperado = lote_correcto(fecha)
            if esperado != lote_actual:
                cur.execute("UPDATE partidos SET lote=%s WHERE id=%s", (esperado, pid))
                print(f"  LOTE CORREGIDO: {local} vs {visit} ({fecha}): lote {lote_actual} → {esperado}")
                fixed += 1

        conn.commit()

        # Resumen final
        cur.execute("SELECT lote, COUNT(*) FROM partidos GROUP BY lote ORDER BY lote")
        print("\nPartidos por lote (después de la corrección):")
        for r in cur.fetchall():
            print(f"  Lote {r[0]}: {r[1]} partidos")

        conn.close()
        print(f"\nTotal corregidos: {fixed}")

    else:
        import sqlite3
        DB = os.path.join(os.path.dirname(__file__), "prode.db")
        conn = sqlite3.connect(DB)

        FIXES = [
            ("Ghana",      "Panamá",    "17/06 Grupo L", 1),
            ("Uzbekistán", "Colombia",  "17/06 Grupo K", 1),
        ]
        fixed = 0
        for local, visit, nueva_fecha, nuevo_lote in FIXES:
            cur = conn.execute(
                "UPDATE partidos SET fecha=?, lote=? "
                "WHERE equipo_local=? AND equipo_visit=?",
                (nueva_fecha, nuevo_lote, local, visit))
            if cur.rowcount:
                print(f"  CORREGIDO: {local} vs {visit} → {nueva_fecha}, lote {nuevo_lote}")
                fixed += 1

        rows = list(conn.execute(
            "SELECT id, equipo_local, equipo_visit, fecha, lote FROM partidos WHERE lote <= 3"))
        for pid, local, visit, fecha, lote_actual in rows:
            if fecha is None:
                continue
            esperado = lote_correcto(fecha)
            if esperado != lote_actual:
                conn.execute("UPDATE partidos SET lote=? WHERE id=?", (esperado, pid))
                print(f"  LOTE CORREGIDO: {local} vs {visit} ({fecha}): lote {lote_actual} → {esperado}")
                fixed += 1

        conn.commit()

        print("\nPartidos por lote (después de la corrección):")
        for r in conn.execute("SELECT lote, COUNT(*) FROM partidos GROUP BY lote ORDER BY lote"):
            print(f"  Lote {r[0]}: {r[1]} partidos")
        conn.close()
        print(f"\nTotal corregidos: {fixed}")

if __name__ == "__main__":
    run()

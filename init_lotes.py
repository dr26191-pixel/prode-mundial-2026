#!/usr/bin/env python3
"""
init_lotes.py — Ejecutar UNA VEZ para inicializar el sistema de lotes.

Asigna lote 1/2/3 a los partidos de grupos según su fecha,
e inserta las definiciones de los 8 lotes en la tabla `lotes`.

Usar en Render Shell:
    python init_lotes.py
"""
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# Definición de los 8 lotes
LOTES_DEF = [
    (1, "Jornada 1 – Grupos",          "11/06 – 17/06", 1),  # publicado de entrada
    (2, "Jornada 2 – Grupos",          "18/06 – 23/06", 0),
    (3, "Jornada 3 – Grupos",          "24/06 – 27/06", 0),
    (4, "Dieciseisavos de Final",          "28/06 – 03/07", 0),
    (5, "Octavos de Final",                "04/07 – 07/07", 0),
    (6, "Cuartos de Final",                "09/07 – 11/07", 0),
    (7, "Semifinales + Tercer puesto",     "14/07 – 18/07", 0),
    (8, "Final",                           "19/07",              0),
]


def fecha_a_lote(fecha_str):
    """Asigna lote según fecha guardada ('14/06 Grupo A' → 614).
    Jornada 1: ≤617, Jornada 2: ≤623, Jornada 3: ≤627, resto: 1 (fallback).
    """
    try:
        parte = (fecha_str or "").split()[0]   # '14/06'
        d, m = parte.split("/")
        ord_ = int(m) * 100 + int(d)
        if ord_ <= 617:
            return 1
        elif ord_ <= 623:
            return 2
        elif ord_ <= 9999:
            return 3
    except Exception:
        pass
    return 1


def run():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Agregar columna lote si no existe
        cur.execute(
            "ALTER TABLE partidos ADD COLUMN IF NOT EXISTS lote INTEGER DEFAULT 1"
        )

        # Crear tabla lotes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lotes (
                numero    INTEGER PRIMARY KEY,
                nombre    TEXT    NOT NULL,
                fechas    TEXT,
                publicado INTEGER DEFAULT 0
            )
        """)

        # Insertar/actualizar definiciones de lotes
        for num, nombre, fechas, publicado in LOTES_DEF:
            cur.execute("""
                INSERT INTO lotes (numero, nombre, fechas, publicado)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (numero) DO UPDATE SET
                    nombre=EXCLUDED.nombre, fechas=EXCLUDED.fechas
            """, (num, nombre, fechas, publicado))

        # Asignar lote a cada partido según su fecha
        cur.execute("SELECT id, fecha FROM partidos")
        rows = cur.fetchall()
        updated = 0
        for pid, fecha in rows:
            lote = fecha_a_lote(fecha or "")
            cur.execute("UPDATE partidos SET lote=%s WHERE id=%s", (lote, pid))
            updated += 1

        conn.commit()
        conn.close()
        print(f"PostgreSQL OK: {updated} partido(s) con lote asignado, "
              f"{len(LOTES_DEF)} lotes definidos.")

    else:
        import sqlite3
        DB = os.path.join(os.path.dirname(__file__), "prode.db")
        conn = sqlite3.connect(DB)

        # Agregar columna lote si no existe
        try:
            conn.execute("ALTER TABLE partidos ADD COLUMN lote INTEGER DEFAULT 1")
            conn.commit()
        except Exception:
            pass  # ya existe

        # Crear tabla lotes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lotes (
                numero    INTEGER PRIMARY KEY,
                nombre    TEXT    NOT NULL,
                fechas    TEXT,
                publicado INTEGER DEFAULT 0
            )
        """)
        conn.commit()

        # Insertar/actualizar definiciones de lotes
        for num, nombre, fechas, publicado in LOTES_DEF:
            conn.execute("""
                INSERT INTO lotes (numero, nombre, fechas, publicado)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (numero) DO UPDATE SET
                    nombre=excluded.nombre, fechas=excluded.fechas
            """, (num, nombre, fechas, publicado))
        conn.commit()

        # Asignar lote a cada partido según su fecha
        cur = conn.cursor()
        cur.execute("SELECT id, fecha FROM partidos")
        rows = cur.fetchall()
        updated = 0
        for pid, fecha in rows:
            lote = fecha_a_lote(fecha or "")
            conn.execute("UPDATE partidos SET lote=? WHERE id=?", (lote, pid))
            updated += 1

        conn.commit()
        conn.close()
        print(f"SQLite OK: {updated} partido(s) con lote asignado, "
              f"{len(LOTES_DEF)} lotes definidos.")


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""Importador simple de tareas a Leantime usando el bridge HTTP.

Uso:
  python tools/import_tasks.py --file tareas.csv --url http://localhost:8000

CSV esperado (cabecera): title,description,project_id (project_id opcional)
También se puede exportar desde Excel a CSV (Archivo -> Guardar como -> CSV UTF-8)
"""
import argparse
import csv
import sys
from pathlib import Path

import httpx


def post_task(client: httpx.Client, base_url: str, title: str, description: str | None = None, project_id: int | None = None):
    payload = {"title": title}
    if description:
        payload["description"] = description
    if project_id is not None:
        payload["project_id"] = project_id
    r = client.post(f"{base_url.rstrip('/')}/tasks", json=payload, timeout=30.0)
    try:
        j = r.json()
    except Exception:
        j = None
    return r.status_code, j or r.text


def main():
    p = argparse.ArgumentParser(prog="import_tasks.py", description="Importa tareas desde CSV al bridge de Leantime")
    p.add_argument("--file", "-f", required=True, help="Ruta al CSV de tareas")
    p.add_argument("--url", "-u", default="http://localhost:8000", help="URL base del bridge (por defecto http://localhost:8000)")
    p.add_argument("--delimiter", "-d", default=",", help="Delimitador CSV (por defecto ,)")
    p.add_argument("--encoding", default="utf-8", help="Codificación del CSV (por defecto utf-8)")
    p.add_argument("--project", "-p", type=int, help="Project ID por defecto (sobrescribe la columna project_id si existe)")
    args = p.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print("ERROR: archivo no encontrado:", csv_path, file=sys.stderr)
        sys.exit(2)

    client = httpx.Client()
    total = 0
    success = 0
    errors = 0

    with csv_path.open("r", encoding=args.encoding, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=args.delimiter)
        for row in reader:
            total += 1
            title = (row.get("title") or row.get("headline") or "").strip()
            description = (row.get("description") or row.get("desc") or "").strip()
            project_id = None
            if args.project:
                project_id = args.project
            else:
                pid = (row.get("project_id") or row.get("project") or "").strip()
                if pid:
                    try:
                        project_id = int(pid)
                    except Exception:
                        project_id = None

            if not title:
                print(f"Skipp: fila {total} sin 'title' (se ignora)")
                errors += 1
                continue

            code, resp = post_task(client, args.url, title=title, description=description or None, project_id=project_id)
            if 200 <= code < 300:
                success += 1
                print(f"OK [{code}]: '{title}' -> {resp}")
            else:
                errors += 1
                print(f"ERR [{code}]: '{title}' -> {resp}")

    print(f"\nSummary: total={total} success={success} errors={errors}")


if __name__ == "__main__":
    main()

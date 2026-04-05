#!/usr/bin/env python3
"""Importador directo a Leantime (JSON-RPC vía /api/jsonrpc).

Usa el cliente interno `src.leantime_client.LeantimeClient` para crear tareas directamente
en la instancia de Leantime (por ejemplo `http://localhost:8080`).

Ejemplo:
  python tools/import_tasks_leantime.py --file tareas.csv --url http://localhost:8080 --token REPLACE_WITH_LEANTIME_TOKEN --project 1

CSV esperado (cabecera): title,description,project_id (project_id opcional)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

from src.leantime_client import LeantimeClient, LeantimeAPIError


def main() -> None:
    p = argparse.ArgumentParser(description="Importa tareas directamente a Leantime via JSON-RPC")
    p.add_argument("--file", "-f", required=True, help="CSV con tareas")
    p.add_argument("--url", "-u", required=True, help="URL base de Leantime (ej. http://localhost:8080)")
    p.add_argument("--token", "-t", required=True, help="API token de Leantime (x-api-key)")
    p.add_argument("--project", "-p", type=int, help="Project ID por defecto (si no está en CSV)")
    p.add_argument("--delimiter", "-d", default=",", help="Delimitador CSV (por defecto ,)")
    args = p.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print("ERROR: archivo no encontrado:", csv_path, file=sys.stderr)
        sys.exit(2)

    lc = LeantimeClient(base_url=args.url, api_token=args.token, token_header="x-api-key", token_prefix="")

    total = 0
    ok = 0
    errs = 0

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=args.delimiter)
        for row in reader:
            total += 1
            title = (row.get("title") or row.get("headline") or "").strip()
            description = (row.get("description") or row.get("desc") or "").strip() or None
            project_id: Optional[int] = None
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
                print(f"SKIP fila {total}: falta 'title'")
                errs += 1
                continue

            try:
                created = lc.create_task(title=title, description=description, project_id=project_id)
                print(f"CREATED id={created.get('id')} title='{title}'")
                ok += 1
            except LeantimeAPIError as e:
                print(f"ERROR fila {total}: {e}")
                errs += 1

    print(f"\nResumen: total={total} creadas={ok} errores={errs}")


if __name__ == "__main__":
    main()

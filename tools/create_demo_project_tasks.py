#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import json
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.leantime_client import LeantimeClient


def load_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def main():
    env = load_env(Path(__file__).resolve().parents[1] / '.env')
    leantime_url = env.get('LEANTIME_URL', 'http://localhost:8080')
    leantime_token = env.get('LEANTIME_TOKEN')
    token_header = env.get('LEANTIME_TOKEN_HEADER', 'Authorization')
    token_prefix = env.get('LEANTIME_TOKEN_PREFIX', '')
    default_project = env.get('LEANTIME_DEFAULT_PROJECT_ID')

    if not leantime_token:
        print('ERROR: LEANTIME_TOKEN no encontrado en .env')
        sys.exit(2)

    client = LeantimeClient(base_url=leantime_url, api_token=leantime_token, token_header=token_header, token_prefix=token_prefix)

    # Intentar conexión; si falla y la URL usa host 'leantime', intentar 'localhost' como fallback
    try:
        client.test_connection()
    except Exception:
        if 'leantime' in leantime_url:
            alt = leantime_url.replace('leantime', 'localhost')
            print('Conexión inicial falló; intentando fallback a', alt)
            client = LeantimeClient(base_url=alt, api_token=leantime_token, token_header=token_header, token_prefix=token_prefix)
            try:
                client.test_connection()
                leantime_url = alt
            except Exception as exc:
                print('No fue posible conectar a Leantime en ninguna URL:', exc)
                # seguimos y los intentos de creación reportarán el error

    project_id = None
    if default_project:
        try:
            project_id = int(default_project)
        except Exception:
            project_id = None

    if project_id is None:
        projects = client.get_projects()
        if not projects:
            print('ERROR: No hay proyectos disponibles para el token de Leantime')
            sys.exit(2)
        project_id = projects[0].get('id')

    print('Usando proyecto id=', project_id)

    # Definir tareas de ejemplo (ordenadas)
    tasks = [
        ("Definir alcance del MVP", "Reunir requisitos y alcance del MVP de CRM."),
        ("Diseñar modelo de datos", "Especificar entidades: clientes, contactos, interacciones."),
        ("Implementar API básica", "Crear endpoints para crear/leer clientes y contactos."),
        ("Interfaz de captura", "Formulario para registrar clientes y agendar seguimientos."),
        ("Pruebas iniciales", "Tests básicos de integración y flujo de altas."),
        ("Despliegue en staging", "Preparar entorno y desplegar para pruebas de usuario."),
    ]

    # Asignar fechas y horas: hoy a partir de mañana 09:00, una tarea cada día a distintas horas
    start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    created = []
    for i, (title, desc) in enumerate(tasks):
        dt = start + timedelta(days=i)
        # alternar horas para variar: 09:00, 11:00, 14:00, 16:00...
        hours = [9, 11, 14, 16, 10, 15]
        hour = hours[i % len(hours)]
        dt = dt.replace(hour=hour)
        due_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        try:
            created_task = client.create_task(title=title, description=desc, project_id=project_id, due_date=due_str, fetch_created=False)
            print(f"CREATED id={created_task.get('id')} title='{title}' due={due_str}")
            created.append(created_task)
        except Exception as exc:
            print(f"ERROR creating '{title}': {exc}")

    print('\nResumen: creadas=', len(created))
    print(json.dumps(created, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

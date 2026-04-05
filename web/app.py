from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Añadir la raíz del repo al path para poder importar `src`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.leantime_client import LeantimeClient, LeantimeConfigurationError, LeantimeAPIError  # noqa: E402
from src.ai_client import AIClient, AIConfigurationError, AIRequestError  # noqa: E402
from .scheduler import RecurrenceScheduler


def _extract_json_object(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("La IA devolvio una respuesta vacia")

    if "```" in raw:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("La IA no devolvio un objeto JSON valido")
    return parsed


def _build_planning_prompt(
    brief: str,
    project_name: str | None,
    existing_tasks: list[dict[str, Any]],
    max_tasks: int,
) -> tuple[str, str]:
    system = (
        "Eres un analista senior de producto y project manager. "
        "Tu trabajo es convertir ideas de negocio en tareas ejecutables para Leantime. "
        "Responde siempre en espanol y en JSON valido, sin markdown ni texto extra."
    )

    existing_text = "\n".join(
        f"- {task.get('headline') or task.get('title')}: {task.get('description') or 'sin descripcion'}"
        for task in existing_tasks[:20]
    ) or "- No hay tareas previas registradas"

    user = (
        f"Proyecto: {project_name or 'sin nombre'}\n"
        f"Objetivo o idea a desarrollar:\n{brief}\n\n"
        "Tareas ya existentes en Leantime para evitar duplicados:\n"
        f"{existing_text}\n\n"
        f"Genera un plan de hasta {max_tasks} tareas nuevas, concretas y accionables. "
        "No repitas tareas ya existentes. Si hace falta, agrupa por fases.\n\n"
        "Devuelve exactamente este JSON:\n"
        '{"resumen":"...","tasks":[{"title":"...","description":"...","priority":"alta|media|baja"}]}'
    )
    return system, user


def _normalize_generated_tasks(payload: dict[str, Any]) -> list[dict[str, str]]:
    tasks = payload.get("tasks") or payload.get("tareas") or []
    if not isinstance(tasks, list):
        raise ValueError("La IA no devolvio una lista de tareas")

    normalized: list[dict[str, str]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        title = str(task.get("title") or task.get("titulo") or task.get("headline") or "").strip()
        description = str(task.get("description") or task.get("descripcion") or "").strip()
        priority = str(task.get("priority") or task.get("prioridad") or "media").strip().lower()
        if not title:
            continue
        if priority not in {"alta", "media", "baja", "high", "medium", "low"}:
            priority = "media"
        normalized.append({"title": title, "description": description, "priority": priority})
    return normalized


def _build_chat_system_prompt() -> str:
    leantime_ready = bool(leantime_client and leantime_client.is_configured)
    ai_ready = bool(ai_client and ai_client.is_configured)
    default_project = env("LEANTIME_DEFAULT_PROJECT_ID") or "no definido"

    return (
        "Eres el asistente integrado de Leantime Copilot dentro de esta aplicacion web. "
        "No hables como un modelo generico ni digas que no puedes conectarte a servicios externos si el bridge ya esta conectado. "
        "Responde siempre en espanol, de forma concreta y orientada a accion. "
        "Tu contexto real es este: "
        f"Leantime conectado={'si' if leantime_ready else 'no'}, "
        f"IA conectada={'si' if ai_ready else 'no'}, "
        f"proyecto por defecto={default_project}. "
        "Capacidades reales disponibles en esta app: responder preguntas del proyecto, proponer tareas, "
        "crear una sola tarea con el boton 'Crear tarea' y generar varias tareas con el boton 'IA planifica y crea'. "
        "Si el usuario pregunta si ya estas conectado a Leantime, responde segun el estado real indicado arriba. "
        "Si el usuario quiere que se creen tareas, indicale con claridad que use el boton adecuado o que te pase el brief para planificarlo."
    )


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v is not None else default


app = FastAPI(title="Leantime MCP Web Bridge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]) 


# Configuracion desde variables de entorno
LEANTIME_URL = env("LEANTIME_URL", "http://localhost:8080")
LEANTIME_TOKEN = env("LEANTIME_TOKEN", None)
LEANTIME_API_BASE = env("LEANTIME_API_BASE", "")

# Token/header configurables para autenticacion con la API de Leantime
LEANTIME_TOKEN_HEADER = env("LEANTIME_TOKEN_HEADER", "Authorization")
LEANTIME_TOKEN_PREFIX = env("LEANTIME_TOKEN_PREFIX", "Bearer")

AI_BASE_URL = env("AI_BASE_URL", env("AI_BASE_URL", "http://localhost:11434/v1"))
AI_API_KEY = env("AI_API_KEY", env("AI_API_KEY", "ollama"))
AI_MODEL = env("AI_MODEL", env("AI_MODEL", "llama3.2:3b"))
AI_API_KEY_HEADER = env("AI_API_KEY_HEADER", "Authorization")


def build_leantime_base_url(leantime_url: str | None, api_base: str) -> str | None:
    if not leantime_url:
        return None
    return f"{leantime_url.rstrip('/')}/{api_base.strip('/')}" if api_base else leantime_url.rstrip('/')


try:
    leantime_client = LeantimeClient(
        build_leantime_base_url(LEANTIME_URL, LEANTIME_API_BASE),
        LEANTIME_TOKEN,
        token_header=LEANTIME_TOKEN_HEADER,
        token_prefix=LEANTIME_TOKEN_PREFIX,
    )
except Exception as exc:  # pragma: no cover - report on startup
    leantime_client = None  # type: ignore
    startup_error = str(exc)
else:
    startup_error = None

try:
    ai_client = AIClient(base_url=AI_BASE_URL, api_key=AI_API_KEY, model=AI_MODEL, api_key_header=AI_API_KEY_HEADER)
except Exception as exc:  # pragma: no cover
    ai_client = None  # type: ignore
    ai_startup_error = str(exc)
else:
    ai_startup_error = None


# Scheduler instance (initialized at startup)
recurrence_scheduler: RecurrenceScheduler | None = None


@app.get("/ping")
def ping() -> dict[str, Any]:
    return {"status": "ok", "leantime_configured": bool(leantime_client and leantime_client.is_configured), "ai_configured": bool(ai_client and ai_client.is_configured)}


@app.get("/projects")
def list_projects() -> Any:
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")
    try:
        return leantime_client.get_projects()
    except LeantimeConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/tasks")
def list_tasks(project_id: int | None = None, status: str | None = None) -> Any:
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")
    try:
        return leantime_client.get_tasks(project_id=project_id, status=status)
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/tasks")
def create_task(payload: dict) -> Any:
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="Falta campo 'title' en el cuerpo JSON")
    description = payload.get("description")
    project_id = payload.get("project_id")
    try:
        return leantime_client.create_task(title=title, description=description, project_id=project_id)
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/ai/describe")
def ai_describe(payload: dict) -> Any:
    if not ai_client:
        raise HTTPException(status_code=500, detail=f"AI client no inicializado: {ai_startup_error}")
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="Falta campo 'title' en el cuerpo JSON")
    system = payload.get("system_prompt", "Eres un asistente que genera descripciones breves y útiles para tareas de proyecto.")
    try:
        text = ai_client.chat(system_prompt=system, user_message=title, max_tokens=256, temperature=0.2)
        return {"description": text}
    except (AIConfigurationError, AIRequestError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/ai/chat")
def ai_chat(payload: dict) -> Any:
    if not ai_client:
        raise HTTPException(status_code=500, detail=f"AI client no inicializado: {ai_startup_error}")

    # Soporta 'messages' (lista) o 'message' (string)
    messages = payload.get("messages")
    if messages and isinstance(messages, list):
        system = None
        user_parts = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content")
            elif m.get("role") == "user":
                user_parts.append(m.get("content", ""))
        user_message = "\n".join(user_parts)
        system_prompt = system or payload.get("system_prompt", _build_chat_system_prompt())
    else:
        user_message = payload.get("message") or payload.get("user_message")
        if not user_message:
            raise HTTPException(status_code=400, detail="Falta campo 'message' o 'messages' en el cuerpo JSON")
        system_prompt = payload.get("system_prompt", _build_chat_system_prompt())

    max_tokens = int(payload.get("max_tokens", 512))
    temperature = float(payload.get("temperature", 0.2))

    try:
        text = ai_client.chat(system_prompt=system_prompt, user_message=user_message, max_tokens=max_tokens, temperature=temperature)
        return {"response": text}
    except (AIConfigurationError, AIRequestError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/ai/plan-and-create")
def ai_plan_and_create(payload: dict) -> Any:
    if not ai_client:
        raise HTTPException(status_code=500, detail=f"AI client no inicializado: {ai_startup_error}")
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")

    brief = (payload.get("brief") or payload.get("message") or "").strip()
    if not brief:
        raise HTTPException(status_code=400, detail="Falta campo 'brief' o 'message' en el cuerpo JSON")

    project_id = payload.get("project_id")
    if project_id is None:
        default_project = env("LEANTIME_DEFAULT_PROJECT_ID")
        if default_project:
            try:
                project_id = int(default_project)
            except ValueError:
                project_id = None
    max_tasks = int(payload.get("max_tasks", 10))
    max_tasks = max(1, min(25, max_tasks))

    try:
        project_name = None
        if project_id is None:
            projects = leantime_client.get_projects()
            first_project = projects[0] if projects else None
            if first_project:
                project_id = first_project.get("id")
                project_name = first_project.get("name") or first_project.get("title")

        existing_tasks = leantime_client.get_tasks(project_id=project_id)
        system_prompt, user_prompt = _build_planning_prompt(brief, project_name, existing_tasks, max_tasks)
        raw = ai_client.chat(system_prompt=system_prompt, user_message=user_prompt, max_tokens=1600, temperature=0.2)
        parsed = _extract_json_object(raw)
        generated_tasks = _normalize_generated_tasks(parsed)

        if not generated_tasks:
            return {
                "summary": parsed.get("resumen") or parsed.get("summary") or "La IA no genero tareas accionables.",
                "generated_count": 0,
                "created_count": 0,
                "tasks": [],
                "raw": raw,
            }

        created_tasks = []
        failed_tasks = []
        for task in generated_tasks:
            try:
                created = leantime_client.create_task(
                    title=task["title"],
                    description=task["description"],
                    project_id=project_id,
                    priority=task["priority"],
                    fetch_created=False,
                )
                created_tasks.append(created)
            except LeantimeAPIError as exc:
                failed_tasks.append({"task": task, "error": str(exc)})

        return {
            "summary": parsed.get("resumen") or parsed.get("summary") or "Plan generado por IA",
            "generated_count": len(generated_tasks),
            "created_count": len(created_tasks),
            "tasks": generated_tasks,
            "created": created_tasks,
            "failed": failed_tasks,
            "raw": raw,
        }
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except (AIConfigurationError, AIRequestError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/pomodoro/log")
def pomodoro_log(payload: dict) -> Any:
    """Registra una sesión de Pomodoro creando una tarea resumen en Leantime.

    Campos aceptados en el payload JSON:
    - duration_minutes: int (duración en minutos)
    - mode: str ("focus" o "break")
    - project_id: int (opcional)
    - note: str (opcional)
    """
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")

    duration = payload.get("duration_minutes")
    mode = payload.get("mode", "focus")
    project_id = payload.get("project_id")
    note = payload.get("note")

    if duration is None:
        raise HTTPException(status_code=400, detail="Falta campo 'duration_minutes' en el cuerpo JSON")

    try:
        title = f"Pomodoro: {int(duration)} min ({mode})"
        description = f"Registro automático de Pomodoro. Modo: {mode}. Duración: {int(duration)} minutos."
        if note:
            description += f"\n\nNota: {note}"

        # Usa proyecto por defecto si no se especifica
        if project_id is None:
            try:
                default_pid = int(env("LEANTIME_DEFAULT_PROJECT_ID") or 0)
            except Exception:
                default_pid = 0
            project_id = default_pid or None

        try:
            created = leantime_client.create_task(title=title, description=description, project_id=project_id)
            return {"created": created}
        except LeantimeAPIError:
            # Fallback: intentar la llamada JSON-RPC directa imitando create_task internals
            values = {"headline": title, "description": description, "type": "task"}
            if project_id is not None:
                values["projectId"] = project_id
            try:
                result = leantime_client._jsonrpc("leantime.rpc.tickets.addTicket", {"values": values})
                created_id = result[0] if isinstance(result, list) and result else None
                if not created_id:
                    raise LeantimeAPIError("La API de Leantime no devolvio el ID de la tarea creada (fallback).")
                created = leantime_client.get_task(int(created_id))
                return {"created": created}
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # pragma: no cover - otros errores inesperados
        raise HTTPException(status_code=500, detail=str(exc))


# Servir UI estática simple para chat en /static/chat.html
static_dir = ROOT / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Utilities for lightweight persistence (recurring jobs)
PLANNING_PATH = Path(env("PLANNING_STORAGE_PATH", "./.planning"))
PLANNING_PATH.mkdir(parents=True, exist_ok=True)
RECURRING_FILE = PLANNING_PATH / "recurring.json"
if not RECURRING_FILE.exists():
    RECURRING_FILE.write_text("[]", encoding="utf-8")


@app.post("/customfields/set")
def customfields_set(payload: dict) -> Any:
    """Setea un campo personalizado. Si `task_id` se pasa, actualiza la descripción de la tarea; si no, crea una nueva tarea."""
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")

    key = payload.get("key")
    value = payload.get("value")
    task_id = payload.get("task_id")
    project_id = payload.get("project_id")

    if not key:
        raise HTTPException(status_code=400, detail="Falta campo 'key' en el cuerpo JSON")

    try:
        if task_id:
            # Obtener tarea actual y anexar la info al campo description
            current = leantime_client.get_task(int(task_id))
            desc = (current.get("description") or "") + f"\n\nCustomField - {key}: {value}"
            updated = leantime_client.update_task(int(task_id), payload={"description": desc})
            return {"updated": updated}
        else:
            title = f"CustomField: {key}"
            description = f"{key}: {value}"
            created = leantime_client.create_task(title=title, description=description, project_id=project_id)
            return {"created": created}
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.on_event("startup")
def _start_scheduler() -> None:
    global recurrence_scheduler
    try:
        recurrence_scheduler = RecurrenceScheduler(str(RECURRING_FILE), leantime_client)
        recurrence_scheduler.start()
    except Exception:
        recurrence_scheduler = None


@app.on_event("shutdown")
def _stop_scheduler() -> None:
    global recurrence_scheduler
    try:
        if recurrence_scheduler:
            recurrence_scheduler.stop()
    except Exception:
        pass


@app.post("/recurring/create")
def recurring_create(payload: dict) -> Any:
    """Crea una tarea inmediata y registra la definición de recurrencia en disco.

    Campos aceptados: `title`, `project_id`, `cron` (string), `start_date` (opcional).
    """
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")

    title = payload.get("title")
    project_id = payload.get("project_id")
    cron = payload.get("cron")
    start_date = payload.get("start_date")

    if not title:
        raise HTTPException(status_code=400, detail="Falta campo 'title' en el cuerpo JSON")

    try:
        created = leantime_client.create_task(title=title, description=(f"Recurrence: {cron}" + (f"\nStart: {start_date}" if start_date else "")), project_id=project_id)

        # Append recurrence definition to recurring.json
        try:
            data = json.loads(RECURRING_FILE.read_text(encoding="utf-8") or "[]")
        except Exception:
            data = []
        entry = {"id": created.get("id"), "title": title, "project_id": project_id, "cron": cron, "start_date": start_date}
        data.append(entry)
        RECURRING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {"created": created, "scheduled": entry}
    except LeantimeAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def _read_recurring() -> list[dict]:
    try:
        return json.loads(RECURRING_FILE.read_text(encoding="utf-8") or "[]")
    except Exception:
        return []


def _write_recurring(data: list[dict]) -> None:
    RECURRING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/recurring/list")
def recurring_list() -> Any:
    """Devuelve la lista de definiciones recurrentes guardadas."""
    return _read_recurring()


@app.put("/recurring/{entry_id}")
def recurring_update(entry_id: int, payload: dict) -> Any:
    """Actualiza una definición recurrente. Campos permitidos: `title`, `project_id`, `cron`, `start_date`."""
    data = _read_recurring()
    for i, e in enumerate(data):
        if int(e.get("id")) == int(entry_id):
            # update allowed fields
            for k in ("title", "project_id", "cron", "start_date"):
                if k in payload:
                    e[k] = payload.get(k)
            data[i] = e
            _write_recurring(data)
            return {"updated": e}
    raise HTTPException(status_code=404, detail="Recurring entry no encontrada")


@app.delete("/recurring/{entry_id}")
def recurring_delete(entry_id: int, delete_task: bool | None = False) -> Any:
    """Elimina una definición recurrente. Si `delete_task=true` también intenta borrar la tarea original en Leantime."""
    data = _read_recurring()
    new = []
    removed = None
    for e in data:
        if int(e.get("id")) == int(entry_id):
            removed = e
            continue
        new.append(e)
    if removed is None:
        raise HTTPException(status_code=404, detail="Recurring entry no encontrada")
    _write_recurring(new)
    result: dict[str, Any] = {"removed": removed}
    if delete_task and leantime_client:
        try:
            # intentar eliminar la tarea original
            leantime_client.delete_task(int(removed.get("id")))
            result["task_deleted"] = True
        except Exception:
            result["task_deleted"] = False
    return result


@app.post("/recurring/run")
def recurring_run(payload: dict | None = None) -> Any:
    """Ejecuta manualmente una recurrencia. Si se pasa `id` ejecuta esa entrada, si no, ejecuta todas.

    El endpoint crea una nueva tarea en Leantime con el `title` y `project_id` de la definición.
    """
    if not leantime_client:
        raise HTTPException(status_code=500, detail=f"Leantime client no inicializado: {startup_error}")

    payload = payload or {}
    entry_id = payload.get("id")
    data = _read_recurring()

    to_run = []
    if entry_id is not None:
        for e in data:
            if int(e.get("id")) == int(entry_id):
                to_run.append(e)
                break
        if not to_run:
            raise HTTPException(status_code=404, detail="Recurring entry no encontrada")
    else:
        to_run = data

    created_tasks = []
    for e in to_run:
        title = e.get("title") or "(recurring)"
        project_id = e.get("project_id")
        description = f"Recurrence run for rule: {e.get('cron')}"
        try:
            created = leantime_client.create_task(title=title, description=description, project_id=project_id)
            created_tasks.append(created)
        except LeantimeAPIError as exc:
            created_tasks.append({"error": str(exc), "rule": e})

    return {"created": created_tasks}

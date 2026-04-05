from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Permite ejecutar pytest tanto desde la raíz interna del proyecto como desde
# el directorio padre que contiene el repositorio anidado.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Settings


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


@pytest.fixture
def fake_mcp() -> FakeMCP:
    return FakeMCP()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        leantime_url="https://example.leantime.test",
        leantime_token="test-token",
        leantime_api_base="/api/v1",
        leantime_default_project_id=101,
        leantime_timeout_seconds=30.0,
        leantime_verify_ssl=True,
        leantime_token_header="Authorization",
        leantime_token_prefix="Bearer",
        log_level="INFO",
        ai_base_url="http://localhost:11434/v1",
        ai_api_key="ollama",
        ai_model="llama3.2:3b",
        ai_timeout_seconds=60.0,
    )


@pytest.fixture
def mock_leantime_client(sample_tasks):
    client = Mock()
    client.get_tasks.return_value = sample_tasks
    client.get_projects.return_value = [{"id": 101, "name": "Proyecto Demo"}]
    client.get_task.side_effect = lambda task_id: next(task for task in sample_tasks if task["id"] == task_id)
    client.create_task.side_effect = lambda payload: {
        "id": 999,
        "title": payload.get("title"),
        "description": payload.get("description"),
        "status": "new",
        **payload,
    }
    client.update_task.side_effect = lambda task_id, payload=None, **kwargs: {
        **next(task for task in sample_tasks if task["id"] == task_id),
        **(payload or {}),
        **kwargs,
    }
    client.delete_task.return_value = None
    client.test_connection.return_value = {"configured": True, "reachable": True, "project_count": 1}
    return client


@pytest.fixture
def sample_tasks():
    return [
        {
            "id": 1,
            "title": "Scraping de facturas PDF",
            "status": "new",
            "dueDate": "2026-04-04",
            "priority": "high",
            "estimatedMinutes": 120,
            "spentMinutes": 30,
            "projectId": 101,
        },
        {
            "id": 2,
            "title": "Validar OCR con muestras",
            "status": "in_progress",
            "dueDate": "2026-04-05",
            "priority": "medium",
            "estimatedMinutes": 90,
            "spentMinutes": 45,
            "projectId": 101,
        },
        {
            "id": 3,
            "title": "Actualizar dashboard en Power BI",
            "status": "done",
            "dueDate": "2026-04-10",
            "priority": "low",
            "estimatedMinutes": 60,
            "spentMinutes": 80,
            "projectId": 101,
        },
    ]


@pytest.fixture
def sample_entregables():
    return [
        {
            "id": 1,
            "nombre": "Auditoria inicial",
            "fase": "auditoria",
            "project_id": 101,
            "tareas_asociadas": [1, 2],
            "fecha_limite": "2026-04-06",
        },
        {
            "id": 2,
            "nombre": "Pipeline de desarrollo",
            "fase": "desarrollo",
            "project_id": 101,
            "tareas_asociadas": [2],
            "fecha_limite": "2026-04-08",
        },
    ]


@pytest.fixture(autouse=True)
def isolated_planning_dir(monkeypatch, tmp_path: Path):
    import src.tools as tools_module

    planning_dir = tmp_path / ".planning"
    monkeypatch.setattr(tools_module, "PLANNING_DIR", planning_dir)
    return planning_dir

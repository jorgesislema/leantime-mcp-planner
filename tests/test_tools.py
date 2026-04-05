from __future__ import annotations

from datetime import date

import httpx

from src.leantime_client import LeantimeClient
from src.tools import register_task_tools


def _register_tools(fake_mcp, mock_leantime_client, settings):
    import logging

    register_task_tools(fake_mcp, mock_leantime_client, settings, logging.getLogger("tests"))
    return fake_mcp.tools


def test_desglosar_tarea_scraping(fake_mcp, mock_leantime_client, settings):
    tools = _register_tools(fake_mcp, mock_leantime_client, settings)

    result = tools["desglosar_tarea"](
        descripcion_tarea="hacer scraping de facturas desde PDFs y cargarlas a PostgreSQL",
        nivel_experiencia="junior",
        tiempo_estimado_maximo=120,
    )

    assert result["ok"] is True
    assert result["subtareas"]
    assert all(item["tiempo_estimado_minutos"] <= 120 for item in result["subtareas"])
    assert any("scraping" in item["titulo"].lower() or "extracción" in item["descripcion"].lower() for item in result["subtareas"])
    assert "scraping" in result["keywords_detectadas"]


def test_desglosar_tarea_ocr(fake_mcp, mock_leantime_client, settings):
    tools = _register_tools(fake_mcp, mock_leantime_client, settings)

    result = tools["desglosar_tarea"](
        descripcion_tarea="extraer datos con OCR de imagenes y PDFs de facturas",
        nivel_experiencia="junior",
        tiempo_estimado_maximo=100,
    )

    assert result["ok"] is True
    assert all(item["tiempo_estimado_minutos"] <= 100 for item in result["subtareas"])
    assert any("ocr" in item["titulo"].lower() or "ocr" in item["descripcion"].lower() for item in result["subtareas"])
    assert "ocr" in result["keywords_detectadas"]


def test_planificar_dia(fake_mcp, mock_leantime_client, settings):
    tools = _register_tools(fake_mcp, mock_leantime_client, settings)

    result = tools["planificar_dia"](fecha="2026-04-03", horas_disponibles=3, bloques_minimos=30)

    assert result["ok"] is True
    assert result["horario_detallado"]
    total_minutes = sum(block["duracion_minutos"] for block in result["horario_detallado"])
    assert total_minutes <= 180
    assert all("inicio" in block and "fin" in block for block in result["horario_detallado"])
    assert any(task["deep_work"] is True for task in result["tareas_recomendadas"])


def test_cliente_leantime_mock(monkeypatch):
    JSONRPC_URL = "https://example.leantime.test/api/jsonrpc"
    TASK_FIXTURE = {"id": 7, "headline": "Nueva tarea", "status": 1, "projectId": 1}

    rpc_responses = {
        "leantime.rpc.projects.getAll": [{"id": 1, "name": "Demo"}],
        "leantime.rpc.tickets.addTicket": [7],
        "leantime.rpc.tickets.getTicket": TASK_FIXTURE,
    }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, **kwargs):
            method = (json or {}).get("method", "")
            result = rpc_responses.get(method)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": result, "id": 1},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(httpx, "Client", MockClient)

    client = LeantimeClient("https://example.leantime.test", "token")
    projects = client.get_projects()
    created = client.create_task("Nueva tarea", "Descripcion", 1, "high", "2026-04-05")

    assert projects == [{"id": 1, "name": "Demo"}]
    assert created["id"] == 7
    assert created["headline"] == "Nueva tarea"


def test_herramientas_con_mock(fake_mcp, mock_leantime_client, settings):
    tools = _register_tools(fake_mcp, mock_leantime_client, settings)

    created = tools["crear_tarea"]("Nueva tarea", "Descripcion breve", 101)
    pending = tools["listar_tareas_pendientes"](limit=5)
    task_detail = tools["obtener_tarea_por_id"](1)

    assert created["ok"] is True
    assert created["id"] == 999
    assert pending["ok"] is True
    assert len(pending["tasks"]) == 2
    assert task_detail["ok"] is True
    assert task_detail["task"]["id"] == 1

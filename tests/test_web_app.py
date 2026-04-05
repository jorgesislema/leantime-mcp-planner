from __future__ import annotations

from web import app as appmod


def test_ai_plan_and_create_creates_tasks(monkeypatch):
    class FakeAI:
        def chat(self, system_prompt: str, user_message: str, max_tokens: int = 0, temperature: float = 0.0) -> str:
            return (
                '{"resumen":"Plan listo","tasks":['
                '{"title":"Analisis inicial","description":"Definir alcance","priority":"alta"},'
                '{"title":"Diseno tecnico","description":"Preparar arquitectura","priority":"media"}'
                ']}'
            )

    created_calls = []

    class FakeLeantime:
        is_configured = True

        def get_projects(self):
            return [{"id": 1, "name": "Proyecto Demo"}]

        def get_tasks(self, project_id=None, status=None):
            return [{"headline": "Base existente", "description": "Tarea previa"}]

        def create_task(self, title, description=None, project_id=None, priority=None, fetch_created=True):
            created_calls.append(
                {
                    "title": title,
                    "description": description,
                    "project_id": project_id,
                    "priority": priority,
                }
            )
            return {
                "id": 100 + len(created_calls),
                "headline": title,
                "description": description,
                "projectId": project_id,
                "priority": priority,
            }

    monkeypatch.setattr(appmod, "ai_client", FakeAI())
    monkeypatch.setattr(appmod, "leantime_client", FakeLeantime())

    result = appmod.ai_plan_and_create({"brief": "Crear MVP de CRM", "project_id": 1, "max_tasks": 5})

    assert result["generated_count"] == 2
    assert result["created_count"] == 2
    assert [item["title"] for item in created_calls] == ["Analisis inicial", "Diseno tecnico"]
    assert result["created"][0]["headline"] == "Analisis inicial"

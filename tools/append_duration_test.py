import httpx, json

payload = {"key": "duration_minutes", "value": "90", "task_id": 280, "project_id": 1}
try:
    r = httpx.post("http://localhost:8000/customfields/set", json=payload, timeout=20)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR', e)

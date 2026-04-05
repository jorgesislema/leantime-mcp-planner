import httpx, json

payload = {"title": "Hacer ejercicio (90 min)", "project_id": 1, "cron": "15 6 * * *"}
try:
    r = httpx.post("http://localhost:8000/recurring/create", json=payload, timeout=20)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR', e)

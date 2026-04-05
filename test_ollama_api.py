import httpx, json

url = "http://localhost:11434/v1/chat/completions"
headers = {"Authorization": "Bearer ollama", "Content-Type": "application/json"}
body = {
    "model": "llama3.2:3b",
    "messages": [{"role": "user", "content": "Responde solo: ok"}],
    "max_tokens": 10,
    "temperature": 0.0,
}

try:
    r = httpx.post(url, json=body, headers=headers, timeout=20)
    print('HTTP', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(r.text)
except Exception as e:
    print('ERROR', e)

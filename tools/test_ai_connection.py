from pathlib import Path
import sys
import json
import urllib.request
import urllib.error

# Asegurar que 'src' esté en el path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ai_client import AIClient


def load_env_file(path: Path) -> dict:
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
        v = v.strip().strip('"').strip("'")
        data[k.strip()] = v
    return data


def main():
    env_path = Path(__file__).resolve().parents[1] / '.env'
    env = load_env_file(env_path)

    base = env.get('AI_BASE_URL') or env.get('AI_URL') or ''
    key = env.get('AI_API_KEY') or env.get('AI_KEY') or ''
    model = env.get('AI_MODEL') or 'default'

    print('AI_BASE_URL=', base)
    print('AI_MODEL=', model)

    client = AIClient(base_url=base, api_key=key, model=model)
    try:
        res = client.test_connection()
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as exc:
        print('ERROR:', exc)
    
    # Intentar llamadas directas con distintos encabezados comunes
    if base:
        endpoint = base.rstrip('/') + '/chat/completions'
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'Eres un asistente de prueba.'},
                {'role': 'user', 'content': 'Responde con ok'}
            ],
            'max_tokens': 5,
        }
        headers_options = [
            {'Authorization': f'Bearer {key}'},
            {'x-api-key': key},
            {'api-key': key},
            {'Authorization': f'DeepSeek {key}'},
            {'Authorization': f'Key {key}'},
        ]
        print('\nProbando cabeceras directas contra:', endpoint)
        for h in headers_options:
            header_name = list(h.keys())[0]
            try:
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(endpoint, data=data, method='POST')
                for k, v in h.items():
                    req.add_header(k, v)
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode('utf-8', errors='ignore')
                    print('Header:', header_name, 'Status:', resp.getcode())
                    try:
                        print(json.loads(body))
                    except Exception:
                        print('Non-json response:', body[:200])
            except urllib.error.HTTPError as he:
                try:
                    body = he.read().decode('utf-8', errors='ignore')
                    print('Header:', header_name, 'HTTPError:', he.code, body[:1000])
                except Exception:
                    print('Header:', header_name, 'HTTPError:', he)
            except Exception as exc:
                print('Error request with header', header_name, exc)


if __name__ == '__main__':
    main()

# leantime-mcp-planner

Servidor MCP que conecta Leantime con IA local (Ollama) para planificación de proyectos freelance: gestión de tareas, generación de descripciones, descomposición con IA y seguimiento de entregables.

## Arquitectura

```
Claude Desktop / Continue.dev
        │  stdio (MCP)
        ▼
   src/server.py   ←── src/tools.py  (herramientas Leantime)
        │           ←── src/ai_tools.py (herramientas IA)
        │
   ┌────┴────────────────┐
   │                     │
src/leantime_client.py   src/ai_client.py
   │  JSON-RPC            │  OpenAI-compatible
   ▼                      ▼
Leantime :8080         Ollama :11434
(Docker)               (local, llama3.2:3b)
```

## Requisitos

- Python 3.10 o superior.
- Docker Desktop (para Leantime + MariaDB).
- Ollama instalado localmente con el modelo `llama3.2:3b`.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell: & .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Levantar Leantime (Docker)

```bash
docker compose up -d
```

Leantime queda disponible en `http://localhost:8080`.  
Credenciales iniciales de la interfaz web: `admin@example.com` / `Cambia_Tu_Password_123`.

### Crear el usuario API en la base de datos

Ejecuta estos comandos una sola vez para generar un usuario API y su hash de contraseña:

```bash
# 1. Genera el hash bcrypt dentro del contenedor (evita corrupción de $ en el shell)
docker exec leantime_db mariadb -u leantime -pleantime_pass leantime \
  -e "INSERT IGNORE INTO zp_user (username,password,firstname,lastname,role,source,status) VALUES ('mcp-api-user','placeholder','MCP','API',10,'api',1);"

# 2. Crea fix_auth.php en el contenedor de Leantime para actualizar el hash
docker cp fix_auth.php leantime_app:/tmp/fix_auth.php
docker exec leantime_app php /tmp/fix_auth.php
```

> El archivo `fix_auth.php` genera el hash con `password_hash()` desde PHP dentro del contenedor y lo escribe directamente en la base de datos, evitando la corrupción de caracteres `$` en el shell.

Una vez creado, el token de API tiene formato `lt_{username}_{clave_en_texto_plano}`, por ejemplo `lt_mcp-api-user_mcpkey2026`.

## Configuración (.env)

Copia `.env.example` a `.env` y ajusta los valores:

```env
# Leantime
LEANTIME_URL=http://localhost:8080
LEANTIME_TOKEN=REPLACE_WITH_LEANTIME_TOKEN
LEANTIME_TOKEN_HEADER=x-api-key
LEANTIME_TOKEN_PREFIX=
LEANTIME_DEFAULT_PROJECT_ID=1
LEANTIME_TIMEOUT_SECONDS=30
LEANTIME_VERIFY_SSL=false

# IA local (Ollama)
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=REPLACE_WITH_AI_API_KEY
AI_MODEL=llama3.2:3b
AI_TIMEOUT_SECONDS=120

LOG_LEVEL=INFO
```

Variables clave:

| Variable | Descripción |
|---|---|
| `LEANTIME_URL` | URL base de Leantime (sin `/api/...`) |
| `LEANTIME_TOKEN` | Token en formato `lt_{user}_{key}` |
| `LEANTIME_TOKEN_HEADER` | Cabecera HTTP. Para Leantime usa `x-api-key` |
| `LEANTIME_TOKEN_PREFIX` | Dejar vacío para `x-api-key`; usar `Bearer` para `Authorization` |
| `AI_BASE_URL` | URL base de Ollama (`http://localhost:11434/v1`) o cualquier API compatible OpenAI |
| `AI_API_KEY` | `ollama` para uso local; clave real si es OpenAI/Groq |
| `AI_MODEL` | Modelo a usar, p.ej. `llama3.2:3b` |

## Levantar Ollama

```bash
# Descargar el modelo (solo la primera vez, ~2 GB)
ollama pull llama3.2:3b

# Iniciar el servidor Ollama (queda escuchando en localhost:11434)
ollama serve
```

Si ya tienes Ollama corriendo como proceso de sistema, no necesitas `ollama serve`.

## Cómo funciona la integración con Leantime

Leantime expone su API a través de **JSON-RPC 2.0** en el endpoint `/api/jsonrpc`.

### Autenticación

Todas las peticiones llevan la cabecera:

```
x-api-key: REPLACE_WITH_LEANTIME_TOKEN
```

El token es válido porque el usuario existe en `zp_user` con `source='api'` y la contraseña fue generada con `password_hash()` de PHP (`$2y$` bcrypt).

### Formato de llamada JSON-RPC

```json
POST http://localhost:8080/api/jsonrpc
Content-Type: application/json
x-api-key: lt_mcp-api-user_mcpkey2026

{
  "jsonrpc": "2.0",
  "method": "leantime.rpc.projects.getAll",
  "params": {},
  "id": 1
}
```

### Métodos JSON-RPC disponibles

| Método | Acción |
|---|---|
| `leantime.rpc.projects.getAll` | Lista todos los proyectos |
| `leantime.rpc.tickets.getAll` | Lista todas las tareas |
| `leantime.rpc.tickets.getTicket` | Obtiene una tarea por `id` |
| `leantime.rpc.tickets.addTicket` | Crea tarea (requiere `{"values": {...}}`) |
| `leantime.rpc.tickets.updateTicket` | Actualiza tarea (requiere `id` + `values`) |
| `leantime.rpc.tickets.delete` | Elimina tarea por `id` |

### Prueba rápida desde PowerShell

```powershell
$body = '{"jsonrpc":"2.0","method":"leantime.rpc.projects.getAll","params":{},"id":1}'
Invoke-RestMethod `
  -Uri http://localhost:8080/api/jsonrpc `
  -Method Post `
  -Body $body `
  -ContentType 'application/json' `
  -Headers @{ 'x-api-key' = 'REPLACE_WITH_LEANTIME_TOKEN' }
```

### Uso desde Python (LeantimeClient)

```python
from src.leantime_client import LeantimeClient

lc = LeantimeClient(
  base_url="http://localhost:8080",
  api_token="REPLACE_WITH_LEANTIME_TOKEN",
  token_header="x-api-key",
  token_prefix="",
)

projects = lc.get_projects()
tasks    = lc.get_tasks(project_id=1)
new_id   = lc.create_task({"headline": "Mi tarea", "projectId": 1})
lc.update_task(new_id, {"description": "Detalle adicional"})
lc.delete_task(new_id)
```

## Verificación end-to-end

```bash
.venv\Scripts\python.exe run_checks.py
```

Salida esperada:

```json
LEANTIME: { "configured": true, "reachable": true, "project_count": 1 }
AI:       { "configured": true, "reachable": true, "model": "llama3.2:3b", "sample_response": "ok" }
```

## Ejecución del servidor MCP

```bash
.venv\Scripts\python.exe run.py
```

El servidor arranca con transporte stdio, listo para Claude Desktop o Continue.dev.

## Uso Con Claude Desktop

Archivo de configuración:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Ejemplo disponible en [examples/claude_desktop_config.json](examples/claude_desktop_config.json).

Usa siempre el Python del `.venv` y `run.py` en la configuración, no `python -m src.server`.

## Uso Con Continue.dev

Ejemplo disponible en [examples/continue_config.json](examples/continue_config.json).

Agrega el servidor dentro de `experimental.mcpServers` en tu configuración de Continue.

## Pruebas unitarias

```bash
.venv\Scripts\python.exe -m pytest -v
```

## Herramientas MCP disponibles

### Leantime

| Herramienta | Descripción |
|---|---|
| `ping` | Valida que el proceso esté vivo |
| `get_server_status` | Muestra configuración operativa |
| `test_leantime_connection` | Verifica conectividad con Leantime |
| `list_projects` | Lista proyectos desde Leantime |
| `list_tasks` | Lista tareas con filtros |
| `crear_tarea` | Crea una tarea en Leantime |
| `listar_tareas_pendientes` | Tareas no completadas del proyecto actual |
| `obtener_tarea_por_id` | Detalle completo de una tarea |
| `actualizar_estado_tarea` | Cambia el estado de una tarea |
| `eliminar_tarea` | Elimina una tarea por ID |

### IA (Ollama / OpenAI-compatible)

| Herramienta | Descripción |
|---|---|
| `test_ai_connection` | Verifica que la API de IA responde |
| `generar_descripcion_tarea` | Genera descripción detallada para una tarea |
| `descomponer_tarea_con_ia` | Divide una tarea compleja en subtareas |
| `sugerir_prioridad` | Sugiere prioridad basada en título y contexto |
| `resumir_tareas_proyecto` | Resume el estado de tareas de un proyecto |

## Crear tareas con IA directamente en Leantime

El bridge web ahora puede tomar un brief en lenguaje natural, pedirle a DeepSeek u otra IA compatible OpenAI que lo convierta en un plan estructurado y crear las tareas automáticamente en Leantime.

### Endpoint automático

```json
POST http://localhost:8000/ai/plan-and-create
Content-Type: application/json

{
  "brief": "Necesito desarrollar un MVP de CRM para captar clientes, registrar contactos y agendar seguimientos.",
  "project_id": 1,
  "max_tasks": 8
}
```

Respuesta esperada:

```json
{
  "summary": "Plan generado por IA",
  "generated_count": 6,
  "created_count": 6,
  "created": [
    {"id": 201, "headline": "Definir alcance del MVP"}
  ]
}
```

### Uso desde la UI

Abre [web/static/chat.html](web/static/chat.html), escribe la idea del proyecto y pulsa `IA planifica y crea`.

El chat de esa pantalla ya responde desde el contexto real del bridge: si Leantime esta configurado, no contestara como un modelo aislado sino como un asistente conectado a tu instancia.

Ese botón hace tres cosas:

1. Lee tareas existentes del proyecto en Leantime.
2. Pide a la IA un desglose en JSON estructurado.
3. Crea automáticamente las tareas en Leantime por ti.

### Requisitos para que funcione

- `LEANTIME_URL` y `LEANTIME_TOKEN` válidos.
- `AI_BASE_URL`, `AI_API_KEY` y `AI_MODEL` válidos.
- El bridge web levantado en `http://localhost:8000`.

Si la IA responde texto libre en vez de JSON válido, el endpoint devolverá error. Para DeepSeek funciona mejor con temperatura baja (`0.2`) como ya está configurado.

### Planificación local

| Herramienta | Descripción |
|---|---|
| `desglosar_tarea` | Desglose local con heurísticas (sin IA) |
| `planificar_dia` | Genera bloques horarios desde tareas pendientes |
| `agregar_alarma` | Crea recordatorios locales |
| `obtener_calendario_dia` | Consulta planificación de una fecha |
| `crear_entregable` | Registra un entregable por fase |
| `obtener_progreso_fase` | Avance y pendientes por fase |
| `sugerir_siguiente_fase` | Siguiente fase según dependencias |
| `generar_informe_entregable` | Resumen de avance y tiempos |

## Estructura del proyecto

```text
docker-compose.yml        ← Leantime + MariaDB locales
run.py                    ← Punto de entrada MCP (stdio)
run_checks.py             ← Verificación end-to-end
src/
  config.py               ← Settings desde .env
  leantime_client.py      ← Cliente JSON-RPC para Leantime
  ai_client.py            ← Cliente OpenAI-compatible (Ollama/OpenAI/Groq)
  ai_tools.py             ← Herramientas MCP que usan IA
  tools.py                ← Herramientas MCP para Leantime y planificación
  server.py               ← Servidor MCP (FastMCP)
tests/
  conftest.py
  test_tools.py
examples/
  claude_desktop_config.json
  continue_config.json
.env.example
requirements.txt
```

La carpeta `.planning/` se crea automáticamente para guardar desgloses, calendarios, alarmas y entregables locales.

## Consideraciones de seguridad

- No subas `.env` al repositorio (está en `.gitignore`).
- Usa contraseñas distintas en `docker-compose.yml` para entornos no locales.
- `LEANTIME_VERIFY_SSL=false` solo es seguro en localhost; actívalo en producción.

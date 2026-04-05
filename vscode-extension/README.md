# Leantime MCP VS Code extension (scaffold)

Este scaffold proporciona una extensión mínima para VS Code que:

- Muestra un `StatusBarItem` con el recuento de tareas del proyecto configurado.
- Hace polling a `http://localhost:8080/tasks?project_id=...` cada X segundos.

Instrucciones rápidas:

1. Abrir `vscode-extension` en una terminal.
2. Ejecutar `npm install`.
3. Ejecutar `npm run compile`.
4. Abrir la carpeta en VS Code y pulsar `F5` para ejecutar la extensión en un host de extensión.

Configuración (per-workspace, en `.vscode/settings.json` o UI de settings):

- `leantime-mcp.bridgeUrl` (string) — URL del bridge (por defecto `http://localhost:8080`).
- `leantime-mcp.projectId` (number) — Project ID a monitorizar.
- `leantime-mcp.pollInterval` (number) — Intervalo de polling en segundos.

Comandos disponibles:

- `Leantime MCP: Refresh` — fuerza una actualización inmediata.
- `Leantime MCP: Open Project in Browser` — abre la vista del proyecto configurado en el navegador.

Auto-detección de `projectId`:

Si no hay `leantime-mcp.projectId` configurado en el workspace, la extensión intentará obtener la lista de proyectos desde el bridge (`/projects`) y te pedirá seleccionar cuál asignar al workspace.

Panel lateral "Leantime Today":

- La extensión añade un panel en el explorador llamado "Leantime Today" que lista las tareas cuya fecha coincide con la fecha actual.
- Al hacer clic en una tarea se muestra un diálogo con detalles y opciones para abrir el listado de tareas del proyecto en el navegador o copiar el `id` de la tarea.
 - En el diálogo de la tarea también hay la opción "Mark Complete" para marcar la tarea como completada desde la extensión. Si el bridge expone `/tasks/{id}/complete` se usará esa ruta; si no, la extensión intenta un `PATCH /tasks/{id}` con `{ "status": "done" }`.
 - En el diálogo de la tarea también hay la opción "Mark Complete" para marcar la tarea como completada desde la extensión. Si el bridge expone `/tasks/{id}/complete` se usará esa ruta; si no, la extensión intenta un `PATCH /tasks/{id}` con `{ "status": "done" }`.
 - También existe la opción "Reopen" para reabrir una tarea completada; la extensión intentará `POST /tasks/{id}/reopen` y, si no existe, hará `PATCH /tasks/{id}` con `{ "status": "open" }`.

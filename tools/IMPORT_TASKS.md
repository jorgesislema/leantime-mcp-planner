Instrucciones rápidas para importar tareas desde Excel/CSV a Leantime

1) Desde Excel: guardar como `CSV UTF-8 (delimitado por comas) (*.csv)`.

2) Formato CSV (cabecera) recomendado:

   title,description,project_id

   - `title`: obligatorio
   - `description`: opcional
   - `project_id`: opcional (si no se indica, puede pasarse con --project)

3) Ejecutar el importador (desde la raíz del repo):

```
python tools/import_tasks.py --file rutas/tareas.csv --url http://localhost:8000 --project 5
```

4) Alternativa con PowerShell (si prefieres no usar Python):

```
Import-Csv tareas.csv | ForEach-Object {
  $body = @{ title = $_.title; description = $_.description; project_id = [int]$_.project_id } | ConvertTo-Json
  Invoke-RestMethod -Uri 'http://localhost:8000/tasks' -Method Post -Body $body -ContentType 'application/json'
}
```

5) Notas:
- El bridge HTTP (por defecto `http://localhost:8000`) debe estar en ejecución y apuntar a tu instancia de Leantime.
- Si tus columnas tienen nombres distintos, renómbralas o modifica el CSV para que contenga `title`.
- Si hay muchas tareas, ejecuta en lotes y revisa límites de API/ratelimit.

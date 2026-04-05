FROM python:3.11-slim
WORKDIR /app

# Instalar dependencias del sistema mínimo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY web/requirements.txt /app/web/requirements.txt
COPY . /app

RUN python -m pip install --upgrade pip setuptools
RUN pip install --no-cache-dir -r /app/web/requirements.txt

EXPOSE 8000
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
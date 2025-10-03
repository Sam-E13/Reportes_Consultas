FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Recolectar archivos estáticos
RUN python manage.py collectstatic --noinput || true

# Exponer el puerto (Render usa PORT dinámicamente)
EXPOSE 8002

# Usar gunicorn en producción
CMD gunicorn ReportesConsulta.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
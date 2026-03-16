FROM python:3.11-slim

WORKDIR /app

COPY backend /app/backend
COPY services/modular-api/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "backend.api_service.main:app", "--host", "0.0.0.0", "--port", "8000"]

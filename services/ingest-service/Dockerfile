FROM python:3.11-slim

WORKDIR /app

COPY services/ingest-service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/ingest-service/ .
COPY backend/shared/ ./backend/shared/

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

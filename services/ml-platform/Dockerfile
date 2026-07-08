FROM python:3.11-slim
WORKDIR /app

COPY services/ml-platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ml-platform/ .
COPY backend/shared/ ./backend/shared/
COPY infra/sql/ml_schema.sql ./infra/sql/ml_schema.sql

ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

COPY services/embedding-service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/embedding-service/ .
COPY backend/shared/ ./backend/shared/

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

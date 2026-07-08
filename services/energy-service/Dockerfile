FROM python:3.11-slim
WORKDIR /app
COPY services/energy-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/energy-service/ .
COPY backend/shared/ ./backend/shared/
COPY infra/sql/ ./infra/sql/
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

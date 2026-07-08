FROM python:3.11-slim

WORKDIR /app

COPY services/ml-service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

RUN python -m spacy link en_core_web_sm en_core_web_sm || true

COPY services/ml-service/ .
COPY backend/shared/ ./backend/shared/

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

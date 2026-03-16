FROM python:3.11-slim

WORKDIR /app

# Install system deps (needed for torch/transformers + spaCy)
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Install spaCy model via direct wheel (MOST RELIABLE)
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# (Optional) Create link name for spaCy
RUN python -m spacy link en_core_web_sm en_core_web_sm || true

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

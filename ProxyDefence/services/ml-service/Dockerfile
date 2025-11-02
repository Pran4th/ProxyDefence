FROM python:3.11-slim

WORKDIR /app

# Install system deps (needed for torch/transformers)
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies first (cached if unchanged)
RUN pip install --prefer-binary -r requirements.txt
# In your ml-service Dockerfile, after the pip install line
RUN python -m spacy download en_core_web_sm

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

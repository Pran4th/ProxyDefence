# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProxyDefence is a military-grade cyber defense intelligence platform with an event-driven microservices architecture. Data flows through a Kafka pipeline: news is ingested → processed by ML/NLP → stored in PostgreSQL and Elasticsearch → served to the React frontend via FastAPI.

## Architecture

### Data Pipeline

```
GNews API → ingest-service → Kafka (raw_articles)
                          → ml-service → Kafka (processed_articles)
                                         → database-service → PostgreSQL + Elasticsearch
                                         → conflict-api → Frontend

```

### Service Ports

| Service | Port |
| --- | --- |
| Frontend (Vite dev) | 8080 |
| Ingest Service | 8001 |
| ML Service | 8002 |
| Database Service | 8003 |
| Conflict API | 8004 |
| Kafka | 9092 |
| PostgreSQL | 5432 |
| Elasticsearch | 9200 |

### Microservices

**ingest-service** (`services/ingest-service/`)

* FastAPI service that fetches news from GNews API
* Publishes raw articles to `raw_articles` Kafka topic
* Trigger via `GET /fetch-real-news` endpoint

**ml-service** (`services/ml-service/`)

* FastAPI service that subscribes to `raw_articles` topic
* Performs sentiment analysis (keyword-based, returns negative/positive/neutral)
* Publishes processed articles to `processed_articles` Kafka topic
* Runs consumer as background thread on startup
* Uses spaCy, Transformers, PyTorch (though sentiment is currently simple keyword-based)

**database-service** (`services/database-service/`)

* FastAPI service that consumes from `processed_articles` topic
* Stores articles in PostgreSQL `processed_articles` table
* Indexes articles in Elasticsearch `processed_articles` index
* Provides REST endpoints: `/api/articles`, `/api/analytics/summary`, `/api/search`, `/api/articles/{article_id}`

**conflict-api** (`services/conflict-api/`)

* Main API gateway for frontend
* Queries PostgreSQL and Elasticsearch
* Async FastAPI with connection pooling (asyncpg, AsyncElasticsearch)
* Endpoints: `/articles`, `/articles/{article_id}`, `/analytics/summary`, `/search`

### Database Schema

**processed_articles** - Main article table with id, title, content, source, published_at, ml_processed, confidence, sentiment
**extracted_entities** - Child table referencing processed_articles(id)
**article_sentiments** - Child table referencing processed_articles(id)

Schema defined in `infra/sql/init.sql`, initialized on PostgreSQL container startup.

### Frontend Stack

* React 18 + TypeScript 5.8 + Vite 5.4
* Tailwind CSS 3.4 + shadcn/ui components (Radix UI primitives)
* React Router 6 for routing
* TanStack Query (@tanstack/react-query) for data fetching
* React Hook Form + Zod for forms
* Recharts for charts
* Lucide React for icons
* Axios for API calls to conflict-api

**Frontend API client** (`frontend/src/lib/api.ts`):

* Uses `VITE_API_URL` env var, defaults to `http://localhost:8000`
* Key functions: `fetchArticles()`, `fetchAnalyticsSummary()`

---

## AI Collaboration (Gemini Integration)

This project uses a "Multi-Model" approach. While Claude handles code generation and refactoring, **Gemini 1.5/2.0** is used for high-context analysis across the entire microservices architecture.

**Gemini Usage Instructions for Claude:**

* **Codebase Reviews:** Use the Gemini CLI to analyze all services (`/services/**`) simultaneously when checking for architectural drift or Kafka schema consistency.
* **Log Analysis:** If a data pipeline error occurs, pipe the output of `docker-compose logs` to Gemini for root-cause analysis across multiple containers.
* **ML/NLP Strategy:** Delegate complex prompt engineering or NLP model selection logic (for `ml-service`) to Gemini, as it can reference a larger corpus of documentation.

**Integration Commands:**

* Analyze all services: `gemini analyze ./services`
* Explain pipeline flow: `gemini "Explain the data flow from ingest-service to Elasticsearch in this repo"`

---

## Development Commands

### Docker Compose (Full Stack)

```bash
# Start all services
docker-compose up

# Start in detached mode
docker-compose up -d

# Rebuild and start
docker-compose up --build

# Stop all services
docker-compose down

```

### Frontend Development

```bash
cd frontend
npm run dev         # Dev server on port 8080
npm run build       # Production build
npm run build:dev   # Development build
npm run lint        # ESLint
npm run preview     # Preview production build

```

### Individual Python Services (Local Dev)

Each service runs on internal port 8000, mapped externally as shown above:

```bash
# Conflict API
cd services/conflict-api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Ingest Service
cd services/ingest-service
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# ML Service
cd services/ml-service
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Database Service
cd services/database-service
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

```

### Trigger Data Pipeline

After starting services, trigger news ingestion:

```bash
curl http://localhost:8001/fetch-real-news

```

## Configuration Notes

* Kafka auto-creates topics, no manual setup needed
* PostgreSQL credentials: `admin/admin123`, database: `defenseintel`
* Elasticsearch runs with security disabled (single-node dev mode)
* All services communicate over the `proxy_net` Docker bridge network
* The `services/frontend/` directory is a placeholder - use `frontend/` at root instead
* Frontend uses Supabase credentials in `.env` but backend connects directly to PostgreSQL

---

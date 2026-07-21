# Deployment (AWS, venv-based)

Deployment mirrors local development exactly: **infrastructure in Docker
(`docker compose up -d` — Postgres, Kafka, Elasticsearch only), Python
services in per-service venvs, frontend built once and served statically.**
There is no app-in-Docker build. That path was removed deliberately — the
torch dependency makes ml-platform's image build slow and fragile, and the
venv workflow is already proven on this exact codebase every day.

## Target

One EC2 instance (Ubuntu 22.04+, `t3.xlarge` / 16 GB recommended — the
transformer models in ml-platform's consumer are the memory floor). Open
inbound: 22 (SSH), 80/443 (nginx). Keep 8000-8007 closed; nginx proxies.

## 1. Provision

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip nginx git
# Docker Engine (for infra only) -- standard install
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # re-login after this
# Node 20+ (build the frontend once; not needed at runtime)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
```

## 2. Clone + configure

```bash
git clone <repo-url> ~/ProxyDefence && cd ~/ProxyDefence
cp .env.example .env   # then fill in real values
```

`.env` changes vs. local dev:
- `POSTGRES_PORT=5434` stays (the override file maps 5434 on the host).
- `VITE_API_URL` must be the public URL nginx serves the API on
  (e.g. `http://<ec2-ip>` — nginx proxies `/api/` to modular-api), **set
  before the frontend build** — Vite bakes it in at build time.
- Real keys for `NEWS_API_KEY`, `OPENAI_API_KEY` (Groq), `AISSTREAM_API_KEY`,
  `EIA_API_KEY`, `CRUDE_PRICE_API_KEY`, `NEWSDATA_API_KEY`; fresh
  `JWT_SECRET_KEY`, non-default `POSTGRES_PASSWORD`/`ELASTIC_PASSWORD`.
- `ENERGY_LOAD_SEED=1` for first boot (idempotent; harmless to leave on).
- `ML_PLATFORM_URL=http://127.0.0.1:8007` (services talk over localhost,
  same as local dev).

## 3. Infra + venvs — the same scripts you use locally

The `.sh` twins of every dev script already exist:

```bash
scripts/dev/setup/setup.sh                  # creates all venvs, installs deps, spaCy models
scripts/dev/infrastructure/start-infra.sh   # docker compose up -d  (PG/Kafka/ES only)
```

## 4. Bootstrap the model registry (fresh DB only)

Model artifacts live in the repo (`services/ml-platform/data/artifacts/`),
but a fresh Postgres volume has no `ml.model_versions` rows pointing
`stage='production'` at them. Start ml-platform once (creates the `ml.`
schema), then:

```bash
cd services/ml-platform
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5434 POSTGRES_DB=defenseintel \
POSTGRES_USER=admin POSTGRES_PASSWORD=<pw> \
.venv/bin/python scripts/seed_demo_models.py
```

Idempotent — inserts the 5 shipped models' production rows (real metrics,
verbatim) so the first prediction request works without retraining.

## 5. Services as systemd units

One unit per service — same commands the `start-*.sh` scripts run, minus
`--reload`. Template (`/etc/systemd/system/pd-energy.service`):

```ini
[Unit]
Description=ProxyDefence energy-service
After=docker.service network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ProxyDefence/services/energy-service
EnvironmentFile=/home/ubuntu/ProxyDefence/.env
Environment=PYTHONPATH=/home/ubuntu/ProxyDefence:/home/ubuntu/ProxyDefence/services/energy-service
Environment=POSTGRES_HOST=127.0.0.1
ExecStart=/home/ubuntu/ProxyDefence/services/energy-service/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8006
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Repeat for: `pd-ingest` (8001), `pd-database` (8003), `pd-modular-api`
(8000), `pd-ml-platform` (8007), plus two non-uvicorn consumers:

```ini
# pd-ml-consumer: ExecStart=.../ml-platform/.venv/bin/python consumer/article_enrichment.py
# pd-db-consumer: ExecStart=.../database-service/.venv/bin/python consumer.py
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pd-modular-api pd-energy pd-ml-platform pd-ingest pd-database pd-ml-consumer pd-db-consumer
```

## 6. Frontend: build once, serve via nginx

```bash
cd services/frontend && npm ci && npm run build   # reads VITE_API_URL from env
sudo cp -r dist /var/www/proxydefence
```

`/etc/nginx/sites-available/proxydefence`:

```nginx
server {
    listen 80;
    root /var/www/proxydefence;
    index index.html;
    location / { try_files $uri /index.html; }          # SPA routing
    location /api/ { proxy_pass http://127.0.0.1:8000; } # modular-api gateway
}
```

## 7. Verify

```bash
curl -s localhost:8006/health   # energy-service + deps
curl -s localhost:8007/health   # ml-platform
curl -s localhost:8000/health   # gateway
curl -s http://localhost/       # frontend via nginx
```

Then trigger the pipeline once: `curl localhost:8001/fetch-real-news` and
watch an article flow through Kafka → enrichment → Postgres → frontend.

## Operations

| Task | Command |
|---|---|
| Logs | `journalctl -u pd-energy -f` |
| Restart a service | `sudo systemctl restart pd-ml-platform` |
| Deploy new code | `git pull`; re-run `pip install -r requirements.txt` in the touched service's venv if deps changed; `sudo systemctl restart pd-<service>`; frontend changes → rebuild `dist` and re-copy |
| Infra down/up | `scripts/dev/infrastructure/stop-infra.sh` / `start-infra.sh` (volumes persist) |

## Research Models

Trained models from `research/` are exported to `research/models/`.
The ML Platform loads models from a configurable path.
Research notebooks never execute on the production host.

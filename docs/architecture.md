# ProxyDefence Architecture

AI-driven energy supply-chain resilience for import-dependent economies.
The highlighted path is the **golden thread**: a live geopolitical signal
becomes an executable procurement + SPR decision in under 60 seconds, with
every stage timestamped in `energy.response_telemetry`.

```mermaid
flowchart LR
    subgraph SOURCES["Live Data Sources"]
        GNEWS["GNews / NewsData<br/>(news)"]
        GDELT["GDELT events"]
        AIS["AISstream<br/>(vessel positions)"]
        SANC["OFAC / EU / UN<br/>sanctions (~330k)"]
        PRICE["FRED / EIA /<br/>crude-price-api"]
        COMTRADE["UN Comtrade<br/>(India crude imports)"]
    end

    subgraph PIPELINE["Event Pipeline"]
        INGEST["ingest-service"]
        KAFKA[("Kafka")]
        MLC["ml-platform consumer<br/>DistilBERT sentiment · BERT NER<br/>XGBoost topic · blended threat score"]
        DB["database-service"]
        PG[("PostgreSQL<br/>+ pgvector")]
        ES[("Elasticsearch")]
    end

    subgraph MLP["ML Platform (8007)"]
        MODELS["5 trained models<br/>disruption-risk AUC 0.734<br/>topic · price · shock · ranker"]
        PRED["prediction API"]
    end

    subgraph ENERGY["Energy Service (8006)"]
        SIG["ArticleSignalIngestor<br/>→ disruption_signals"]
        CORR["Corridor Risk Engine<br/>probability by corridor & supplier"]
        RISK["Risk Engine<br/>ML-blended scores"]
        TWIN["Digital Twin<br/>tick-based network flow<br/>GDP · fuel price · run rates"]
        SPR["SPR Engine<br/>ISPRL Visakh/Mangalore/Padur"]
        PROC["Procurement Optimizer<br/>Pareto · grade compatibility"]
        ORCH["Response Orchestrator<br/>signal → recommendation<br/>⏱ telemetry-tracked"]
    end

    subgraph SERVE["Serving"]
        GW["modular-api (8000)<br/>JWT gateway · Copilot · RAG"]
        FE["React Command Center<br/>corridor strip · map · stopwatch"]
    end

    GNEWS --> INGEST --> KAFKA --> MLC --> KAFKA
    KAFKA --> DB --> PG
    DB --> ES
    GDELT --> MODELS
    SANC --> MODELS
    PRICE --> MODELS
    AIS --> CORR
    COMTRADE --> CORR
    MODELS --> PRED
    PRED -. "ML blend" .-> RISK
    PG --> SIG

    SIG ==> ORCH
    ORCH ==> TWIN ==> ORCH
    ORCH ==> SPR
    ORCH ==> PROC
    SIG --> CORR
    RISK --> CORR

    ORCH --> GW --> FE
    CORR --> GW

    style ORCH fill:#7c2d12,stroke:#f97316,stroke-width:3px,color:#fff
    style SIG fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff
    style TWIN fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff
    style SPR fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff
    style PROC fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff
    style FE fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#fff
```

## The golden thread (measured)

```
disruption signal (news→ML, live)          t = 0
  → scenario match (keyword→template)      + <1s
  → digital twin run (30-day horizon)      + ~8s
  → SPR optimization (3 ISPRL sites)       + ~2s
  → procurement orchestration (Pareto)     + ~2s
  = executable recommendation              ~12s measured p50
```

Every response writes `energy.response_telemetry`
(signal_detected_at → analysis_started_at → analysis_completed_at →
recommendation_generated_at, total_latency_seconds).
`GET /api/v1/intelligence/command/telemetry` serves p50/p95.

## Corridor disruption probability (the brief's #1 build)

Transparent composite index per corridor (Hormuz, Red Sea/Suez, Cape,
West Africa, Malacca): 0.40·signal pressure + 0.25·entity ML risk +
0.20·GDELT instability + 0.15·AIS anomaly → logistic squash. Every
weight published in an `assumptions[]` block with a how-to-test recipe;
every driver is a named live signal. India import share per corridor from
UN Comtrade 2021-24 (Hormuz: 46.5% in 2024).
```

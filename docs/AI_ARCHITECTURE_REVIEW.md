# AI Architecture Review — ProxyDefence

> **Date:** 2026-07-05
> **Author:** Principal AI Architect
> **Scope:** Complete AI transformation blueprint for hackathon-winning energy supply chain resilience platform
> **Methodology:** Source-code verified architecture analysis (100% validated from existing implementation)

---

## Table of Contents

1. [Current AI Maturity](#1-current-ai-maturity)
2. [AI Opportunity Matrix](#2-ai-opportunity-matrix)
3. [Agent Architecture](#3-agent-architecture)
4. [Tool Architecture](#4-tool-architecture)
5. [RAG Architecture](#5-rag-architecture)
6. [ML Architecture](#6-ml-architecture)
7. [LLM Architecture](#7-llm-architecture)
8. [Multi-Agent Orchestration](#8-multi-agent-orchestration)
9. [Module-by-Module AI Analysis](#9-module-by-module-ai-analysis)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Judging Optimization](#11-judging-optimization)
12. [What NOT to Build](#12-what-not-to-build)
13. [Expected Score After Implementation](#13-expected-score-after-implementation)
14. [Final Architecture Diagram](#14-final-architecture-diagram)

---

## 1. Current AI Maturity

### AI Maturity Score: **1.2/10**

| Category | Score | Evidence |
|----------|-------|----------|
| LLM Integration | 0/10 | Zero LLM API calls anywhere in codebase |
| RAG Pipeline | 0/10 | No retrieval-augmented generation pipeline exists |
| Agentic AI | 0/10 | No agent framework, no autonomous loops, no tool calling |
| ML in Production | 3/10 | 3 models (sentiment, NER, embeddings) but 5 heuristic components |
| ML Platform | 1/10 | Complete infrastructure but zero trained artifacts |
| Knowledge Graph Reasoning | 1/10 | Graph data exists but no graph algorithms beyond BFS |
| Semantic Understanding | 4/10 | bge-small-en-v1.5 embeddings enable basic semantic search |
| Autonomous Decision-Making | 0/10 | All decisions are manually triggered with explicit parameters |
| Natural Language Interface | 2/10 | "Copilot" is rule-based keyword matching, not NLU |
| Executive Intelligence | 1/10 | Executive cards are template-based, no natural language generation |

### Key Metrics (Verified from Source)

| Metric | Value |
|--------|-------|
| Lines of LLM integration | **0** |
| Trained model artifacts (.joblib/.pkl) | **0** |
| Agent definitions | **0** |
| RAG pipelines | **0** |
| MLflow runs | **0** |
| Parquet dataset files | **0** |
| Heuristic intelligence components | **5** (topic, threat, relationships, summarization, risk scoring) |
| Production ML models | **3** (sentiment, NER, embeddings) |
| Deterministic-but-AI-eligible subsystems | **7** (Copilot, Risk, Procurement, SPR, Digital Twin, Alerts, Reports) |

---

## 2. AI Opportunity Matrix

For every subsystem, a detailed analysis of where AI should replace, augment, or leave deterministic logic.

### 2.1 Copilot (backend/api/copilot/) — AI Maturity: 1/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | Rule-based intelligence retrieval system. Receives question → semantic search → count high-risk articles → compute threat level (if >5 critical articles → critical; if >3 → high) → compute threat indicators (count military/economic/diplomatic keywords) → normalize entities → compute energy impact (count infra events) → return JSON. |
| **Current Logic** | `CopilotService.compute_threat_level()`: 5 hardcoded thresholds. `compute_threat_indicators()`: topic keyword counting. `normalize_entities()`: dedup + sort by count. `compute_energy_impact()`: count-based severity. |
| **Current Limitations** | Zero natural language understanding. Zero reasoning. Zero context awareness. Each query is independent (no conversation memory). Cannot answer "why" or "explain". Output is JSON, not natural language. |
| **What AI replaces** | **Everything.** Replace the entire rule-based pipeline with an LLM that has access to tools and RAG. The rule-based threat level, indicators, energy impact, and summary should all be LLM-generated. |
| **What AI augments** | The existing semantic search result (top articles) becomes the RAG context. The existing entity/relationship/event data becomes tool outputs fed to the LLM. |
| **What stays deterministic** | Database queries for articles, entities, events, relationships. The search/retrieval layer. |
| **Expected improvement** | From a keyword counter to an actual intelligence analyst that can reason, explain, and converse. |
| **Difficulty** | Medium |
| **Hackathon impact** | **GAME-CHANGER** — transforms the most visible feature from "fake AI" to "real AI" |

### 2.2 Risk Intelligence Engine (services/energy-service/services/risk_engine.py) — AI Maturity: 2/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | `RiskScoringEngine`: 4-dimension weighted scoring (geopolitical/operational/economic/environmental). `SignalDetector`: threshold-based signal detection. `CommodityPriceIngestor`, `SanctionsIngestor`, `AISIngestor`: all simulate data (no real APIs). |
| **Current Logic** | Risk scores computed as: `(data_source_weight × signal_strength + ...) / total_signals`. Dimensions are weighted hardcoded values. "High risk" = score > 0.7. Data ingestors generate random walk prices. |
| **Current Limitations** | Simulated data. Hardcoded weights. No learning from historical outcomes. No correlation between signals. No predictive capability. |
| **What AI replaces** | **Risk score computation.** Replace weighted formula with ML-predicted risk scores (using ML Platform). Replace hardcoded thresholds with learned thresholds. |
| **What AI augments** | **Signal correlation.** LLM can analyze multiple signals and identify compound risks that no weighted formula would catch. **Scenario evaluation.** LLM can evaluate what-if scenarios with reasoning. |
| **What stays deterministic** | Data storage/retrieval. CRUD operations. The ingestion pipeline structure. The risk factor definition system. |
| **Expected improvement** | From naive weighted scoring to learned risk prediction + LLM-powered risk narrative. |
| **Difficulty** | Medium-High |
| **Hackathon impact** | **HIGH** — "ML-predicted risk scores" is a compelling demo point |

### 2.3 Digital Twin (services/energy-service/services/digital_twin/) — AI Maturity: 6/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | Tick-based simulation engine (378 lines). Capacity-constrained flow engine (299 lines). Network graph builder with BFS pathfinding (386 lines). 10 scenario templates (231 lines). |
| **Current Logic** | Explicit flow equations: `flow = min(capacity, demand, supply)`. Disruption modeling: `capacity *= (1 - disruption_pct)`. Cascade effects: propagate flow reduction downstream. Aggregate impacts: sum supply gaps, compute economic impact via multiplier. |
| **Current Limitations** | Deterministic (same inputs → same outputs). No probabilistic analysis. No Monte Carlo. No learning from past simulations. Scenario templates are hand-crafted. |
| **What AI replaces** | **Nothing in the core engine.** The flow simulation is correct as deterministic math. |
| **What AI augments** | **Scenario generation.** LLM can create new scenario templates from natural language descriptions ("Simulate a blockade in the Red Sea that also triggers a cyber attack on Ras Tanura"). **Scenario analysis.** LLM can interpret simulation results and explain impacts in natural language. **Recommendation generation.** LLM can suggest mitigation strategies based on simulation outputs. **Auto-trigger.** Agent can detect risk signals and autonomously trigger simulations. |
| **What stays deterministic** | The core simulation engine. Flow computation. Network graph building. All math. |
| **Expected improvement** | From manual scenario configuration to autonomous scenario generation, execution, and analysis. |
| **Difficulty** | Medium |
| **Hackathon impact** | **HIGH** — "Describe a scenario in natural language and watch it simulate" is extremely demo-friendly |

### 2.4 Knowledge Graph (backend/api/graph/ + energy.entity_relationships) — AI Maturity: 3/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | 3 relational graph layers: entity co-occurrence (public.relationships), typed asset relationships (energy.entity_relationships), supply chain topology (energy.network_nodes/edges). 2 API endpoints (full graph, entity expansion). BFS pathfinding. |
| **Current Logic** | PostgreSQL recursive CTEs for pathfinding. No graph algorithms (no PageRank, no community detection, no centrality). Entity matching via LOWER() and LIKE. |
| **Current Limitations** | No graph-native querying. No graph algorithms. No semantic graph traversal. Relationship inference is heuristic (co-occurrence). No knowledge graph reasoning. |
| **What AI replaces** | **Relationship inference.** Replace entity-pairing heuristic with LLM-based relationship extraction. **Graph reasoning.** LLM can traverse the graph in natural language ("How is Jamnagar refinery connected to the Strait of Hormuz?"). |
| **What AI augments** | **Entity resolution.** LLM can disambiguate entities (e.g., "Iran" vs "Islamic Republic of Iran"). **Graph enrichment.** LLM can suggest missing relationships. **Natural language graph queries.** |
| **What stays deterministic** | Graph storage and basic querying. BFS pathfinding for known routes. The network graph topology. |
| **Expected improvement** | From a relational graph with basic queries to a semantically-enriched knowledge graph with LLM-powered reasoning. |
| **Difficulty** | Medium |
| **Hackathon impact** | **HIGH** — "Ask your knowledge graph questions in natural language" is compelling |

### 2.5 Semantic Search (services/embedding-service/ + backend/api/search/) — AI Maturity: 5/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | bge-small-en-v1.5 (384d) via fastembed. pgvector cosine distance. Top 5 results. Elasticsearch multi_match for full-text search. |
| **Current Logic** | `SELECT ... FROM article_embeddings ORDER BY embedding <=> $1 LIMIT 5`. ES: `multi_match: { query, fields: [title^3, summary^2, content, source, topic], fuzziness: AUTO }`. |
| **Current Limitations** | No hybrid search (dense + sparse combined). No re-ranking. No cross-encoder. Top 5 is too few for RAG. No filtering by date/risk/relevance. |
| **What AI replaces** | **Re-ranking.** Add a cross-encoder (e.g., BAAI/bge-reranker-v2-m3) for result re-ranking. |
| **What AI augments** | **Hybrid search.** Combine dense (pgvector) + sparse (ES BM25) with weighted fusion. **Query expansion.** LLM can expand search queries. **Result filtering.** LLM can filter results by relevance. **Search-as-a-tool.** Expose search as an agent tool. |
| **What stays deterministic** | The core embedding generation. The vector store. The ES index. |
| **Expected improvement** | From basic dense search to production-grade hybrid search with re-ranking. |
| **Difficulty** | Low-Medium |
| **Hackathon impact** | Medium — foundational improvement, not demo-visible |

### 2.6 Procurement Orchestrator (services/energy-service/services/procurement/) — AI Maturity: 7/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | SupplierIntelligence (218 lines), RefineryCompatibility (183 lines), ProcurementOptimizer (269 lines), ProcurementOrchestrator (526 lines). Pareto frontier optimization (cost/risk/lead-time). 4 executive card types. |
| **Current Logic** | Composite scoring: `composite_score = 0.30 × reliability + 0.20 × strategic_value + 0.15 × (1 - lead_time_normalized) + 0.15 × (1 - risk_normalized) + 0.20 × cost_score`. Pareto frontier: non-dominated sorting. Executive cards: template-based with hardcoded categories. |
| **Current Limitations** | Executive cards are template-generated (no natural language). Recommendations follow preset patterns. No learning from past procurement outcomes. No autonomous triggering. |
| **What AI replaces** | **Executive card generation.** Replace template-based cards with LLM-generated executive summaries, risk narratives, and recommendations. **Supplier scoring weights.** ML could learn optimal weights from historical outcomes. |
| **What AI augments** | **Procurement narrative.** LLM can explain why specific suppliers were chosen. **Scenario comparison.** LLM can compare multiple optimization runs. **Autonomous trigger.** Agent can detect supply gap and autonomously run procurement optimization. |
| **What stays deterministic** | The optimization engine (Pareto frontier computation is correct math). Compatibility scoring (NCI-based). Route cost computation. |
| **Expected improvement** | From template-driven procurement to AI-powered procurement with natural language explanation and autonomous triggering. |
| **Difficulty** | Low-Medium |
| **Hackathon impact** | **HIGH** — "AI explains why it chose these suppliers" is compelling |

### 2.7 SPR Decision Intelligence (services/energy-service/services/procurement/spr_engine.py) — AI Maturity: 6/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | SPREngine (851 lines). 6 strategies, 3 policies, 5-phase decision timeline. Release/refill/recommendation generation. Cost analysis. |
| **Current Logic** | Drawdown: `daily_release = min(max_drawdown, supply_gap / num_facilities)`. Timeline: hardcoded 5-phase structure. Recommendations: 4 card types with template content. Strategy: hardcoded ordering and reserve factors. |
| **Current Limitations** | Recommendations are template-based. Strategy selection is manual. No learning from past releases. No market timing. No probabilistic reserve modeling. |
| **What AI replaces** | **Recommendation generation.** LLM generates detailed release/refill/policy recommendations with natural language reasoning. **Strategy recommendation.** LLM recommends optimal strategy based on current conditions. |
| **What AI augments** | **Release narrative.** LLM explains the decision timeline in natural language. **Policy impact analysis.** LLM compares different policies. **Autonomous trigger.** Agent can detect supply crisis and autonomously run SPR analysis. |
| **What stays deterministic** | Drawdown computation. Capacity constraints. Timeline structure. Cost calculations. Policy constraint enforcement. |
| **Expected improvement** | From manual SPR analysis to AI-assisted strategic reserve management with natural language decision support. |
| **Difficulty** | Low-Medium |
| **Hackathon impact** | **HIGH** — "AI manages the nation's strategic petroleum reserve" is dramatic |

### 2.8 Alerts (backend/api/alerts/) — AI Maturity: 3/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | CRUD alerts. Manual generation via POST /alerts/generate (admin only). Status management (open/investigating/resolved). Watchlist-based entity tracking. |
| **Current Logic** | Generation: threshold-based (threat_score >= 55). Templates: "New {alert_type} for {entity_text}: {message}". Auto-generated from event intelligence when threat score exceeds hardcoded threshold. |
| **Current Limitations** | Simple threshold triggers. No ML-based anomaly detection. No alert correlation. No alert prioritization learning. No natural language alert descriptions. |
| **What AI replaces** | **Alert generation.** LLM can analyze multiple signals and generate contextual alerts. **Alert correlation.** LLM can group related alerts. **Alert prioritization.** Learned from past alert outcomes. |
| **What AI augments** | **Alert description.** LLM generates rich alert narratives. **Alert triage.** LLM recommends response actions. **Auto-response.** Agent can take predefined actions for known alert patterns. |
| **What stays deterministic** | Alert storage, status management, user notification. |
| **Expected improvement** | From threshold-based alerts to AI-powered intelligent alerting with correlation and triage. |
| **Difficulty** | Medium |
| **Hackathon impact** | Medium — visible but not headline |

### 2.9 Reports (backend/api/reports/) — AI Maturity: 3/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | CRUD reports. Generate from case (aggregates case data). Template-based structure (executive_summary, key_actors, key_events, threat_assessment, recommendations). |
| **Current Logic** | Report generation collects case items and formats into predefined JSON structure. No natural language generation. Content is concatenated from source data. |
| **Current Limitations** | Template-driven. No natural language. No insightful analysis. No executive-quality writing. |
| **What AI replaces** | **Report generation.** LLM generates full intelligence reports from case data with natural language. Executive summary, threat assessment, and recommendations all LLM-generated. |
| **What AI augments** | **Report formatting.** Markdown/HTML export. **Executive brief.** Condensed version for executives. |
| **What stays deterministic** | Report storage and retrieval. Case-to-report data aggregation. |
| **Expected improvement** | From template data dumps to professionally written intelligence reports. |
| **Difficulty** | Low |
| **Hackathon impact** | Medium — good for the "executive decision support" criterion |

### 2.10 Frontend — AI Maturity: 1/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | 28 pages, React 18 + TanStack Query + shadcn/ui. Copilot page shows rule-based responses. All pages are static/dashboard-style. |
| **Current Limitations** | No AI anywhere in the frontend. Copilot page sends query → receives JSON → renders. No chat UI with streaming. No AI-generated visualizations. No natural language input across pages. |
| **What AI replaces** | **Copilot page.** Replace JSON display with full chat UI (streaming markdown, citations, follow-up suggestions). |
| **What AI augments** | **Natural language input on every page.** "Show me high-risk refineries" triggers filter + LLM interpretation. **Chat overlay.** Floating AI assistant on every page. **AI summaries.** AI-generated page summaries. |
| **What stays deterministic** | Dashboard layouts, charts, filters, CRUD forms. |
| **Expected improvement** | From traditional dashboard to AI-native interface with chat, natural language, and intelligent assistance everywhere. |
| **Difficulty** | Medium |
| **Hackathon impact** | **GAME-CHANGER** — an AI-native UI is the most visible improvement |

### 2.11 Analytics (backend/api/analytics/) — AI Maturity: 4/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | 8 endpoints returning aggregate statistics (dashboard, threat-trends, summary, graph, timeseries, entities, topics). Dashboard-v2 is a duplicate. |
| **Current Logic** | SQL aggregate queries: COUNT, AVG, GROUP BY, ORDER BY. Sentiment distribution counts. Topic frequency. Entity mention counts. |
| **Current Limitations** | Purely descriptive (what happened). No predictive (what will happen). No prescriptive (what to do). No natural language explanation of trends. |
| **What AI replaces** | **Trend explanation.** LLM interprets analytics data and explains trends. **Anomaly detection.** ML detects unusual patterns. |
| **What AI augments** | **Narrative analytics.** "Last week, risk scores increased 15% primarily due to..." **Drill-down recommendations.** "You should investigate these 3 entities driving the trend." |
| **What stays deterministic** | The aggregate SQL queries. Chart data. Trend computation. |
| **Expected improvement** | From descriptive dashboards to AI-powered analytical narratives. |
| **Difficulty** | Low-Medium |
| **Hackathon impact** | Medium — visible in the analytics page |

### 2.12 ML Service (services/ml-service/) — AI Maturity: 5/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | Transformers DistilBERT sentiment + BERT-large NER + spaCy fallback. Heuristic topic/threat/relationships/summarization. Kafka consumer. |
| **Current Logic** | Sentiment: `pipeline(text[:1000])` → POSITIVE/NEGATIVE/heuristic neutral. NER: `ner_pipeline(text[:1200])` → LOC/ORG/PER/MISC > 0.70. Topic: bag-of-words keyword counting (war/diplomacy/economics/cyber). Threat: `0.40×topic_score + 0.30×sentiment_score + 0.20×entity_count + 0.10×length_factor`. Relationships: entity pairing + keyword matching. |
| **Current Limitations** | Topic is keyword counting (0% ML). Threat is weighted formula (0% ML). Relationship extraction is pairing + keywords (0% ML). Summarization is first-2-sentences (0% ML). |
| **What AI replaces** | **Topic classification.** Replace keyword counting with zero-shot classification (BART/MNLI) or fine-tuned classifier. **Threat scoring.** Replace formula with learned ML model. **Relationship extraction.** Replace heuristic with LLM-based extraction. **Summarization.** Replace first-2-sentences with BART/LED abstractive summarization. |
| **What AI augments** | NER quality can improve with better models. Sentiment can expand to multi-class (including neutral properly). |
| **What stays deterministic** | The Kafka consumer infrastructure. The database writes. The pipeline orchestration. |
| **Expected improvement** | From 3/8 AI components to 8/8 AI components. |
| **Difficulty** | Medium |
| **Hackathon impact** | Medium — internal improvement, visible in data quality |

### 2.13 Embedding Service (services/embedding-service/) — AI Maturity: 6/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | bge-small-en-v1.5 via fastembed. pgvector storage. Semantic search endpoint. Kafka consumer. |
| **Current Logic** | `embed_text()` → list(model.embed([text]))[0] → pgvector INSERT. Search: `<=>` cosine distance, top 5. |
| **Current Limitations** | One embedding model fits all (articles). No query-side embedding optimization. No document chunking strategy. Fixed 384d (may lose nuance for complex docs). Consumer has undefined variable bug. |
| **What AI replaces** | **Document chunking.** Add intelligent chunking (semantic boundaries, not fixed length). **Multi-vector indexing.** Embed different content types with different strategies. |
| **What AI augments** | **Query rewriting.** LLM rewrites queries before embedding. **Hybrid fusion.** Combine dense + sparse results. |
| **What stays deterministic** | The embedding model itself. The vector database. The ANN search. |
| **Expected improvement** | Better retrieval quality for RAG. |
| **Difficulty** | Low |
| **Hackathon impact** | Low — invisible foundation work |

### 2.14 Database Service (services/database-service/) — AI Maturity: 2/10

| Aspect | Detail |
|--------|--------|
| **Current Architecture** | Kafka consumer → PostgreSQL upsert + event clustering + energy enrichment + ES indexing. |
| **Current Logic** | Event clustering: entity overlap ≥2 + topic match + 7-day window + text similarity ≥0.60. Energy enrichment: LOWER()+LIKE matching against 14 entity tables. Alert generation: threat_score ≥ 55. |
| **Current Limitations** | Event clustering thresholds are hardcoded. Entity matching is basic text matching (no semantic). Alert threshold is arbitrary. |
| **What AI replaces** | **Event clustering.** LLM can determine if articles describe the same event with semantic understanding. **Entity matching.** Embedding similarity can replace LIKE matching. |
| **What AI augments** | **Enrichment quality.** LLM can verify and enrich entity matches. **Alert relevance.** LLM can filter false-positive alerts. |
| **What stays deterministic** | Database writes. Elasticsearch indexing. Kafka consumption. |
| **Expected improvement** | Better data quality flowing into every downstream system. |
| **Difficulty** | Medium (LLM in consumer adds latency) |
| **Hackathon impact** | Low — invisible infrastructure |

---

## 3. Agent Architecture

### 3.1 Complete Agent Ecosystem

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SUPERVISOR AGENT (Orchestrator)                   │
│  Routes requests, manages context, coordinates specialist agents     │
│  Maintains shared memory, resolves conflicts, sets priorities        │
└───────────────────────┬─────────────────────────────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Intelligence  │ │  Scenario    │ │  Procurement │ │  SPR         │
│    Agent      │ │    Agent     │ │    Agent     │ │    Agent     │
├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ Search news   │ │ Run sims     │ │ Optimize     │ │ Release plan │
│ Risk analysis │ │ Gen scenarios│ │ Supplier mgmt│ │ Refill plan  │
│ Threat assess │ │ Flow analysis│ │ Cost optimize │ │ Policy eval  │
│ Entity track  │ │ Impact report│ │ Route select │ │ Timeline     │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Knowledge     │ │  Executive   │ │  Geospatial  │ │  Prediction  │
│  Graph Agent  │ │ Brief Agent  │ │    Agent     │ │    Agent     │
├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ Graph queries │ │ Gen reports  │ │ Map analysis │ │ ML inference │
│ Entity res.   │ │ Exec summary │ │ Route viz    │ │ Risk predict │
│ Relat. infer  │ │ Card gen     │ │ Hotspot find │ │ Gap predict  │
│ Graph enrich  │ │ Export docs  │ │ Distance calc│ │ Price pred   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  RAG Agent   │ │  Research    │ │  Validation  │
│              │ │    Agent     │ │    Agent     │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ Retrieve docs│ │ Deep analysis│ │ Fact-check   │
│ Context wins │ │ Compare cases│ │ Consistency  │
│ Citation gen │ │ Hypotheticals│ │ Source verify│
│ Re-ranking   │ │ What-if Q&A  │ │ Confidence   │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 3.2 Agent Definitions

#### 3.2.1 Supervisor Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Orchestrate all specialist agents. Route requests, manage context, resolve conflicts, maintain shared state. |
| **Inputs** | User query, system events, alert triggers, scheduled tasks |
| **Outputs** | Routed subtasks, merged responses, escalation decisions |
| **LLM** | GPT-4o (primary), Claude 3.5 Sonnet (fallback for complex reasoning) |
| **Memory** | Short-term: conversation context (last 50 messages). Long-term: vector store of past decisions and outcomes |
| **Tools** | `route_to_agent(agent_name, task)`, `get_agent_status(agent_name)`, `resolve_conflict(agent_a, agent_b)`, `escalate_to_human(task, reasoning)` |
| **RAG** | Yes — retrieval of past decisions, policies, reference data |
| **Complexity** | High — the most architecturally complex agent |
| **When invoked** | Every user query, every system event, every scheduled analysis |

#### 3.2.2 Intelligence Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Monitor, analyze, and report on geopolitical risk intelligence. The "eyes and ears" of the system. |
| **Inputs** | News articles (from processed_articles), entity profiles, disruption signals, risk scores |
| **Outputs** | Threat assessments, risk narratives, entity reports, trend analyses, anomaly alerts |
| **LLM** | GPT-4o |
| **Memory** | Recent article summaries, tracked entity states, signal history |
| **Tools** | `search_articles(query, filters)`, `get_entity_profile(entity_name)`, `list_active_signals()`, `get_risk_trends(days)`, `get_commodity_prices(commodity)`, `evaluate_scenario(params)` |
| **RAG** | Yes — retrieve relevant articles, historical events, entity profiles |
| **KG** | Yes — traverse entity relationships for context |
| **Digital Twin** | No direct access (routes through Scenario Agent) |
| **Complexity** | Medium |
| **When invoked** | User asks about threats, news analysis, scheduled monitoring |

#### 3.2.3 Scenario Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Design, execute, and analyze Digital Twin simulation scenarios. Translate natural language to simulation parameters. |
| **Inputs** | Natural language scenario description, risk signals, historical disruption data |
| **Outputs** | Simulation results, impact narratives, comparison analyses, mitigation recommendations |
| **LLM** | GPT-4o (for scenario design and analysis), deterministic engine for simulation execution |
| **Memory** | Recent simulation results, scenario templates, comparison baselines |
| **Tools** | `create_scenario(name, config)`, `run_simulation(scenario_uuid, ticks)`, `get_simulation_results(run_uuid)`, `compare_runs(run_uuids)`, `get_flow_state(run_uuid, tick)`, `list_scenario_templates()` |
| **RAG** | Yes — retrieve historical scenarios and their outcomes |
| **Digital Twin** | **YES — primary user** |
| **Procurement** | Routes to Procurement Agent when supply gap detected |
| **SPR** | Routes to SPR Agent when reserve impact detected |
| **Complexity** | High — bridges natural language and deterministic simulation |
| **When invoked** | User describes a scenario, risk signal triggers simulation, scheduled stress testing |

#### 3.2.4 Procurement Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Optimize procurement decisions, manage supplier relationships, and ensure supply continuity. |
| **Inputs** | Supply gap (from simulation), optimization parameters, supplier intelligence, route costs |
| **Outputs** | Procurement plans, supplier recommendations, cost analyses, executive cards |
| **LLM** | GPT-4o (for explanation and narrative), deterministic optimizer for core computation |
| **Memory** | Recent procurement runs, supplier performance history, contract terms |
| **Tools** | `run_procurement_orchestrator(params)`, `get_supplier_profile(uuid)`, `find_alternative_suppliers(supplier, commodity)`, `get_route_costs(origin, dest)`, `get_executive_cards(run_uuid)`, `acknowledge_card(card_uuid)` |
| **RAG** | Yes — retrieve supplier intelligence, past procurement outcomes |
| **Digital Twin** | Receives supply gap from Scenario Agent |
| **Complexity** | Medium |
| **When invoked** | Supply gap detected, user requests procurement plan, scheduled rebalancing |

#### 3.2.5 SPR Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Manage Strategic Petroleum Reserve: release planning, refill scheduling, policy optimization. |
| **Inputs** | Supply gap, disruption timeline, current reserve status, policy constraints |
| **Outputs** | Release plans, refill schedules, decision timelines, policy recommendations |
| **LLM** | GPT-4o (for strategy recommendation and narrative) |
| **Memory** | Recent SPR runs, policy history, release outcomes |
| **Tools** | `run_spr_analysis(params)`, `get_spr_facilities()`, `get_spr_inventory()`, `get_spr_policies()`, `get_spr_run(uuid)`, `list_spr_runs()` |
| **RAG** | Yes — retrieve strategic reserve policies, historical release data |
| **Procurement** | Coordinates with Procurement Agent for refill procurement |
| **Complexity** | Medium |
| **When invoked** | Supply crisis detected, user requests reserve analysis, scheduled reserve review |

#### 3.2.6 Knowledge Graph Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Answer natural language questions about the knowledge graph. Traverse relationships, discover paths, explain connections. |
| **Inputs** | Natural language graph queries, entity names, relationship types |
| **Outputs** | Graph traversal explanations, entity connections, path discoveries, relationship inferences |
| **LLM** | GPT-4o (for NL→graph-query translation and result explanation) |
| **Memory** | Graph query history, frequent entity resolutions |
| **Tools** | `query_graph(entity, depth)`, `find_path(source, target)`, `get_entity_relationships(entity)`, `get_network_graph(node_type)`, `get_entity_profile(name)`, `resolve_entity(alias)` |
| **RAG** | Yes — retrieve entity descriptions and context |
| **KG** | **YES — primary user of all 3 graph layers** |
| **Complexity** | Medium-High — requires understanding graph structure and translating NL |
| **When invoked** | User asks about relationships, entity connections, supply chain paths |

#### 3.2.7 Executive Brief Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Generate executive-quality briefings, reports, and decision support materials. |
| **Inputs** | Data from all other agents: risk assessment, simulation results, procurement plans, SPR status |
| **Outputs** | Executive summaries, intelligence reports, decision briefs, recommended actions |
| **LLM** | GPT-4o — requires best-in-class writing quality |
| **Memory** | Generated reports, executive preferences, briefing templates |
| **Tools** | `generate_report(title, sections)`, `get_reports()`, `get_executive_cards()`, `get_simulation_results(uuid)`, `get_risk_dashboard()` |
| **RAG** | Yes — retrieve supporting data for every claim in the report |
| **Complexity** | Medium |
| **When invoked** | User requests briefing, scheduled report generation, post-simulation analysis |

#### 3.2.8 Geospatial Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Answer geospatial questions, analyze spatial patterns, visualize geographic data. |
| **Inputs** | Location names, coordinates, region queries |
| **Outputs** | Spatial analysis, proximity calculations, map data, regional risk assessments |
| **LLM** | GPT-4o (for spatial reasoning and explanation) |
| **Memory** | Recent spatial queries, location cache |
| **Tools** | `get_entity_by_location(lat, lng, radius)`, `find_nearby_infrastructure(lat, lng, type, radius)`, `get_shipping_routes(port_a, port_b)`, `calculate_distance(loc_a, loc_b)`, `get_region_risk(region_name)` |
| **RAG** | Yes — retrieve location descriptions and context |
| **KG** | Yes — traverse location-based relationships |
| **Complexity** | Low-Medium |
| **When invoked** | User asks about locations, spatial patterns, route analysis |

#### 3.2.9 RAG Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Retrieve, rank, and present relevant information from all indexed sources. The retrieval backbone for all other agents. |
| **Inputs** | Query (natural language or embedding), filters (date, source, type), top_k |
| **Outputs** | Ranked results with relevance scores, source citations, context windows |
| **LLM** | Not directly (uses embedding model + cross-encoder + optional LLM query rewriting) |
| **Memory** | Query cache, frequently accessed documents |
| **Tools** | `hybrid_search(query, filters, top_k)`, `semantic_search(query, top_k)`, `keyword_search(query, filters)`, `rerank_results(query, results)`, `get_document_by_id(id)`, `get_context_window(doc_id, query)` |
| **RAG** | **YES — the RAG Agent IS the RAG system** |
| **Complexity** | Medium |
| **When invoked** | Every agent queries RAG Agent for context retrieval |

#### 3.2.10 Prediction Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Run ML inference, return predictions with confidence scores and feature importance. |
| **Inputs** | Feature vectors, entity identifiers, prediction type |
| **Outputs** | Predictions, confidence scores, feature importance, SHAP explanations |
| **LLM** | No — uses trained ML models via ML Platform |
| **Memory** | Prediction cache model |
| **Tools** | `predict_risk(entity_uuid)`, `predict_supply_gap(region, days)`, `predict_price(commodity, days)`, `predict_refinery_utilization(refinery_uuid)` |
| **RAG** | No |
| **Complexity** | Medium (requires trained models) |
| **When invoked** | Risk assessment, supply gap analysis, price forecasting |

#### 3.2.11 Research Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Conduct deep research: compare historical cases, analyze hypothetical scenarios, explore what-ifs. |
| **Inputs** | Research question, constraints, depth parameters |
| **Outputs** | Research report, comparative analysis, hypothetical outcomes |
| **LLM** | Claude 3.5 Sonnet (best for deep analysis and long-form reasoning) |
| **Memory** | Research session context, findings summary |
| **Tools** | All tools from Intelligence, Scenario, Knowledge Graph, and RAG agents |
| **RAG** | Yes — extensive retrieval for comprehensive research |
| **Complexity** | High — orchestrates multiple subsystems |
| **When invoked** | User asks deep analytical questions, comparative analysis, "what if we had done X" |

#### 3.2.12 Validation Agent

| Field | Specification |
|-------|--------------|
| **Purpose** | Fact-check, verify sources, assess confidence, detect inconsistencies. The system's "critic." |
| **Inputs** | Claims, generated content, decisions from other agents |
| **Outputs** | Confidence scores, source citations, inconsistency reports, correction suggestions |
| **LLM** | Claude 3.5 Sonnet (stronger at critical analysis) |
| **Memory** | Validation history, known facts database |
| **Tools** | `verify_claim(claim)`, `check_consistency(doc_a, doc_b)`, `assess_confidence(claim, sources)`, `find_contradictions(text)` |
| **RAG** | Yes — retrieve supporting/contradicting evidence |
| **Complexity** | Medium-High |
| **When invoked** | After any agent generates critical output, before executive briefing delivery |

### 3.3 Agent Communication Protocol

```
Request Flow:
┌─────────┐     ┌──────────┐     ┌──────────┐
│  User   │────▶│Supervisor│────▶│Specialist│
│ Query   │     │  Agent   │     │  Agent   │
└─────────┘     └────┬─────┘     └────┬─────┘
                     │                │
                     │ 1. Analyze     │ 2. Execute tools
                     │    intent      │ 3. Query RAG Agent
                     │ 2. Route to    │ 4. Query KG Agent
                     │    specialist  │ 5. Return results
                     │ 3. Merge resp  │
                     │ 4. Validate    │
                     └────────────────┘

Cross-Agent Communication:
Specialist Agent A ──(subtask)──▶ Supervisor ──(route)──▶ Specialist Agent B
                                     │
                              (results merged)

Critique Flow:
Specialist Agent ──(output)──▶ Validation Agent ──(corrections)──▶ Back to Agent
                                     │
                              (or escalate to supervisor)

Memory Flow:
Any Agent ──(read/write)──▶ Shared Vector Store (past decisions, outcomes, context)
```

### 3.4 Shared Memory Architecture

| Memory Store | Content | Access | Persistence |
|-------------|---------|--------|-------------|
| **Conversation Memory** | Recent interactions per session | All agents (read), Supervisor (write) | Session (redis/volatile) |
| **Decision Store** | Past decisions, outcomes, justifications | All agents (read), Any (write) | PostgreSQL (permanent) |
| **Agent State** | Current status, active tasks, results | Supervisor (read/write) | In-memory + Redis |
| **Tool Cache** | Recent tool outputs, API responses | All agents (read), RAG Agent (write) | Redis (TTL-based) |
| **Knowledge Base** | Indexed documents, entities, relationships | All agents via RAG Agent | pgvector + ES (permanent) |

---

## 4. Tool Architecture

### 4.1 Complete Tool Inventory

Every tool maps to existing API endpoints. No new backend endpoints are needed (all data operations already exist).

#### Category: Search & Retrieval

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `search_articles` | GET /articles | query, sentiment, topic, risk_level, limit, offset | Article[] | Intelligence, RAG, Research |
| `search_semantic` | GET /semantic-search | query, top_k | {results: Article[], similarity_scores} | RAG, Intelligence |
| `search_fulltext` | GET /search | query, filters | {results, total} | RAG, Intelligence |
| `get_article` | GET /articles/{id} | article_id | Article | Intelligence, RAG |
| `get_article_entities` | GET /articles/{id}/entities | article_id | Entity[] | Intelligence, KG |

#### Category: Knowledge Graph

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `query_knowledge_graph` | GET /graph/network | entity, depth, limit | {nodes, edges} | KG, Intelligence, Research |
| `expand_entity_graph` | GET /graph/{entity} | entity_name, depth, limit | {nodes, edges} | KG, Research |
| `get_entity_profile` | GET /entities/{entity_name} | entity_name | EntityProfile | Intelligence, KG |
| `get_entity_relationships` | GET /entities/{entity_name}/relationships | entity_name | Relationship[] | KG, Research |
| `get_energy_network` | GET /api/v1/energy/graph/network | table, uuid | {nodes, edges} | KG, Scenario, Geospatial |
| `find_path` | GET /api/v1/intelligence/digital-twin/network/path | from_node, to_node | {path, distance} | KG, Scenario, Geospatial |
| `get_downstream` | GET /.../network/downstream/{node_id} | node_id | Edge[] | Scenario, KG |
| `get_upstream` | GET /.../network/upstream/{node_id} | node_id | Edge[] | Scenario, KG |
| `get_dependencies` | GET /.../network/dependencies/{node_id} | node_id, depth | Node[] | Scenario, KG |

#### Category: Risk Intelligence

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `get_risk_dashboard` | GET /api/v1/intelligence/risk | none | RiskDashboard | Intelligence, Executive |
| `score_entity` | GET /api/v1/intelligence/risk/entity/{uuid} | entity_uuid, entity_type | RiskScore | Intelligence, Prediction |
| `get_risk_trends` | GET /api/v1/intelligence/risk/trends | days | TimeSeries[] | Intelligence, Executive |
| `list_signals` | GET /api/v1/intelligence/signals | severity, dimension, status, limit | Signal[] | Intelligence, Supervisor |
| `create_signal` | POST /api/v1/intelligence/signals | title, description, source, severity | Signal | Intelligence, Supervisor |
| `evaluate_scenario` | POST /api/v1/intelligence/scenarios/evaluate | scenario_params | ScenarioEvaluation | Intelligence, Research |
| `list_risk_factors` | GET /api/v1/intelligence/risk-factors | none | RiskFactor[] | Intelligence |
| `get_commodity_prices` | GET /api/v1/intelligence/commodity-prices | commodity_family | Price[] | Intelligence, Prediction |
| `get_port_congestion` | GET /api/v1/intelligence/port-congestion | port_name | Congestion[] | Intelligence, Geospatial |
| `get_tanker_availability` | GET /api/v1/intelligence/tanker-availability | vessel_type | Tanker[] | Intelligence, Procurement |
| `get_sanctions` | GET /api/v1/intelligence/sanctions | country_code | Sanctions[] | Intelligence, Procurement |
| `propagate_risk` | POST /api/v1/intelligence/propagate | entity_uuid | PropagationMap | Intelligence |
| `get_entity_risk_profile` | GET /.../entity/{table}/{uuid}/risk-profile | entity_table, entity_uuid | RiskProfile | Intelligence |

#### Category: Digital Twin & Simulation

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `build_network` | POST /.../digital-twin/network/build | none | {nodes, edges} | Scenario |
| `get_network_graph` | GET /.../digital-twin/network | node_type | NetworkGraph | Scenario, Geospatial |
| `list_scenarios` | GET /.../digital-twin/scenarios | is_template | Scenario[] | Scenario, Research |
| `create_scenario` | POST /.../digital-twin/scenarios | name, config, assumptions | Scenario | Scenario |
| `run_simulation` | POST /.../digital-twin/run | scenario_uuid, name, ticks | SimulationRun | Scenario |
| `get_simulation_run` | GET /.../digital-twin/runs/{uuid} | run_uuid | SimulationRun | Scenario, Executive |
| `get_run_timeline` | GET /.../digital-twin/runs/{uuid}/timeline | run_uuid | Timeline[] | Scenario, Executive |
| `get_run_impacts` | GET /.../digital-twin/runs/{uuid}/impacts | run_uuid | ImpactReport | Scenario, Executive |
| `get_run_flows` | GET /.../digital-twin/runs/{uuid}/flows | run_uuid | FlowState[] | Scenario |
| `compare_runs` | GET /.../digital-twin/compare | run_uuids | ComparisonReport | Scenario, Executive |
| `get_demand_profiles` | GET /.../digital-twin/demand | none | DemandProfile[] | Scenario, SPR |
| `get_recommendations` | GET /.../digital-twin/recommendations | run_uuid | Recommendation[] | Scenario, Executive |
| `estimate_baseline_flows` | POST /.../digital-twin/flows/estimate-baseline | none | FlowState[] | Scenario |
| `list_simulation_runs` | GET /.../digital-twin/runs | status | SimulationRun[] | Scenario |
| `delete_run` | DELETE /.../digital-twin/runs/{uuid} | run_uuid | status | Scenario |

#### Category: Procurement

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `list_suppliers` | GET /.../procurement/suppliers | none | Supplier[] | Procurement |
| `get_supplier_profile` | GET /.../procurement/suppliers/{uuid} | supplier_uuid | SupplierProfile | Procurement |
| `find_alternative_suppliers` | GET /.../procurement/suppliers/{uuid}/alternatives | supplier_uuid, commodity_uuid | Alternative[] | Procurement |
| `get_compatibility` | GET /.../procurement/compatibility | refinery_uuid, commodity_uuid, min_score | Compatibility[] | Procurement |
| `get_route_costs` | GET /.../procurement/routes | origin_node_id, dest_node_id | RouteCost[] | Procurement, Scenario |
| `run_procurement_optimization` | POST /.../procurement/optimize | supply_gap, commodity, goal, max_cost, max_risk | OptimizationResult | Procurement |
| `run_procurement_orchestration` | POST /.../procurement/run | simulation_run_uuid, supply_gap, goal | ProcurementRun | Procurement |
| `list_procurement_runs` | GET /.../procurement/runs | status, limit | ProcurementRun[] | Procurement, Executive |
| `get_procurement_run` | GET /.../procurement/runs/{uuid} | run_uuid | ProcurementRun | Procurement, Executive |
| `get_executive_cards` | GET /.../procurement/executive-cards | severity, category | ExecutiveCard[] | Executive, Procurement |
| `get_recommendations` | GET /.../procurement/recommendations | run_uuid, priority | Recommendation[] | Procurement, Executive |

#### Category: SPR

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `get_spr_facilities` | GET /.../procurement/spr/facilities | none | SPRFacility[] | SPR |
| `get_spr_inventory` | GET /.../procurement/spr/inventory | facility_uuid, limit | Inventory[] | SPR |
| `get_spr_policies` | GET /.../procurement/spr/policies | none | SPRPolicy[] | SPR |
| `create_spr_policy` | POST /.../procurement/spr/policies | name, threshold, max_rate | SPRPolicy | SPR |
| `compute_spr_demand` | GET /.../procurement/spr/demand | none | DemandReport | SPR |
| `run_spr_analysis` | POST /.../procurement/spr/analyze | disruption, days, gap, strategy, policy | SPRRun | SPR |
| `list_spr_runs` | GET /.../procurement/spr/runs | limit | SPRRun[] | SPR, Executive |
| `get_spr_run` | GET /.../procurement/spr/runs/{uuid} | run_uuid | SPRRun | SPR, Executive |
| `acknowledge_spr_card` | POST /.../procurement/spr/executive-cards/{uuid}/ack | card_uuid | status | Executive |

#### Category: Energy Catalog

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `list_energy_entities` | GET /api/v1/energy/{table} | table, search, status, criticality, limit | Entity[] | All |
| `get_energy_entity` | GET /api/v1/energy/{table}/{uuid} | table, uuid | Entity | All |
| `get_energy_relationships` | GET /.../energy/{table}/{uuid}/relationships | table, uuid | Relationship[] | KG, Geospatial |
| `get_entity_events` | GET /.../energy/{table}/{uuid}/events | table, uuid | InfrastructureEvent[] | Intelligence |
| `get_capacity_history` | GET /.../energy/{table}/{uuid}/history | table, uuid | CapacityHistory[] | Prediction |

#### Category: Analytics & Monitoring

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `get_dashboard_stats` | GET /analytics/dashboard-v2 | none | DashboardV2 | Executive, Intelligence |
| `get_analytics_summary` | GET /analytics/summary | none | AnalyticsSummary | Executive, Intelligence |
| `get_threat_trends` | GET /analytics/threat-trends | none | ThreatAnalytics | Intelligence, Executive |
| `get_timeseries` | GET /analytics/timeseries | none | TimeSeriesPoint[] | Intelligence |
| `get_entity_insights` | GET /analytics/entities | none | EntityInsight[] | Intelligence |
| `get_topic_breakdown` | GET /analytics/topics | none | TopicBreakdown[] | Intelligence |

#### Category: Copilot & Intelligence

| Tool Name | Backend Endpoint | Inputs | Outputs | Agent Users |
|-----------|-----------------|--------|---------|-------------|
| `query_copilot` | POST /copilot/query | question | CopilotResponse | All (replaced by agent system) |
| `get_alerts` | GET /alerts | status, limit | Alert[] | Intelligence, Supervisor |
| `list_events` | GET /events | limit, offset | Event[] | Intelligence |
| `get_event` | GET /events/{id} | event_id | EventDetails | Intelligence |

---

## 5. RAG Architecture

### 5.1 What Should Be Indexed

| Index | Source Data | Chunking Strategy | Embedding Model | Filter Fields | Update Frequency |
|-------|-------------|-------------------|-----------------|---------------|-----------------|
| **News Articles** | processed_articles | 512-token sliding window with 64-token overlap | bge-large-en-v1.5 (upgrade from bge-small) | date, sentiment, risk_level, topic, source | Real-time (Kafka) |
| **Infrastructure Assets** | energy.* (14 entity tables) | Entity-level (no chunking — atomic) | bge-large-en-v1.5 | type, country, status, criticality | On seed/update |
| **Relationships** | public.relationships + energy.entity_relationships | Relationship triple (source, type, target) | bge-large-en-v1.5 | source_type, target_type, confidence | On insert |
| **Simulation Results** | digital_twin_runs + flow_states + impacts | Per-run summary + per-impact detail | bge-large-en-v1.5 | scenario, status, date | On simulation completion |
| **Procurement Runs** | procurement_runs + recommendations | Per-run summary + per-recommendation | bge-large-en-v1.5 | status, goal, date | On run completion |
| **SPR Runs** | spr_release_runs + spr_recommendations | Per-run summary + per-card | bge-large-en-v1.5 | strategy, policy, date | On analysis completion |
| **Executive Decisions** | executive_recommendations | Per-card with context | bge-large-en-v1.5 | severity, category, acknowledged | On creation |
| **Risk Scores** | energy.risk_scores + risk_factors | Per-entity profile + per-dimension trend | bge-large-en-v1.5 | dimension, entity_type, date | On scoring |
| **Disruption Signals** | energy.disruption_signals | Per-signal with metadata | bge-large-en-v1.5 | severity, dimension, source | On creation |
| **Policies** | spr_policy_constraints | Per-policy (minimal — already atomic) | bge-large-en-v1.5 | is_active, type | On change |
| **Alerts** | alerts | Per-alert with context | bge-large-en-v1.5 | status, alert_type, risk_score | On generation |

### 5.2 Retrieval Strategy

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│           Query Processing Layer              │
│  1. LLM rewrites/expands query               │
│  2. Extract entities for KG traversal         │
│  3. Identify intent → select indices         │
│  4. Generate filter predicates               │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌──────────────┐ ┌──────────────┐
│  Dense Path  │ │  Sparse Path │
│  pgvector    │ │  Elastic     │
│  cosine_dist │ │  BM25        │
│  top_k=50    │ │  top_k=50    │
└──────┬───────┘ └──────┬───────┘
       │                │
       └───────┬───────┘
               ▼
┌──────────────────────────────────────────────┐
│           Fusion Layer                        │
│  Reciprocal Rank Fusion (RRF)                 │
│  k=60 constant                                │
│  Weight: dense=0.5, sparse=0.3, KG=0.2       │
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│           Cross-Encoder Re-ranking            │
│  bge-reranker-v2-m3                           │
│  Re-rank top 60 → top 15                     │
│  Add relevance scores                         │
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│           Context Assembly                    │
│  1. Deduplicate results                      │
│  2. Order by relevance                       │
│  3. Build context window                     │
│  4. Add source citations                     │
│  5. Add confidence scores                    │
│  6. Return to calling agent                  │
└──────────────────────────────────────────────┘
```

### 5.3 Hybrid Search Integration

The RAG Agent exposes a single `hybrid_search()` tool that:

1. **Dense retrieval**: `pgvector <=> cosine distance` on all indices
2. **Sparse retrieval**: Elasticsearch `multi_match` with per-field boosts
3. **KG expansion**: Extract entities → traverse relationships → add connected entities to results
4. **RRF fusion**: Reciprocal Rank Fusion with tunable weights
5. **Cross-encoder re-ranking**: bge-reranker-v2-m3 scores top 60 → return top 15
6. **Filter application**: Date ranges, risk levels, entity types, sources

### 5.4 Index Management

Each index type has an `_index_metadata` table tracking:
- Last indexed timestamp
- Total document count
- Index version
- Embedding model version
- Re-index required flag

Incremental indexing triggers:
- Kafka message → embedding service → update index
- Simulation completion → update index
- Procurement run → update index
- SPR analysis → update index

Full re-index: Scheduled or on-demand via admin endpoint.

---

## 6. ML Architecture

### 6.1 Predictive Models

#### Model 1: Predictive Risk Scoring

| Aspect | Specification |
|--------|---------------|
| **Problem** | Replace heuristic risk score (weighted formula) with ML-predicted risk |
| **Target** | Risk score (0-1) for entity/disruption |
| **Features** | Historical signals count, commodity price volatility, sanctions count, port congestion %, tanker availability %, news sentiment (30d avg), geopolitical event count, entity criticality, supply chain depth, past disruption frequency |
| **Training Data** | Historical risk_scores, disruption_signals, commodity_prices, news articles, entity attributes from energy schema |
| **Model** | XGBoost Regressor (best for tabular data with mixed feature types) |
| **Evaluation** | RMSE, MAE, R², calibration curve |
| **Inference** | POST /api/v1/ml/predict (model_name="risk_predictor") |
| **Integration** | RiskScoringEngine calls ML Bridge → ML Platform → returns ML score alongside heuristic score |
| **Priority** | **HIGH** — visible improvement to risk intelligence |

#### Model 2: Supply Gap Prediction

| Aspect | Specification |
|--------|---------------|
| **Problem** | Predict supply gap magnitude during disruptions |
| **Target** | supply_gap_bpd (regression) |
| **Features** | Disruption severity, affected node capacity, node degree centrality, alternative route capacity, inventory levels, historical gap duration, seasonality, global price |
| **Training Data** | Digital Twin simulation runs (completed), historical disruption data |
| **Model** | Random Forest Regressor (handles non-linearity well) |
| **Evaluation** | RMSE, MAPE, R², prediction intervals |
| **Inference** | POST /api/v1/ml/predict (model_name="supply_gap_predictor") |
| **Integration** | Digital Twin simulation → ML prediction → compare with simulated gap |
| **Priority** | **MEDIUM** — requires simulation run data to train |

#### Model 3: Crude Price Direction

| Aspect | Specification |
|--------|---------------|
| **Problem** | Predict short-term crude price direction (up/down/flat) |
| **Target** | Price direction (classification: up/down/flat) for next 7 days |
| **Features** | Last 30 days price, volatility, inventory levels, disruption signals count, sanctions count, tanker rates, refinery utilization %, seasonality |
| **Training Data** | Historical commodity_prices + disruption_signals + sanctions |
| **Model** | XGBoost Classifier (multi-class) |
| **Evaluation** | Accuracy, F1, confusion matrix |
| **Inference** | POST /api/v1/ml/predict (model_name="price_predictor") |
| **Integration** | Procurement Agent uses for purchase timing, SPR Agent for release timing |
| **Priority** | **MEDIUM** — compelling but requires price history |

#### Model 4: Refinery Utilization Prediction

| Aspect | Specification |
|--------|---------------|
| **Problem** | Predict refinery throughput based on crude supply and disruption factors |
| **Target** | utilization_pct (regression) |
| **Features** | Refinery NCI, crude supply by type, disruption signals affecting supply, port congestion, pipeline status, seasonality, maintenance schedule |
| **Training Data** | Refinery profiles + simulation flows + disruption signals |
| **Model** | Gradient Boosting Regressor |
| **Evaluation** | RMSE, MAPE |
| **Inference** | POST /api/v1/ml/predict (model_name="refinery_utilization") |
| **Integration** | Risk Intelligence uses for refinery-specific risk |
| **Priority** | **LOW** — nice-to-have |

#### Model 5: Anomaly Detection

| Aspect | Specification |
|--------|---------------|
| **Problem** | Detect anomalous patterns in commodity prices, port congestion, tanker availability |
| **Target** | Anomaly score (0-1), is_anomaly (binary) |
| **Features** | Raw time-series values, z-scores, rolling averages, rate of change, seasonal residuals |
| **Training Data** | Historical commodity_prices, port_congestion, tanker_availability |
| **Model** | Isolation Forest + Statistical (z-score + IQR) ensemble |
| **Evaluation** | Precision@k, recall@k, F1 |
| **Inference** | POST /api/v1/ml/predict (model_name="anomaly_detector") |
| **Integration** | Alert generation, Intelligence Agent monitoring |
| **Priority** | **MEDIUM** — enhances alert quality |

### 6.2 Training Pipeline Execution

The existing ML Platform infrastructure (already built) needs to be executed:

1. **Run FeatureBuilder**: Compute features from Energy Service data
2. **Build Dataset**: EnergyServiceLoader → DatasetSplitter → parquet + DVC
3. **Train Models**: ModelTrainer for each model → MLflow → joblib dump
4. **Register Models**: model_versions table INSERT
5. **Optimize Hyperparameters**: Optuna or GridSearch for each model
6. **Evaluate**: Cross-validation, test set evaluation, SHAP explanations
7. **Promote**: Move best models to production stage
8. **Connect Inference**: Update ML Bridge to call ML Platform predict endpoint

---

## 7. LLM Architecture

### 7.1 Recommended LLM Strategy

| Tier | Provider | Model | Use Case | Why |
|------|----------|-------|----------|-----|
| **Primary** | OpenAI | **GPT-4o** | All agent reasoning, RAG generation, chat, tool calling | Best-in-class tool calling reliability. Fastest inference. Best API. Most hackathon-friendly. |
| **Secondary** | Anthropic | **Claude 3.5 Sonnet** | Research Agent, Validation Agent, long-form report generation | Superior at critical analysis and long-document reasoning. Excellent fallback for complex tasks. |
| **Fallback** | Ollama | **Llama 3 70B** / **Qwen 2.5 72B** | Offline demo mode, air-gapped environments | Zero API cost. Works without internet. Good enough quality for demo. |

**Architecture Decision**: GPT-4o as the primary LLM for ALL agents because:
1. **Tool calling** is the most reliable of any model — critical for agent ecosystem
2. **Speed** — fastest inference among frontier models
3. **API maturity** — best SDK, error handling, streaming support
4. **Context window** — 128K tokens sufficient for any RAG context
5. **Hackathon presentation** — most well-known, judges trust it
6. **Cost** — negligible for demo scale ($5-10 for entire hackathon)

### 7.2 Prompt Architecture

Every agent has a structured prompt template:

```
SYSTEM: You are {agent_name}, an AI agent in the ProxyDefence energy supply chain resilience platform.
Your role is {agent_purpose}.
You have access to the following tools: {tool_list}
You operate within these constraints: {constraints}
Your communication style: {style}

CONTEXT (from RAG):
{retrieved_documents}
{active_alerts}
{current_risk_status}

CONVERSATION HISTORY:
{last_N_messages}

CURRENT TASK:
{task_description}

AVAILABLE TOOLS:
{tool_schemas}

RESPONSE FORMAT:
{structured_output_schema}
```

### 7.3 Streaming Architecture

```
User Question
    │
    ▼
Supervisor Agent (streams: "Analyzing your question...")
    │
    ├──▶ Route to Intelligence Agent
    │       (streams: "Searching latest intelligence...")
    │       (streams: "Found 3 relevant articles about Hormuz...")
    │       (streams: "Running risk analysis...")
    │
    ├──▶ Route to Scenario Agent (if simulation needed)
    │       (streams: "Running Hormuz closure simulation...")
    │       (streams: "Tick 10/90: 15% supply gap detected...")
    │       (streams: "Tick 25/90: 40% supply gap, 3 refineries affected...")
    │
    ├──▶ Route to Procurement Agent (if procurement needed)
    │       (streams: "Optimizing procurement...")
    │       (streams: "Found 2 alternative suppliers...")
    │
    └──▶ Supervisor merges (streams: "Generating executive brief...")
            (streams: final answer with citations)
```

Each agent streams intermediate results via Server-Sent Events so the user sees progress.

### 7.4 Cost Optimization for Hackathon

| Strategy | Detail |
|----------|--------|
| **Tiered LLM** | GPT-4o for primary, switch to GPT-4o-mini for simple tasks (entity extraction, query rewriting) |
| **Context caching** | Cache frequent RAG contexts to reduce token usage |
| **Batch processing** | Non-real-time tasks (nightly reports) use cheaper models |
| **Streaming** | Always stream — reduces perceived latency by 3-5x |
| **Token budgeting** | Max 4000 output tokens per response, max 32000 context tokens |
| **Retry logic** | 3 retries with exponential backoff on API errors |

---

## 8. Multi-Agent Orchestration

### 8.1 Request Routing

```
User: "What's the current risk in the Strait of Hormuz?"

Supervisor Agent:
1. Intent classification: "geopolitical risk query about specific chokepoint"
2. Required agents: Intelligence (primary), RAG (supporting), KG (supporting)
3. Execution plan:
   a. RAG Agent: Retrieve recent articles about Hormuz
   b. KG Agent: Get entity profile for "Strait of Hormuz", find connected entities
   c. Intelligence Agent: Get risk dashboard, check signals for Hormuz region
   d. Supervisor: Merge results into coherent answer
4. Stream response to user
```

```
User: "Simulate a full blockade of the Strait of Hormuz for 60 days"

Supervisor Agent:
1. Intent classification: "simulation scenario with specific parameters"
2. Required agents: Scenario (primary), Intelligence (supporting), RAG (supporting), Executive (final)
3. Execution plan:
   a. RAG Agent: Retrieve past Hormuz-related scenarios and outcomes
   b. Intelligence Agent: Get current risk state of Hormuz region
   c. Scenario Agent: Create scenario, run simulation (90 ticks)
   d. Scenario Agent: Get impacts, timeline, flows
   e. IF supply_gap > 0: Route to Procurement Agent
   f. IF reserve_impact: Route to SPR Agent
   g. Executive Agent: Generate briefing
4. Stream each phase to user
5. Deliver final executive briefing
```

### 8.2 Conflict Resolution

When two agents provide conflicting assessments:

1. **Supervisor detects conflict** (e.g., Procurement says "risk is acceptable", SPR says "critical — release reserves")
2. Supervisor routes to **Validation Agent** for fact-checking
3. Validation Agent reviews evidence from both agents
4. If resolvable: Supervisor merges with confidence weighting
5. If unresolvable: Supervisor escalates to user with both perspectives and recommendation

### 8.3 Memory Management

```
Per-Conversation:
  Supervisor maintains conversation state:
  - User queries and responses
  - Agent routing decisions
  - Retrieved context IDs
  - Generated artifacts (simulation run IDs, procurement run IDs)
  
Per-Session (user login session):
  - Active agent states
  - Recent tool call results (cache, TTL 5 min)
  - Pending tasks (if any)

Global (permanent):
  - Decision store: every significant decision logged
  - Outcome store: actual outcomes of recommendations (filled later via feedback)
  - Agent metrics: response time, tool success rate, user satisfaction (implicit)
```

---

## 9. Module-by-Module AI Summary

| Module | Current State | AI Improvement | Difficulty | Hackathon Impact | Priority |
|--------|--------------|----------------|-----------|-----------------|----------|
| **Copilot** | Rule-based keyword counter | Full LLM + RAG + tools replacement | Medium | **GAME-CHANGER** | **P0** |
| **Frontend** | Static dashboards + JSON display | Chat UI, streaming, AI everywhere | Medium | **GAME-CHANGER** | **P0** |
| **RAG (new)** | Does not exist | Hybrid search + re-ranking + context | Medium-High | **GAME-CHANGER** | **P0** |
| **Agent System (new)** | Does not exist | 12-agent ecosystem with supervisor | High | **GAME-CHANGER** | **P1** |
| **Risk Engine** | Weighted formula + simulated data | ML-predicted scores + LLM narrative | Medium-High | HIGH | P1 |
| **Digital Twin** | Deterministic simulation engine | LLM scenario generation + analysis | Medium | HIGH | P1 |
| **Procurement** | Deterministic optimization | LLM executive narrative + auto-trigger | Low-Medium | HIGH | P1 |
| **SPR** | Deterministic release planning | LLM strategy recommendation + narrative | Low-Medium | HIGH | P1 |
| **ML Platform** | Infrastructure with zero artifacts | Train 3-5 models, register, connect | Low | HIGH | P1 |
| **Reports** | Template data dumps | LLM-generated intelligence reports | Low | Medium | P2 |
| **Alerts** | Threshold-based | ML anomaly detection + LLM correlation | Medium | Medium | P2 |
| **Analytics** | Descriptive SQL aggregates | LLM trend explanation + narrative | Low-Medium | Medium | P2 |
| **Knowledge Graph** | Relational tables + basic queries | LLM NLI + entity resolution | Medium | HIGH | P1 |
| **Semantic Search** | Single-model dense search | Hybrid + re-ranking + query expansion | Low | Low | P2 |
| **ML Service** | 3 real + 5 heuristic components | Upgrade heuristics to ML | Medium | Low | P3 |

### Priority Definition

| Priority | Meaning | When |
|----------|---------|------|
| **P0** | Must have for hackathon. Without it, we cannot credibly claim "AI-Driven." | Week 1 |
| **P1** | High impact. Significantly improves demo quality and judging scores. | Week 2 |
| **P2** | Nice to have. Improves depth but not essential for core narrative. | Week 3 |
| **P3** | Polish. Only if time permits. | Week 4 |

---

## 10. Implementation Roadmap

### Week 1: AI Foundation (P0)

| Day | Task | Deliverable | Files to Create/Modify |
|-----|------|-------------|----------------------|
| **1** | LLM integration layer | `backend/shared/llm/` package with OpenAI client, retry logic, token management, streaming | `backend/shared/llm/client.py`, `backend/shared/llm/config.py`, `backend/shared/llm/tokens.py` |
| **1** | Fix embedding consumer bug | Working embedding pipeline | `services/embedding-service/consumer.py` (line 86 fix) |
| **2** | Upgrade embedding model to bge-large-en-v1.5 | Higher quality embeddings, better retrieval | `services/embedding-service/services/embeddings.py`, `services/embedding-service/requirements.txt` |
| **2-3** | RAG Agent | Hybrid search, cross-encoder re-ranking, context assembly, citation generation | `backend/api/rag/` (new router), `backend/api/rag/agent.py`, `backend/api/rag/retriever.py`, `backend/api/rag/reranker.py` |
| **3-4** | Supervisor Agent + Intelligence Agent | Agent framework, tool definitions, routing, streaming | `backend/api/agents/supervisor.py`, `backend/api/agents/intelligence.py`, `backend/api/agents/router.py`, `backend/api/agents/stream.py` |
| **4-5** | Rewrite Copilot as LLM agent | Working AI chat with RAG + tools | `backend/api/copilot/service.py` (complete rewrite) |

### Week 2: Intelligence Layer (P1)

| Day | Task | Deliverable | Files |
|-----|------|-------------|-------|
| **1-2** | Scenario Agent | Natural language → simulation params → run → analyze | `backend/api/agents/scenario.py` |
| **2-3** | Procurement Agent + SPR Agent | NL procurement requests, SPR analysis with LLM reasoning | `backend/api/agents/procurement.py`, `backend/api/agents/spr.py` |
| **3** | Knowledge Graph Agent | NL graph queries, entity resolution, path explanation | `backend/api/agents/knowledge_graph.py` |
| **3-5** | Train ML models | Execute ML Platform pipeline, register models | Research notebooks → production models |
| **4-5** | Connect ML predictions to agents | Risk predictions available via Prediction Agent | `backend/api/agents/prediction.py` |

### Week 3: Experience Layer (P1-P2)

| Day | Task | Deliverable | Files |
|-----|------|-------------|-------|
| **1-3** | Rewrite Copilot frontend page | Streaming chat UI, markdown rendering, citation display, follow-up suggestions | `frontend/src/pages/Copilot.tsx` (rewrite), `frontend/src/components/ChatMessage.tsx`, `frontend/src/components/ChatInput.tsx`, `frontend/src/hooks/useAgentStream.ts` |
| **2-3** | Floating AI assistant | AI assistant overlay on every page | `frontend/src/components/AIAssistant.tsx`, `frontend/src/hooks/useAIAssistant.ts` |
| **3-4** | Executive Brief Agent + Validation Agent | Report generation, fact-checking | `backend/api/agents/executive.py`, `backend/api/agents/validation.py` |
| **4-5** | Executive Briefing page | AI-generated executive summary across all systems | `frontend/src/pages/ExecutiveBrief.tsx` |

### Week 4: Polish & Demo Prep (P2-P3)

| Day | Task | Deliverable | Files |
|-----|------|-------------|-------|
| **1** | Alert correlation via LLM | Smart alert grouping, triage recommendations | `backend/api/alerts/service.py` |
| **2** | Analytics narratives | AI-generated trend explanations on analytics page | `backend/api/analytics/service.py`, `frontend/src/pages/Analytics.tsx` |
| **2-3** | Demo scripts | 3 guided demo scenarios with expected outcomes | `docs/DEMO_SCRIPTS.md` |
| **3-4** | Presentation materials | Architecture diagrams, value props, technical deep-dive | `docs/PRESENTATION.md` |
| **4** | Load test + harden | 10 concurrent users, edge cases, error handling | Stress testing, logging improvement |

---

## 11. Judging Optimization

### How to Maximize Each Criterion

#### Business Impact (Target: 9/10)

| Strategy | How We Achieve It |
|----------|-------------------|
| **Real problem, real data** | Energy supply chain resilience for import-dependent economies is a $2T problem. Our data models real infrastructure. |
| **Measurable outcomes** | Every AI response includes numbers: "This disruption would cost $X, reduce supply by Y bpd, last Z days." |
| **Executive focus** | The Executive Brief Agent produces outputs that look like they came from a Ministry of Petroleum briefing room. |
| **Before/after contrast** | Demo starts with the rule-based Copilot, then shows the AI-powered version. The contrast is obvious in 30 seconds. |

#### Technical Excellence (Target: 9/10)

| Strategy | How We Achieve It |
|----------|-------------------|
| **Multi-agent architecture** | 12 specialized agents with supervisor orchestration is architecturally impressive. |
| **Hybrid RAG** | Dense + sparse + KG retrieval with cross-encoder re-ranking is production-grade. |
| **ML + AI + deterministic** | Proper separation: ML for predictions, LLM for reasoning, deterministic engines for math. |
| **Streaming everywhere** | Every AI response streams in real-time. No "thinking..." spinner. |

#### Innovation (Target: 9/10)

| Strategy | How We Achieve It |
|----------|-------------------|
| **AI-native energy platform** | Not a chatbot bolted onto a dashboard. AI is embedded into every subsystem. |
| **Natural language simulation** | "Simulate a Hormuz blockade" → simulation runs → results analyzed → recommendations generated. All from one sentence. |
| **Self-critiquing system** | Validation Agent reviews other agents' outputs. The AI checks its own work. |
| **Cross-domain reasoning** | Risk signals → simulation → procurement → SPR. End-to-end AI orchestration across domains. |

#### Scalability (Target: 8/10)

| Strategy | How We Achieve It |
|----------|-------------------|
| **Stateless agents** | Agents hold context in memory, not in process state. Scale horizontally. |
| **Async tool execution** | Independent tools run in parallel. Simulation runs async. |
| **Caching** | RAG context cache, tool output cache, LLM response cache. |
| **Kafka foundation** | Event-driven architecture already scales. |

#### User Experience (Target: 9/10)

| Strategy | How We Achieve It |
|----------|-------------------|
| **Single text input** | "What's the risk in Hormuz?" triggers the entire system. No form filling. |
| **Streaming visibility** | Users see agents working in real-time: "Searching articles... Running simulation... Analyzing impacts..." |
| **Trust through transparency** | Every claim has citations. Every recommendation shows reasoning. Every prediction shows confidence. |
| **10-minute demo flow** | 3 pre-scripted demos that each show a different aspect: intelligence query, scenario simulation, crisis management. |

### Demo Script Outline (10 minutes)

```
0:00-0:30 — Introduction: "This is an AI-Driven Energy Supply Chain Resilience Platform"
0:30-2:00 — Demo 1: Geopolitical Intelligence
  User: "What's the current risk situation in the Middle East?"
  System: Searches articles, analyzes risks, shows entity graph, produces executive summary
  Key feature: RAG + KG Agent + Intelligence Agent

2:00-5:00 — Demo 2: Disruption Simulation
  User: "Simulate a full blockade of the Strait of Hormuz for 60 days"
  System: Runs Digital Twin simulation, detects supply gaps, triggers procurement, analyzes SPR
  Key feature: Scenario Agent → Procurement Agent → SPR Agent → Executive Brief Agent

5:00-7:00 — Demo 3: Predictive Analytics
  User: "Which refineries are most at risk next quarter?"
  System: ML prediction + risk analysis + natural language explanation
  Key feature: Prediction Agent + Intelligence Agent + KG Agent

7:00-8:00 — Architecture overview
  Visual: Agent flow diagram, showing how agents collaborate
  Key point: "Every subsystem has dedicated AI agents"

8:00-9:00 — Technical highlights
  Multi-agent orchestration, hybrid RAG, LLM integration, ML Platform
  Key point: "3 trained models, 12 agents, 500+ API endpoints"

9:00-10:00 — Q&A
```

---

## 12. What NOT to Build

| Don't Build | Why |
|-------------|-----|
| **Graph DB migration (Neo4j)** | PostgreSQL works fine. Migration costs weeks. Zero demo impact. |
| **Real API integrations** | Simulated data works for demo. Real APIs add failure risk. |
| **Kubernetes/auto-scaling** | Docker Compose is sufficient for demo. K8s adds complexity with no visible benefit. |
| **Mobile app** | Not required for hackathon. No judges will ask about mobile. |
| **CI/CD pipeline** | Unnecessary for hackathon. Manual deploy is fine. |
| **Custom authentication** | JWT auth exists. No SSO, no OAuth, no 2FA needed. |
| **Data visualization library switch** | Recharts and Cytoscape work well. Don't rewrite. |
| **Infrastructure as Code** | Terraform/Pulumi would be over-engineering for a hackathon demo. |
| **End-to-end testing suite** | Unit tests are sufficient for hackathon. E2E tests take too long. |
| **Performance optimization** | Premature optimization. The system works at demo scale. |
| **Multi-language support** | English-only is fine for international hackathon. |
| **Dark mode / theme customization** | shadcn/ui theming exists. Don't add customization options. |
| **PDF export** | Nice-to-have. Doesn't contribute to judging criteria. |
| **Notification system (email/SMS)** | Requires external services. Not visible in demo. |
| **Audit trail enhancements** | Existing audit_log works. Deepening audit adds no demo value. |

**The Golden Rule for Hackathon:** If it can't be seen in a 10-minute demo, it doesn't matter.

---

## 13. Expected Score After Implementation

| Criterion | Current | After Implementation | Improvement |
|-----------|---------|---------------------|-------------|
| **Business Impact** | 6/10 | 9/10 | AI-powered intelligence, executive briefings, measurable outcomes |
| **Technical Excellence** | 6/10 | 9/10 | Multi-agent architecture, hybrid RAG, 5 trained ML models, streaming |
| **Innovation** | 5/10 | 9/10 | AI-native energy platform, natural language simulation, self-critiquing agents |
| **Scalability** | 5/10 | 8/10 | Stateless agents, async tools, Kafka foundation, caching |
| **User Experience** | 6/10 | 9/10 | Natural language interface, streaming visibility, transparent reasoning |
| **Overall** | **5.6/10** | **8.8/10** | **+3.2 points — from "competent" to "contender"** |

### Score Breakdown

| Factor | Weight | Current | After | Weighted Current | Weighted After |
|--------|--------|---------|-------|-----------------|---------------|
| Business Impact | 25% | 6 | 9 | 1.50 | 2.25 |
| Technical Excellence | 25% | 6 | 9 | 1.50 | 2.25 |
| Innovation | 20% | 5 | 9 | 1.00 | 1.80 |
| Scalability | 15% | 5 | 8 | 0.75 | 1.20 |
| User Experience | 15% | 6 | 9 | 0.90 | 1.35 |
| **Total** | **100%** | | | **5.65** | **8.85** |

---

## 14. Final Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            USER INTERFACE LAYER                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Frontend (React 18 + Vite + shadcn/ui + Recharts + Cytoscape)           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │   │
│  │  │Dashboard │ │Analytics │ │ Copilot  │ │Executive │ │ AI Assistant │   │   │
│  │  │  Pages   │ │  Pages   │ │ Chat UI  │ │  Brief   │ │  (Floating)  │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │ HTTP + SSE (streaming)
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (Modular API :8000)                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Routers: articles, analytics, auth, cases, copilot, entities, events,   │   │
│  │  graph, health, reports, search, watchlists, energy (proxy), alerts       │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AI ORCHESTRATION LAYER                                   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           SUPERVISOR AGENT                                 │   │
│  │                 (GPT-4o — routing, merging, escalation)                    │   │
│  └──┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬──────┬──────┘   │
│     │       │       │       │       │       │       │       │      │          │
│  ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐   │
│  │Intel│ │Scen │ │Proc │ │ SPR │ │  KG │ │Exec │ │Valid│ │RAG  │ │Pred │   │
│  │Agent│ │Agent│ │Agent│ │Agent│ │Agent│ │Agent│ │Agent│ │Agent│ │Agent│   │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  LLM Layer: GPT-4o (primary) │ Claude 3.5 (fallback) │ Ollama (offline)   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  RAG Layer: Hybrid Search (pgvector + ES) → RRF Fusion → Cross-encoder   │   │
│  │  Indices: articles, entities, infrastructure, simulations, decisions      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  ML Layer: XGBoost, Random Forest (via ML Platform :8007)                  │   │
│  │  Models: risk_scorer, supply_gap, price_direction, refinery_utilization   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DETERMINISTIC SERVICE LAYER                             │
│                                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐      │
│  │  Energy  │ │  Risk    │ │ Digital  │ │Procure-  │ │  SPR Decision    │      │
│  │ Service  │ │ Engine   │ │  Twin    │ │  ment    │ │  Intelligence    │      │
│  │  (:8006) │ │(:8006)   │ │ (:8006)  │ │ (:8006)  │ │   (:8006)        │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘      │
│                                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐      │
│  │  Ingest  │ │  ML      │ │Database  │ │Embedding  │ │   ML Platform    │      │
│  │ Service  │ │ Service  │ │ Service  │ │ Service   │ │   (:8007)        │      │
│  │  (:8001) │ │ (:8002)  │ │ (:8003)  │ │ (:8005)   │ │(trained models)  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘      │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DATA INFRASTRUCTURE LAYER                                │
│                                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │  PostgreSQL   │ │  Kafka       │ │ Elasticsearch │ │     pgvector          │   │
│  │  3 schemas   │ │  2 topics    │ │  1 index      │ │  (384d → 768d)        │   │
│  │  80+ tables  │ │  3 consumer  │ │              │ │                       │   │
│  │              │ │  groups      │ │              │ │                       │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Legend

| Layer | Color/Shading | Purpose |
|-------|---------------|---------|
| 🔴 **AI Layer (NEW)** | Red | LLM, agents, RAG, ML — all new |
| 🟢 **Deterministic Layer (EXISTING)** | Green | All existing services — unchanged |
| 🟡 **Data Layer (EXISTING)** | Yellow | PostgreSQL, Kafka, ES — unchanged |
| 🔵 **UI Layer (MODIFIED)** | Blue | Frontend — new pages + modified Copilot |

### Key Integration Points

1. **Agent → Tool**: Each agent calls existing API endpoints with no backend changes
2. **Agent → RAG**: RAG Agent provides context to all agents via hybrid search
3. **Agent → LLM**: All agents use GPT-4o via shared LLM client with streaming
4. **Agent → ML**: Prediction Agent calls ML Platform for ML inference
5. **Supervisor → Specialists**: Routing decisions based on intent classification
6. **Specialist → Supervisor**: Results returned with confidence scores and evidence
7. **Validation Agent → All**: Cross-checks outputs for consistency and accuracy

---

**End of AI Architecture Review**

This document is the blueprint for the next 4 weeks of development. Follow the priority order (P0 → P1 → P2 → P3) and the implementation roadmap (Week 1 → Week 4). Do not build anything in the "What NOT to Build" section. Optimize every decision for a 10-minute live demo at an international AI hackathon.

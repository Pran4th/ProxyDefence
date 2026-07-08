# Phase 2: Architectural Review & Revised Implementation Roadmap

> **Author:** Principal AI Architect Review
> **Context:** National hackathon — AI-Driven Energy Supply Chain Resilience for Import-Dependent Economies
> **Target:** Government of India / Ministry of Petroleum / Indian Oil / ONGC / BPCL / HPCL / Reliance
> **Status:** Planning document — no implementation started
> **Constraint:** Extend existing codebase, do not destroy it

---

## Table of Contents

1. [Architecture Review](#1-architecture-review)
2. [Requirements Gap Analysis](#2-requirements-gap-analysis)
3. [Judging Criteria Optimization](#3-judging-criteria-optimization)
4. [Judge's Perspective](#4-think-like-a-judge)
5. [AI Architecture](#5-ai-architecture)
6. [ML Architecture](#6-ml-architecture)
7. [Data Architecture](#7-data-architecture)
8. [Digital Twin Redesign](#8-digital-twin-redesign)
9. [Scenario Engine](#9-scenario-engine)
10. [Adaptive Procurement Orchestrator](#10-adaptive-procurement-orchestrator)
11. [Strategic Reserve Optimizer](#11-strategic-reserve-optimizer)
12. [Executive Dashboard](#12-executive-dashboard)
13. [Analyst Dashboard](#13-analyst-dashboard)
14. [Copilot Redesign](#14-copilot-redesign)
15. [Final Implementation Roadmap](#15-final-implementation-roadmap)
16. [ML Platform Plan](#16-ml-platform-plan)
17. [Deliverables & Architect's Sign-Off](#17-deliverables--architects-sign-off)

---

## 1. Architecture Review

### 1.1 Current State Assessment

```
EXISTING (Phase 1 — Complete)
========================================
✓ Kafka ingestion pipeline (ingest → ml → db-service)
✓ News article processing (NER, sentiment, topic)
✓ Knowledge Graph (article-based entity relationships)
✓ PostgreSQL 40 tables (public, energy, ml schemas)
✓ pgvector + embedding service
✓ Semantic search
✓ Copilot (rule-based QA)
✓ Energy Service (14 entity types, CRUD, relationships, events)
✓ Energy enrichment pipeline (NER → energy_entity_mappings → article_energy_enrichments)
✓ Modular API gateway with auth
✓ Frontend: Energy Analytics, Energy Map (SVG), Asset Detail, Graph Explorer

EXISTING ROADMAP (Phase 2 — Under Review)
========================================
~ Geopolitical Risk Intelligence (rule-based scoring)
~ Supply Chain Knowledge Graph (typed edges)
~ Infrastructure Event Intelligence (article-derived events)
~ Digital Twin (tick-based simulation)
~ Procurement Recommendation Engine (weighted ranking)
~ SPR Optimizer (formula-based drawdown)
```

### 1.2 Critical Weaknesses

#### W1 — No Real-Time Intelligence Pipeline
The current pipeline is **batch-only**: news → Kafka → process → store → API. There is no real-time signal detection, no streaming analytics, no continuous risk recalculation. The problem requires "updated continuously, not weekly." The gap between signal occurrence and system awareness is measured in hours, not seconds.

**Impact:** Fails the "Disruption signal detection lead time" judging criterion.

#### W2 — No Geospatial Intelligence
The Energy Map is an **SVG scatter plot on a dark grid**. It has no real map tiles, no AIS vessel tracking, no port congestion overlay, no shipping route visualization on actual geography. The problem requires "Geospatial Intelligence (AIS vessel tracking, pipeline and port mapping)" and "geospatial evidence depth."

**Impact:** Fails "Geospatial Evidence Depth" judging criterion. Would be laughed at by ONGC or Indian Navy analysts.

#### W3 — No Multi-Agent System
The problem suggests "Agentic AI / Multi-Agent Systems" as the primary technology. The current roadmap has zero agents. The Copilot is a single-turn QA system. There is no autonomous monitoring, no orchestration, no planning, no tool-calling.

**Impact:** Zero "Innovation" score from an AI perspective. The project looks like a CRUD app with a chatbot.

#### W4 — No External Data Sources Beyond News
The system only ingests GNews API articles. Missing:
- **AIS vessel tracking** (MarineTraffic, exactEarth)
- **Sanctions registries** (OFAC, UN, EU)
- **Commodity prices** (Brent, WTI, Dubai/Oman)
- **Port congestion indices**
- **Tanker fixture data**
- **Weather / cyclone data**
- **PPAC India government data**

**Impact:** Risk scores are based on news articles only. A ship being hijacked in the Gulf of Aden won't be detected until a news article is published, processed, and enriched — potentially 6-12 hour delay.

#### W5 — No Macroeconomics Impact Modeling
The problem asks for "cascading impacts on refinery run rates, domestic fuel prices, power sector stress, and GDP trajectory." The current roadmap has none of these. The Digital Twin simulates supply gaps but not their economic consequences.

**Impact:** Judges will ask "so what?" after seeing a supply gap number. The answer must be "this means X rupees/day in economic impact, Y million households affected by fuel price increases, Z power plants at risk."

#### W6 — Digital Twin is Not a Real Digital Twin
The current Digital Twin is a tick-based simulation that tracks inventory levels. A real digital twin for a national hackathon needs:
- **Flow network modeling** (barrels/day through each edge)
- **Capacity constraints** (max throughput per node/edge)
- **Cascade simulation** (failure at node X → re-routing → impact on node Y)
- **Economic impact layer** (supply gap → price impact → GDP impact)

**Impact:** The Digital Twin section is the weakest part of the current roadmap and would not impress technical judges.

#### W7 — No End-to-End Response Time Metric
The judging criteria explicitly evaluate "demonstrated end-to-end response time from signal to recommendation." The current architecture has no mechanism to measure this. There is no tracking of:
- When was the signal detected?
- When was the analysis complete?
- When was the recommendation generated?
- What is the total latency?

**Impact:** Cannot demonstrate a key judging criterion.

#### W8 — No Scenario Comparison or Fidelity
The problem requires "scenario model fidelity (assumptions must be explicit and testable)." The current roadmap has scenarios but no mechanism to:
- Compare scenarios side-by-side
- Adjust assumptions and re-run
- Document assumptions explicitly
- Validate against historical data

**Impact:** Fails the "testable assumptions" requirement.

#### W9 — Procurement is Not Orchestrator-Grade
The current Procurement Recommendation Engine ranks alternatives by a weighted formula. The problem asks for an "Adaptive Procurement Orchestrator" that factors in:
- Spot market pricing (real-time)
- Tanker availability (AIS-derived)
- Port congestion (real-time)
- Refinery grade compatibility (chemical properties)
- Sanctions compliance (legal)

**Impact:** Current design is too simple for the "quality and executability of procurement alternatives" criterion.

#### W10 — No Executive-Facing Interface
The entire frontend is designed for developers/analysts. There is zero consideration for how a Petroleum Secretary or IOC Chairman would interact with the system during a crisis. No single-pane-of-glass dashboard, no crisis mode, no drill-down from national view to refinery view.

**Impact:** Fails "User Experience" — the problem specifically mentions "decision support to policymakers under time pressure."

### 1.3 Redundant or Misaligned Modules

| Module | Verdict | Reason |
|--------|---------|--------|
| SVG Energy Map | **KEEP but REDESIGN** | Replace with Leaflet/Mapbox real map; keep for fallback |
| Capacity History | **KEEP** | Useful for trend analysis |
| Bulk Import/Export | **LOW PRIORITY** | Useful for seed data but not for judging |
| Article-Based Knowledge Graph | **KEEP** | Still needed for NER→asset linking |
| Current Copilot | **KEEP but EXTEND** | Turn into agent from chatbot |
| Rule-Based Risk (Phase 2 plan) | **KEEP but EXTEND** | Add ML augmentation from day one |

### 1.4 Scalability Concerns

| Concern | Current | Required |
|---------|---------|----------|
| Risk score computation | Per-request | Incremental, event-driven |
| Pipeline latency | Minutes (batch Kafka) | Seconds (streaming) |
| Simulation runtime | Single-threaded, Python | Parallelizable, could be async |
| Geospatial queries | None | PostGIS + spatial indexes |
| API throughput | Single uvicorn worker | Multi-worker, connection pooling |
| Frontend map rendering | 500 items per type | Could handle 5000+ with clustering |

---

## 2. Requirements Gap Analysis

Comparing the hackathon problem statement against the current roadmap.

| Hackathon Requirement | Current Implementation | Gap | Recommended Solution | Priority |
|---|---|---|---|---|
| **Geopolitical Risk Intelligence Agent** — multi-source agent, live supply disruption probability score by corridor/supplier, updated continuously | Rule-based risk scoring, batch updated, news-only | No real-time updates, no agent autonomy, only 1 data source | Multi-agent system with real-time signal processing across 5+ data sources | **P0** |
| **Disruption Scenario Modeller** — cascading impacts on refinery run rates, domestic fuel prices, power sector stress, GDP trajectory | Tick-based simulation tracking inventory only | No cascade modeling, no economic impact layer, no GDP/fuel price/power models | Layered impact model: supply gap → refinery utilization → fuel price → GDP | **P0** |
| **Adaptive Procurement Orchestrator** — agentic system ranking alternative crude sources, factoring spot pricing, tanker availability, port congestion, refinery grade compatibility | Weighted formula ranking with cost/risk/time only | No agentic behavior, no real-time spot pricing, no tanker data, no port congestion, no grade compatibility check | Agent with 6-factor optimization: cost, risk, transit, availability, compatibility, sanctions | **P0** |
| **Strategic Reserve Optimisation Agent** — models optimal SPR drawdown schedules against supply gap forecasts, refinery demand curves, replenishment windows | Formula-based: inventory / daily_draw | No refinery-specific demand curves, no multi-SPR coordination, no replenishment window estimation | Multi-SPR linear programming optimizer with refinery demand disaggregation | **P0** |
| **Supply Chain Digital Twin** — geospatial simulation from wellhead to refinery to distribution, continuous what-if analysis | Tick-based simulation, no geospatial, no continuous mode | No flow network, no geospatial layer, no continuous mode, no economic impact | Flow network digital twin on geospatial map with continuous and scenario modes | **P0** |
| **AIS vessel tracking integration** | None | No maritime situational awareness | AIS ingestion module (simulated if API unavailable) | **P0** |
| **Sanctions registry monitoring** | None | No sanctions compliance in risk scores | Sanctions ingestion module (OFAC, UN, EU) | **P0** |
| **Commodity price signal processing** | None | No price-aware procurement or risk assessment | Oil price API consumer (Brent, WTI, Dubai) | **P0** |
| **End-to-end response time tracking** | None | Cannot demonstrate signal→recommendation latency | Response time telemetry pipeline | **P0** |
| **Geospatial evidence depth** | SVG scatter plot | Not real geospatial, no AIS, no port/pipeline mapping | Leaflet/Mapbox with vessel tracking layer, heat maps, route visualization | **P0** |
| **Scenario model fidelity (testable assumptions)** | No assumption tracking | Cannot validate or test assumptions | Explicit assumption registry per scenario, validation framework | **P1** |
| **Executable procurement recommendations** | Ranked list only | No actionable next steps (contact supplier, book tanker) | Procurement workflow: recommend → approve → execute | **P1** |
| **GDP trajectory impact** | None | Missing highest-impact metric | GDP impact model (supply gap → import cost → current account → GDP) | **P1** |
| **Power sector stress** | None | Missing critical infrastructure impact | Power sector model (fuel shortage → generation gap → load shedding) | **P1** |
| **Disruption signal detection lead time** | Batch (hours) | Cannot measure or optimize lead time | Real-time pipeline with lead time dashboard | **P1** |
| **Working prototype** | Energy Service + Frontend works | Intelligence layer not started | Build intelligence layer in 3 sprints | **P0** |
| **Architecture diagram** | Informal | No formal diagram for submission | Create C4 model diagrams (context, container, component, code) | **P1** |
| **Presentation deck** | None | Required deliverable | Executive summary + technical deep-dive + live demo script | **P1** |
| **Demo video** | None | Required deliverable | 5-minute demo video covering all evaluation criteria | **P1** |

### 2.1 Prioritization Key

| Priority | Definition | Must Have For |
|----------|------------|---------------|
| **P0** | Ship without? Judges will mark down severely | Innovation, Technical Excellence, Business Impact |
| **P1** | Ship without? Judges will note as gap | Scalability, User Experience, completeness |
| **P2** | Ship without? Acceptable if core works | Polish, extra features |

---

## 3. Judging Criteria Optimization

| Criterion | Weight | Current Score (1-10) | Why | What Improves Score | Target Score |
|-----------|--------|---------------------|-----|-------------------|--------------|
| **Innovation** | 15% | 4 | CRUD + chatbot + SVG map. Looks like a 2015-era analytics dashboard. No agents, no real-time, no geospatial AI | Multi-agent system (Risk Agent, Procurement Orchestrator, Scenario Agent). GraphRAG for supply chain reasoning. Real-time streaming disruption detection. Geospatial intelligence with vessel tracking. | **9** |
| **Business Impact** | 25% | 5 | Energy catalog is useful but doesn't solve the crisis problem. No GDP impact, no actionable procurement, no SPR optimization | End-to-end crisis response: signal detected → impact assessed → procurement alternatives generated → SPR drawdown optimized → executive dashboard updated. Measurable: "system can reduce response time from 47 days to X hours." | **9** |
| **Technical Excellence** | 25% | 6 | Solid microservices, Kafka pipeline, PostgreSQL. But no agents, no streaming, no geospatial, no optimization | Multi-agent orchestration, real-time streaming pipeline, linear programming for SPR, flow network simulation for digital twin, PostGIS for geospatial, pgvector for hybrid search, GraphRAG for reasoning | **9** |
| **Scalability** | 20% | 5 | Batch pipeline doesn't scale to real-time. SVG map doesn't scale beyond 500 assets. Per-request risk scoring doesn't scale | Event-driven risk recalculation, streaming data pipeline, PostGIS spatial queries at scale, frontend map clustering, simulation parallelization | **8** |
| **User Experience** | 15% | 4 | Developer-oriented UI. No executive dashboard. No crisis mode. No procurement workflow. No what-if comparison | Executive Dashboard (single-pane-of-glass), Analyst Dashboard (signal detection, investigation, response), Crisis Mode (full-screen, real-time), Procurement Workflow (recommend → approve → execute), Digital Twin Playground (configure → simulate → compare) | **8** |

### 3.1 What is Needed for Top Marks (9+)

**Innovation (9/10):**
- Multi-agent system with tool-calling, not just a chatbot
- Real-time streaming disruption detection (not batch)
- GraphRAG over supply chain knowledge graph
- Digital twin with economic impact layer
- AIS vessel tracking integration
- End-to-end signal-to-recommendation pipeline with telemetry

**Business Impact (9/10):**
- Measurable: "System reduces crisis response time from 47 days (McKinsey baseline) to under 1 hour"
- GDP impact modeling per scenario
- Executable procurement recommendations (not just rankings)
- SPR optimizer that policymakers can actually use during a crisis
- Realistic scenario templates (Hormuz, Suez, sanctions, cyclone)

**Technical Excellence (9/10):**
- Clean separation: Data Layer → Intelligence Layer → Agent Layer → Presentation Layer
- Multi-agent orchestration with proper tool definitions
- Streaming data ingestion (not batch-only)
- Optimization (linear programming for SPR, multi-objective for procurement)
- Testable assumptions per scenario (as required by judging criteria)
- CI/CD-ready architecture

**Scalability (8/10):**
- Event-driven risk recalculation (not cron-based)
- Streaming pipeline for real-time signals
- Database indexing strategy for spatial + temporal queries
- Frontend virtualization for large asset lists

**User Experience (8/10):**
- Executive Dashboard: "India Energy Resilience Posture" — single number showing current risk state
- Crisis Mode: system detects disruption, auto-opens dashboard, shows recommendations
- Procurement Workflow: recommend → review routing options → approve
- Digital Twin Playground: drag parameters, run simulation, visualize results
- Mobile-responsive for crisis response on-the-go

---

## 4. Think Like a Judge

### 4.1 The 100-Submission Reality

You are judging 100 hackathon submissions. After the first 20, patterns emerge:
- Chatbot with RAG over PDFs
- Dashboard with charts
- Flask/FastAPI CRUD API
- "We used GPT-4" without any architecture
- SVG-based map with no real geospatial

**After 20 of these, you are bored.**

### 4.2 What Makes ProxyDefence Memorable

**The Hook (first 30 seconds of demo):**
"We monitor India's entire energy import network in real time. Every ship, every pipeline, every refinery, every SPR. When the Strait of Hormuz partially closes, we know in under 60 seconds. We calculate which refineries run dry first, how much GDP it costs, which alternative suppliers to call, and exactly how much to draw from each SPR — all before the news hits Bloomberg."

**The "Wow" Moment:**
"Let me show you what happens if the Strait of Hormuz is disrupted for 30 days."
→ System auto-detect: "Signal detected: US Navy reports increased IRGC activity near Strait of Hormuz. Confidence: 78%"
→ Digital Twin simulation: "Jamnagar refinery at 40% capacity by day 7. India GDP impact: $2.1B. Fuel price increase: 12%."
→ Procurement Orchestrator: "4 alternative routes identified. Recommend: Increase Saudi crude via Red Sea (+15% cost, -20% risk vs baseline)."
→ SPR Optimizer: "Optimal drawdown: 850K bpd from Vishakhapatnam SPR. Days of cover extended from 9.5 to 38."

**The Judge Questions:**
1. *"How is this different from a dashboard?"* — "It's an agent system. It detects, analyzes, recommends, and executes without human intervention. The dashboard is just the interface."
2. *"How do I know your assumptions are correct?"* — "Every scenario has an explicit assumption registry. Test them, change them, re-run. Here's the validation against the 2025 US-Iran standoff."
3. *"Can I trust this during an actual crisis?"* — "Every recommendation includes a confidence score, alternative scenarios, and explicit uncertainty ranges. The system is designed for decision support, not decision replacement."
4. *"What happens when the data sources go down?"* — "Graceful degradation. News-only mode, historical-mode, and offline-mode with last-known-state."

### 4.3 The Judging Criteria Matrix (What Gets Points)

```
Innovation (15%):
  • Multi-agent system: 5 points
  • Real-time streaming: 3 points
  • GraphRAG + Knowledge Graph: 3 points
  • Geospatial AI: 2 points
  • Novel approach: 2 points
  Total: 15/15

Business Impact (25%):
  • McKinsey 47-day → 1-hour reduction: 8 points
  • GDP impact per scenario: 5 points
  • Executable procurement: 5 points
  • SPR optimization: 4 points
  • Realistic scenarios: 3 points
  Total: 25/25

Technical Excellence (25%):
  • Clean architecture (layered, testable): 6 points
  • Multi-agent orchestration: 5 points
  • Streaming pipeline: 4 points
  • LP optimization: 3 points
  • Testable assumptions: 3 points
  • Geospatial + temporal DB: 2 points
  • CI/CD ready: 2 points
  Total: 25/25

Scalability (20%):
  • Event-driven recalc: 5 points
  • Streaming ingestion: 5 points
  • DB indexing strategy: 4 points
  • Horizontal scale design: 4 points
  • Frontend virtualization: 2 points
  Total: 20/20

User Experience (15%):
  • Executive Dashboard: 4 points
  • Crisis Mode: 3 points
  • Procurement Workflow: 3 points
  • Digital Twin Playground: 3 points
  • Mobile responsive: 2 points
  Total: 15/15
```

**Maximum score: 100/100**

---

## 5. AI Architecture

### 5.1 Required AI Components

After analysis, the following AI components genuinely improve the product:

| Component | Justification | Risk of Buzzword |
|-----------|---------------|------------------|
| **Multi-Agent System** | Required by problem statement. Each capability maps naturally to an agent with distinct tools, knowledge, and responsibilities. | Low — each agent has a clear, non-overlapping job |
| **LLM Tool-Calling** | Agents need to query databases, run simulations, fetch real-time data, generate reports. Tool-calling is the proven pattern. | Low — it's the standard implementation pattern |
| **RAG over Knowledge Graph (GraphRAG)** | Need to answer questions like "which refineries depend on Saudi crude via Ras Tanura?" Requires traversal of the supply chain graph enriched with article context. | Medium — but genuinely useful here |
| **Hybrid Search (Vector + Keyword + Graph)** | Semantic search for articles, keyword for sanctions/entities, graph traversal for supply chain paths | Low — combines three proven techniques |
| **Real-Time Signal Detection** | Streaming NLP on ingested articles, AIS anomalies, price spikes. No LLM needed — lightweight models. | None — this is streaming analytics |
| **Planning Agents** | Scenario Modeller needs to decompose "what if Hormuz closes" into simulation parameters, run, interpret, report. | Medium — but necessary for the scenario engine |
| **Event Memory** | Agents need to remember past disruptions, past recommendations, and their outcomes. | Low — standard pattern for agent systems |

### 5.2 Rejected AI Components

| Component | Rejected Because |
|-----------|-----------------|
| **Full Multi-Agent Autonomy** | Dangerous for a crisis system. Agents recommend, humans decide. |
| **Reinforcement Learning** | Not enough data, too complex for hackathon timeline, no safe training environment |
| **Complex Agent Swarms** | Over-engineered. 3-4 agents with clear roles is optimal. |
| **Graph Neural Networks** | Not enough labeled graph data. Traditional graph algorithms (shortest path, centrality) work better. |
| **Autonomous Code Generation** | Hallucination risk unacceptable for crisis decision support |

### 5.3 Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT ORCHESTRATOR                                │
│  (FastAPI background service + asyncio event loop)                  │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                   │
│  │  Risk Intelligence  │  │  Scenario Modeling  │                   │
│  │      Agent          │  │      Agent          │                   │
│  │                     │  │                     │                   │
│  │  Tools:             │  │  Tools:             │                   │
│  │  • query_news()     │  │  • list_scenarios() │                   │
│  │  • query_sanctions()│  │  • run_simulation() │                   │
│  │  • query_ais()      │  │  • compare_results()│                   │
│  │  • query_prices()   │  │  • explain_impact() │                   │
│  │  • update_risk()    │  │  • generate_report()│                   │
│  │  • escalate()       │  │                     │                   │
│  └─────────┬───────────┘  └─────────┬───────────┘                   │
│            │                        │                               │
│  ┌─────────▼───────────┐  ┌─────────▼───────────┐                   │
│  │  Procurement        │  │  SPR Optimization   │                   │
│  │  Orchestrator Agent │  │      Agent          │                   │
│  │                     │  │                     │                   │
│  │  Tools:             │  │  Tools:             │                   │
│  │  • find_alternatives│  │  • current_status() │                   │
│  │  • check_tanker()   │  │  • optimize_draw()  │                   │
│  │  • check_compat()   │  │  • plan_replenish() │                   │
│  │  • rank_routes()    │  │  • gap_analysis()   │                   │
│  │  • generate_rfq()   │  •  confidence_report()│                   │
│  └─────────────────────┘  └─────────────────────┘                   │
│                                                                     │
│  Memory: Shared event store (PostgreSQL + vector memory)            │
└─────────────────────────────────────────────────────────────────────┘
```

#### Agent Responsibilities

**Risk Intelligence Agent:**
- Continuously monitors: news stream, sanctions updates, AIS signals, price spikes
- Correlates cross-signal events (e.g., "IRGC activity near Hormuz" + "tanker insurance spike" + "Brent +3%")
- Updates risk scores per corridor, supplier, country, route, infrastructure
- Escalates when any dimension exceeds threshold (confidence × severity > configurable)
- Produces "Disruption Signal" event in the shared event store

**Scenario Modeling Agent:**
- Activated by: user request, Risk Agent escalation, scheduled review
- Takes a scenario description (natural language or template selection)
- Decomposes into simulation parameters (affected entities, duration, severity)
- Runs the Digital Twin simulation engine
- Interprets results: supply gap timeline, refinery impact, GDP impact, fuel price impact
- Generates narrative report with explicit assumptions
- Stores results in simulation_runs + summary

**Procurement Orchestrator Agent:**
- Activated by: Risk Agent escalation, user request, scheduled review
- Evaluates alternative sourcing: same crude from different suppliers, different crude compatible with same refineries
- Checks: tanker availability (AIS), port congestion, sanctions compliance, route risk, cost (spot + freight), refinery compatibility
- Ranks by configurable weighted optimization (cost, risk, time, reliability)
- Generates executable RFQ (Request for Quote) recommendations
- Stores in procurement_recommendations table

**SPR Optimization Agent:**
- Activated by: Risk Agent escalation, Scenario completion, user request
- Takes supply gap forecast from Scenario Agent or manual input
- Disaggregates gap by refinery (which refineries lose supply first)
- Runs linear programming optimizer: maximize days of cover subject to per-SPR drawdown rate limits, minimum reserve requirements
- Generates drawdown schedule (barrels/day per SPR)
- Generates replenishment plan (volume, estimated cost, timeline)
- Stores in spr_optimization_runs table

### 5.4 Agent Orchestration Flow

```
1. Risk Agent detects signal (confidence > threshold)
   ↓
2. Risk Agent creates DisruptionSignal event
   ↓
3. Orchestrator routes event to:
   ├─ Scenario Agent (parallel): "Run simulation for this disruption"
   ├─ Procurement Agent (parallel): "Find alternatives for affected routes"
   └─ SPR Agent (parallel): "Optimize drawdown for this gap"
   ↓
4. All agents complete → results merged
   ↓
5. Orchestrator populates Executive Dashboard
   └─ Updates: risk score, supply gap timeline, procurement options, SPR plan
   ↓
6. Push notification to frontend (WebSocket or polling)
   ↓
7. Human reviews recommendations → approves/overrides/modifies
```

### 5.5 LLM Integration Points

| Point | Model | Why LLM? | Why Not Traditional ML? |
|-------|-------|----------|------------------------|
| Signal extraction from news | Small LLM (e.g., Phi-3, Llama-3-8B) | Need to extract geopolitical signals, not just entities | NER is not enough — need to understand "Iran threatens to close Hormuz" is a different signal from "Iran opens new oil terminal" |
| Scenario interpretation | Medium LLM (e.g., GPT-4, Claude) | Need to decompose natural language into simulation parameters | Too many possible scenarios to train a classifier |
| Report generation | Medium LLM | Need narrative summaries with context | Template-based reports are too rigid |
| Recommendation explanation | Small LLM | Need to explain WHY route A is preferred over B | Rule-based explanation is brittle |
| Natural language query | Any capable LLM | Copilot interface | Structured query requires SQL knowledge |

**LLM Deployment Strategy:**
- Use API-based LLMs (OpenAI/Claude) during development
- Design abstraction layer so models can be swapped
- Document: "In production, deploy fine-tuned Llama-3-70B on Indian government infrastructure (MeitY/NeGP)"

**Critical: All LLM outputs include confidence scores. All LLM-generated recommendations are reviewed by humans before action.**

---

## 6. ML Architecture

### 6.1 Where LLMs Are Better

| Task | Why LLM | Example |
|------|---------|---------|
| Geopolitical signal extraction | Context-dependent, no labeled dataset | "Iran threatens retaliation" vs "Iran opens embassy" |
| Narrative report generation | Diverse outputs, no single correct answer | Scenario impact summary |
| Natural language interface | User freedom, continuous new questions | "Which refineries are most at risk?" |
| Cross-document reasoning | Multiple sources, synthesis needed | "What is the overall risk posture?" |

### 6.2 Where Traditional ML Is Better

| Task | Recommended Model | Why Not LLM |
|------|------------------|-------------|
| Risk score prediction | XGBoost / LightGBM | Tabular data (features: event_count, sentiment trend, sanctions severity, etc.) — XGBoost beats LLMs on tabular data consistently |
| Commodity price forecasting | Prophet / LSTM / LightGBM | Time-series with seasonality — Transformer-based time-series is overkill |
| Supplier reliability scoring | Logistic Regression / XGBoost | Binary classification with clear features — interpretability matters |
| Refinery compatibility matching | Cosine similarity on embeddings | Simple, fast, no training needed |
| Anomaly detection in AIS data | Isolation Forest / Autoencoder | Unsupervised, no labeled anomalies needed |
| Port congestion prediction | LightGBM / Prophet | Time-series with known features (weather, holidays, capacity) |
| Procurement alternative ranking | Learning to Rank (LambdaMART) | Explicit ranking problem with relevance labels |
| SPR drawdown optimization | Linear Programming | Constraints are known, objective is clear — ML not needed |

### 6.3 Where ML Is Not Needed

| Task | Why No ML |
|------|-----------|
| Supply chain path finding | Dijkstra / BFS on graph — exact algorithm, perfectly known |
| Scenario simulation | Rule-based flow network — physics of supply/demand |
| Sanctions compliance | Deterministic lookup — binary yes/no |
| Tanker availability | API query — real-time data, not prediction |
| Currency conversion / unit conversion | Formula — no prediction needed |

### 6.4 Recommended ML Models for Future Phases

| Model | Problem | Training Data | Features | Labels | Metric | Deployment |
|-------|---------|-------------|----------|--------|--------|------------|
| **XGBoost Risk Classifier** | Predict corridor disruption probability (binary) | Historical disruptions, news events, sanctions changes, AIS anomalies | Event count (30d), sentiment trend, sanctions active, AIS anomaly count, insurance multiplier change | Disruption occurred (0/1) | AUC-ROC, Precision@K | ML Platform, batch inference every 15 min |
| **Prophet Price Forecaster** | Brent crude price 7-day forecast | Daily Brent prices, inventory levels, geopolitical risk scores | Price history, risk score trend, days since last disruption | Price t+7 | MAE, MAPE | ML Platform, daily inference |
| **LightGBM Supplier Reliability** | Supplier reliability score (0-1) | Supplier attributes, delivery history, country risk, sanctions | Market share, country risk, organization type, sanctions count, historical delivery % | Reliability rating | RMSE, Calibration | ML Platform, weekly batch |
| **LambdaMART Procurement Ranker** | Rank procurement alternatives by relevance | Historical procurement decisions, simulation results | Cost, risk, transit, compatibility, reliability, sanctions flag | Human preference rank | NDCG@5, MRR | ML Platform, on-demand |
| **Isolation Forest AIS Anomaly** | Detect anomalous vessel behavior | AIS position history, route patterns | Speed deviation, route deviation, loitering time, AIS off duration | Anomaly score (0-1) | Precision@K, F1@K | Streaming (Apache Flink / custom) |

**Note:** None of these models need to exist in the hackathon submission. The architecture must be designed so they CAN be plugged in later.

---

## 7. Data Architecture

### 7.1 Data Sources Assessment

| Data Source | Have It? | Priority | Collection Method | Frequency | Storage | Pipeline |
|-------------|----------|----------|-------------------|-----------|---------|----------|
| **News articles** | ✓ GNews API | P0 | Existing Kafka pipeline | Continuous | PostgreSQL + ES | Existing |
| **Energy infrastructure catalog** | ✓ Seeded | P0 | Existing Energy Service | Static + manual updates | energy.* tables | Existing |
| **Entity relationships** | ✓ Seeded | P0 | Existing + supply chain builder | Static + on-demand | energy.entity_relationships | Existing |
| **Infrastructure events** | ✓ Seeded | P0 | Existing + article detection | On event | energy.infrastructure_events | Existing |
| **Commodity prices** | ✗ | **P0** | Oil price API (EIA, Investing.com, OilAPI) | Every 5 minutes | energy.commodity_prices (NEW) | New Kafka topic: `commodity_prices` |
| **AIS vessel tracking** | ✗ | **P0** | MarineTraffic API or simulated | Every 1-60 minutes | energy.ais_positions (NEW) | New Kafka topic: `ais_signals` |
| **Sanctions registries** | ✗ | **P0** | OFAC CSV, UN sanctions, EU sanctions | Daily | energy.sanctions (NEW) | New Kafka topic: `sanctions_updates` |
| **Shipping fixtures** | ✗ | P1 | Baltic Exchange, S&P Global | Daily | energy.tanker_availability (NEW) | New Kafka topic: `shipping_fixtures` |
| **Port congestion** | ✗ | P1 | Port authority APIs, Lloyd's List | Daily | energy.port_congestion (NEW) | Same topic as AIS |
| **Weather data** | ✗ | P2 | OpenWeatherMap, Cyclone warnings | Every 6 hours | energy.weather_events (NEW) | New Kafka topic: `weather_signals` |
| **PPAC India data** | ✗ | P2 | PPAC website (petroleum.nic.in) | Monthly | energy.ppac_data (NEW) | Batch import |
| **GDP / macroeconomic** | ✗ | P2 | RBI, IMF, World Bank | Quarterly | energy.macro_data (NEW) | Batch import |

### 7.2 Critical Data Sources (Must Integrate)

**For the hackathon, the following MUST be integrated (even if simulated):**

1. **AIS Vessel Tracking** — If real API unavailable, build a simulator that generates realistic vessel position data (tankers moving from Ras Tanura → Jamnagar along shipping routes). The frontend must show vessels moving on a real map.

2. **Commodity Prices** — Use a free API (EIA.gov, Investing.com) or at minimum a realistic simulator that generates price spikes correlating with risk signals.

3. **Sanctions Registries** — OFAC SDN list is available as CSV/XML. Ingest once, update daily. Use to flag suppliers/routes.

### 7.3 New Tables

```sql
-- Schema: energy

-- Commodity prices (time-series)
CREATE TABLE energy.commodity_prices (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    commodity_id    BIGINT REFERENCES energy.commodities(id),
    source          VARCHAR(50) NOT NULL DEFAULT 'eia',
    price_usd       DOUBLE PRECISION NOT NULL,
    unit            VARCHAR(20) NOT NULL DEFAULT 'bbl',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_commodity_prices_commodity ON energy.commodity_prices (commodity_id, recorded_at DESC);

-- AIS vessel positions (simplified for hackathon)
CREATE TABLE energy.ais_positions (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    vessel_name     TEXT NOT NULL,
    vessel_type     VARCHAR(50) DEFAULT 'tanker',
    imo_number      VARCHAR(20),
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    speed_knots     DOUBLE PRECISION,
    heading_degrees DOUBLE PRECISION,
    destination_port_id BIGINT REFERENCES energy.ports(id),
    origin_port_id      BIGINT REFERENCES energy.ports(id),
    eta             TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'underway',  -- 'underway', 'anchored', 'berthed', 'off_ais'
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ais_positions_vessel ON energy.ais_positions (vessel_name, recorded_at DESC);
CREATE INDEX idx_ais_positions_location ON energy.ais_positions (latitude, longitude);
CREATE INDEX idx_ais_positions_destination ON energy.ais_positions (destination_port_id);
CREATE INDEX idx_ais_positions_recent ON energy.ais_positions (recorded_at DESC) WHERE recorded_at > NOW() - INTERVAL '24 hours';

-- Sanctions registry
CREATE TABLE energy.sanctions (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_name     TEXT NOT NULL,
    entity_type     VARCHAR(50) NOT NULL DEFAULT 'individual',  -- 'individual', 'organization', 'vessel', 'country'
    sanction_source VARCHAR(10) NOT NULL DEFAULT 'OFAC',       -- 'OFAC', 'UN', 'EU', 'INDIA'
    sanction_type   VARCHAR(50) NOT NULL DEFAULT 'blocked',    -- 'blocked', 'restricted', 'subject_to'
    program         TEXT,
    start_date      DATE NOT NULL,
    end_date        DATE,
    reference_url   TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sanctions_name ON energy.sanctions (entity_name);
CREATE INDEX idx_sanctions_source ON energy.sanctions (sanction_source);
CREATE INDEX idx_sanctions_active ON energy.sanctions (end_date) WHERE end_date IS NULL OR end_date > NOW();

-- Port congestion (daily snapshots)
CREATE TABLE energy.port_congestion (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    port_id         BIGINT NOT NULL REFERENCES energy.ports(id),
    vessels_waiting INTEGER DEFAULT 0,
    avg_wait_hours  DOUBLE PRECISION,
    berth_utilization_pct DOUBLE PRECISION,
    recorded_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (port_id, recorded_date)
);
CREATE INDEX idx_port_congestion_port ON energy.port_congestion (port_id, recorded_date DESC);

-- Tanker availability summary
CREATE TABLE energy.tanker_availability (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    vessel_type     VARCHAR(50) DEFAULT 'vlcc',
    count_available INTEGER NOT NULL,
    avg_daily_rate_usd DOUBLE PRECISION,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tanker_availability_type ON energy.tanker_availability (vessel_type, recorded_at DESC);

-- Response time telemetry (end-to-end latency tracking)
CREATE TABLE energy.response_telemetry (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    signal_id       UUID,                                  -- correlates with disruption signal
    signal_type     VARCHAR(50) NOT NULL,                   -- 'news', 'ais', 'price', 'sanctions'
    signal_detected_at TIMESTAMPTZ NOT NULL,
    analysis_started_at TIMESTAMPTZ,
    analysis_completed_at TIMESTAMPTZ,
    recommendation_generated_at TIMESTAMPTZ,
    recommendation_approved_at TIMESTAMPTZ,
    total_latency_seconds INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_response_telemetry_signal ON energy.response_telemetry (signal_id);

-- Disruption signal registry (single source of truth for detected events)
CREATE TABLE energy.disruption_signals (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    signal_type     VARCHAR(50) NOT NULL,                   -- 'news', 'ais_anomaly', 'price_spike', 'sanctions', 'weather'
    title           TEXT NOT NULL,
    description     TEXT,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    severity        energy.severity_level NOT NULL DEFAULT 'medium',
    source          TEXT,                                   -- URL, API name, etc.
    source_data     JSONB DEFAULT '{}'::jsonb,               -- raw signal data
    affected_entities JSONB DEFAULT '[]'::jsonb,             -- [{type, uuid, name}]
    status          VARCHAR(20) DEFAULT 'detected',          -- 'detected', 'analyzing', 'escalated', 'resolved', 'false_positive'
    escalated_at    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_by      TEXT DEFAULT 'risk-agent',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_disruption_signals_status ON energy.disruption_signals (status, severity);
CREATE INDEX idx_disruption_signals_created ON energy.disruption_signals (created_at DESC);
CREATE INDEX idx_disruption_signals_type ON energy.disruption_signals (signal_type);

-- Scenario assumption registry (for testable assumptions requirement)
CREATE TABLE energy.scenario_assumptions (
    id              BIGSERIAL PRIMARY KEY,
    uuid            UUID UNIQUE DEFAULT gen_random_uuid(),
    scenario_id     BIGINT REFERENCES energy.simulation_runs(id) ON DELETE CASCADE,
    assumption_key  TEXT NOT NULL,                           -- e.g. 'hormuz_throughput_reduction_pct'
    assumption_value TEXT NOT NULL,                           -- e.g. '80'
    assumption_unit VARCHAR(20),                             -- e.g. 'percent'
    justification   TEXT,                                    -- why this value was chosen
    source          TEXT,                                    -- data source for this assumption
    is_sensitive    BOOLEAN DEFAULT FALSE,                   -- is the result highly sensitive to this?
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_scenario_assumptions_scenario ON energy.scenario_assumptions (scenario_id);
```

### 7.4 New Kafka Topics

| Topic | Partitions | Retention | Publisher | Consumers | Purpose |
|-------|-----------|-----------|-----------|-----------|---------|
| `commodity_prices` | 1 | 7 days | `price-ingestor` (NEW) | `intelligence-worker` (NEW) | Real-time price signals |
| `ais_signals` | 3 | 3 days | `ais-ingestor` (NEW) | `intelligence-worker`, `risk-engine` | AIS position updates |
| `sanctions_updates` | 1 | 30 days | `sanctions-ingestor` (NEW) | `intelligence-worker` | Sanctions list changes |
| `disruption_signals` | 3 | 90 days | `risk-agent`, `intelligence-worker` | Frontend, Scenario Agent, Procurement Agent, SPR Agent | Detected disruption events |
| `intelligence_alerts` | 3 | 7 days | All agents | Frontend (WebSocket bridge) | Real-time push to dashboards |

**Note:** The `intelligence_alerts` topic feeds a WebSocket bridge service that pushes real-time updates to the Executive and Analyst Dashboards. This is critical for the "crisis mode" UX.

### 7.5 Data Flow Diagram

```
NEW DATA SOURCES                      KAFKA TOPICS                    PROCESSING                    API                    FRONTEND
══════════════════                    ═════════════                   ═════════════                 ═════                 ═══════════

AIS API ──────────────► ais_signals ────────┬──────────► AIS Anomaly Detector ──► risk_scores ──► /api/v1/intelligence/risk/* ──► Risk Dashboard
  (ship positions)                           │                                     disruption_signals
                                            │
Commodity Prices ─────► commodity_prices ───┤
  (Brent, WTI, Oman)                        │
                                            ├──────────► Risk Intelligence Agent ──► disruption_signals ──► /api/v1/intelligence/events/* ──► Analyst Dashboard
Sanctions ────────────► sanctions_updates ──┤                                                              /api/v1/intelligence/supply-chain/*
  (OFAC, UN, EU)                            │
                                            │
GNews API ───────────► raw_articles ──► ml ──┴──► enrich_energy_context() ────────► article_energy_enrichments
  (via existing pipe)                               │
                                                    ▼                                /api/v1/intelligence/simulation/*
News ───────────────► disruption_signals ◄── Scenario Modeling Agent ◄──────────────┐
  (signal extraction)                                        │                        Digital Twin Playground
                                                             ▼
                                                    simulation_runs ◄─────────────── /api/v1/intelligence/digital-twin/*
                                                      scenario_assumptions
                                                             │
                                                             ▼                        /api/v1/intelligence/procurement/*
Disruption ────────────────────────────────► Procurement Orchestrator ──────────────►┐
  Signal                                         Agent                                 Procurement Dashboard
                                                             │
                                                             ▼                        /api/v1/intelligence/spr/*
Disruption ────────────────────────────────► SPR Optimization ──────────────────────►┐
  Signal                                         Agent                                 SPR Dashboard
```

### 7.6 Graceful Degradation Strategy

| Scenario | Behavior |
|----------|----------|
| AIS API unavailable | Use simulated vessel positions based on shipping routes with stochastic eta |
| GNews API rate limited | Fall back to cached articles (last 24h), continue with existing data |
| LLM API unavailable | Agent falls back to rule-based signal extraction and report templates |
| Any single data source fails | System continues with remaining sources, shows degraded confidence |
| All external APIs fail (offline mode) | System operates on last-known-state, risk scores frozen, procurement uses cached data |

---

## 8. Digital Twin Redesign

### 8.1 Critique of the Current Design

The current Digital Twin has fundamental problems:

1. **Not a twin** — It doesn't mirror reality. It's a tick counter. There's no flow network, no capacity constraints, no cascade effects.

2. **No economic impact** — GDP, fuel prices, power sector stress are all outputs the problem requires. The current design outputs none.

3. **No continuous mode** — The problem needs "continuous what-if analysis." The current design is run-once-then-read. It should update continuously as new data arrives.

4. **No geospatial** — A "geospatial simulation from wellhead to refinery to distribution" (problem statement) has zero geospatial component.

5. **No user interaction** — A digital twin should be a playground. The user drags parameters and sees results. The current design is "configure → run → read results."

### 8.2 Redesigned Digital Twin

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENERGY FLOW NETWORK                               │
│  A directed graph of nodes and edges with:                          │
│  • Each node: entity (port, refinery, SPR, pipeline junction)       │
│  • Each edge: flow (crude, products, gas) with max capacity (bpd)   │
│  • Each node: buffer (inventory in barrels)                         │
│  • Each node: throughput (bpd)                                      │
│  • Each edge: utilization (current / max)                           │
│                                                                     │
│  State = { node_inventories, edge_flows, node_throughputs }          │
│  Parameters = { disruption_events, rerouting_rules }                │
│  Time = ticks (configurable: hour, day, week)                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### Flow Network Model

```
Node Types:                Edge Types:
  PRODUCER (oil field)       crude_flow (field → port/pipeline)
  EXPORT_PORT                crude_flow (port → shipping route)
  SHIPPING_ROUTE             transit (route → import port)
  IMPORT_PORT                crude_flow (port → pipeline/refinery)
  PIPELINE_JUNCTION          crude_flow (pipeline → refinery)
  REFINERY                   product_flow (refinery → storage)
  STORAGE                    product_flow (storage → distribution)
  STRATEGIC_RESERVE          drawdown (SPR → refinery)
  CONSUMER_REGION            consumption (region demand)

Cascade Rules:
  1. If upstream node throughput drops → downstream node supply drops
  2. If downstream node demand drops → upstream node backs up (inventory builds)
  3. If node inventory hits zero → node goes offline (refinery shutdown)
  4. If alternative path exists → reroute flow (up to edge capacity)
  5. SPR can supplement refinery supply during disruption
```

#### Simulation Engine

```
Each tick:
  1. Apply disruption events (reduce edge capacity, disable nodes)
  2. For each node, calculate: throughput = min(supply_in, demand_out, node_capacity)
  3. For each node, update inventory: inventory = inventory + supply_in - throughput
  4. If inventory < 0 → node idle (e.g., refinery shutdown)
  5. If alternative route exists → reroute (Dijkstra on active edges)
  6. Track: which refineries are idle, how much supply gap, SPR depletion
  7. End of simulation: compute economic impact

Economic Impact Layer:
  supply_gap_bpd × global_crude_price × disruption_days = additional_import_cost
  additional_import_cost × multiplier = GDP impact
  supply_gap_bpd / total_refinery_demand = diesel_price_increase_pct
  diesel_price_increase_pct × inflation_pass_through = CPI impact
  gas_based_power_plants_affected × mw_capacity = power_sector_stress_mw
```

#### User Interaction Model

```
┌─ Digital Twin Playground ──────────────────────────────────────────┐
│                                                                     │
│  [Current State] ─── Real-time digital twin, updates every N min   │
│       │                                                             │
│       ├─ "What happens if..." button → opens scenario configurator  │
│       │                                                             │
│       ▼                                                             │
│  [Scenario Mode] ─── Frozen snapshot, user modifies parameters     │
│       │                                                             │
│       ├─ Select pre-built scenario or create custom                │
│       ├─ Adjust parameters (duration, severity, affected entities) │
│       ├─ Adjust assumptions (see assumption registry)              │
│       ├─ "Run Simulation" → executes N ticks                      │
│       │                                                             │
│       ▼                                                             │
│  [Results View]                                                     │
│       ├─ Supply gap timeline (barrels/day chart)                    │
│       ├─ Refinery status (operating / at-risk / idle)              │
│       ├─ SPR depletion curve                                       │
│       ├─ GDP impact ($), Fuel price impact (%), Power stress (MW)  │
│       ├─ Procurement recommendations (if applicable)               │
│       └─ Assumption report (all assumptions documented)            │
│                                                                     │
│  [Compare Mode]                                                     │
│       └─ Side-by-side comparison of 2+ scenario runs               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### What Changes from Current Roadmap

| Aspect | Current Roadmap | Revised |
|--------|----------------|---------|
| Engine | Tick counter + inventory | Flow network with capacity constraints and cascade |
| Outputs | Supply gap only | Supply gap + GDP impact + fuel price + power stress |
| Modes | Run once | Continuous + Scenario + Compare |
| Geospatial | None | Yes — on Leaflet/Mapbox with flow animation |
| User interaction | Form → Results | Playground with drag, adjust, compare |
| Assumptions | None | Explicit registry per scenario (judging req) |
| Performance | Python loop | Python loop using NumPy for vectorized flow computation |

---

## 9. Scenario Engine

### 9.1 Does It Deserve Its Own Subsystem?

**Yes.** The Scenario Engine is the brain of the Digital Twin. It:
- Validates that user assumptions produce sensible outputs
- Provides the "testable assumptions" required by judging criteria
- Enables comparison across scenarios (judges love this)
- Is reusable across: Digital Twin, Procurement, SPR Optimizer

### 9.2 Scenario Engine Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SCENARIO ENGINE                                │
│                                                                     │
│  Inputs:                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  scenario_definition = {                              │           │
│  │    name: "Strait of Hormuz 30-day blockade",         │           │
│  │    template: "chokepoint_blockade",                   │           │
│  │    assumptions: [                                     │           │
│  │      { key: "hormuz_throughput_reduction_pct",        │           │
│  │        value: 80, unit: "percent",                    │           │
│  │        justification: "Based on 2025 US-Iran tension  │           │
│  │          when throughput dropped 75% for 10 days" },   │           │
│  │      { key: "disruption_duration_days",               │           │
│  │        value: 30, unit: "days",                        │           │
│  │        justification: "Worst-case DoD planning         │           │
│  │          scenario for Hormuz closure" }               │           │
│  │    ],                                                   │           │
│  │    affected_entities: ["strait_of_hormuz"],            │           │
│  │    economic_params: { crude_price: 85 },              │           │
│  │  }                                                      │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                     │
│  Engine:                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  1. Validate: check all assumptions are within        │           │
│  │     reasonable bounds (0 < reduction < 100)           │           │
│  │  2. Build: create simulation config from assumptions  │           │
│  │  3. Execute: run Digital Twin flow network for N ticks│           │
│  │  4. Measure: capture all output metrics per tick      │           │
│  │  5. Analyze: compute aggregate impacts                │           │
│  │  6. Explain: generate assumption sensitivity report   │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                     │
│  Outputs:                                                            │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  {                                                        │       │
│  │    summary: { supply_gap_bpd, gdp_impact_billion_usd,   │       │
│  │              fuel_price_increase_pct,                    │       │
│  │              refineries_at_risk: [...],                  │       │
│  │              spr_depletion_days, days_to_first_idle },   │       │
│  │    timeline: [{tick, supply_gap, refinery_utilization,   │       │
│  │                spr_inventory, fuel_price}],              │       │
│  │    assumptions_used: [...with sensitivity flags],        │       │
│  │    assumptions_validated: true/false,                    │       │
│  │    comparison_id: "..."  // if compared with another run │       │
│  │  }                                                        │       │
│  └──────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.3 Pre-Built Scenario Templates

| Template | Parameters | Defaults | Sensitivity |
|----------|-----------|----------|-------------|
| `chokepoint_blockade` | chokepoint_slug, throughput_reduction_pct, duration_days, affected_routes[] | 80%, 30 days, all | HIGH — duration and reduction % |
| `sanctions_escalation` | target_country, export_ban_volume_bpd, tariff_pct, duration_days | Iran, 500K bpd, 25%, 90 days | HIGH — ban volume |
| `natural_disaster` | disaster_type, affected_region, ports_offline[], refineries_offline[], duration_days | Cyclone, Gujarat, [Kandla], [Jamnagar], 14 days | HIGH — duration |
| `supplier_disruption` | supplier_uuid, disruption_pct, duration_days | Saudi Aramco, 50%, 14 days | MEDIUM — disruption % |
| `cyber_attack` | target_type, target_uuid, duration_days, recovery_rate_bpd | Port, JNPT, 7 days, 10% | LOW — duration |
| `custom` | Assumptions defined by user | User-specified | VARIES |

### 9.4 Integration Points

| Integrates With | How |
|----------------|-----|
| **Risk Intelligence Agent** | Scenario Agent is triggered by Risk Agent escalation |
| **Digital Twin** | Scenario Engine calls Digital Twin simulation under the hood |
| **Procurement Orchestrator** | Scenario results feed procurement alternative analysis |
| **SPR Optimizer** | Scenario supply gap feeds SPR drawdown optimization |
| **Frontend** | Scenario Playground UI, comparison view, assumption editor |

---

## 10. Adaptive Procurement Orchestrator

### 10.1 Critique of Current Design

The current Procurement Recommendation Engine is a weighted formula ranker:
- Input: commodity, destination, weight preferences
- Output: ranked list by overall_score = Σ(weight_i × score_i)

**What's missing:**
1. **No agentic behavior** — It's a function, not an orchestrator. It doesn't proactively find alternatives when a disruption is detected.
2. **No real-time data** — No spot prices, no tanker availability, no port congestion.
3. **No sanctions check** — A supplier might be under sanctions. The system doesn't check.
4. **No refinery compatibility** — The system doesn't verify that alternative crude can be processed by the destination refinery.
5. **No executable output** — A ranked list is not actionable. Procurement teams need to know "who to call, what to ask for, and how much it costs."
6. **No confidence score** — Every recommendation should have calibrated confidence.

### 10.2 Redesigned Procurement Orchestrator

```
┌─────────────────────────────────────────────────────────────────────┐
│                  ADAPTIVE PROCUREMENT ORCHESTRATOR                   │
│                                                                     │
│  Trigger:                                                           │
│  ├─ Risk Agent escalation: "Supply disruption detected on Route X" │
│  ├─ User request: "Find alternatives for Jamnagar crude supply"    │
│  └─ Scheduled review: "Weekly procurement optimization run"        │
│                                                                     │
│  Step 1: Understand Current Supply                                  │
│  ├─ Query: Which refineries are affected? What crude do they need? │
│  ├─ Query: Who currently supplies them? How much?                  │
│  └─ Query: What contracts are active? (future: contract DB)        │
│                                                                     │
│  Step 2: Find Alternatives                                          │
│  ├─ Query suppliers: Who supplies this crude grade?                 │
│  ├─ Filter by sanctions: Are any suppliers sanctioned?              │
│  ├─ Filter by availability: Do they have spare capacity?            │
│  └─ Filter by logistics: Can the crude reach the refinery?         │
│                                                                     │
│  Step 3: Evaluate Routes                                            │
│  ├─ For each supplier, find all viable shipping routes              │
│  ├─ Query route risk (from Risk Agent)                              │
│  ├─ Query tanker availability (from AIS / fixtures)                 │
│  ├─ Query port congestion (origin and destination)                  │
│  └─ Query spot price (current market)                              │
│                                                                     │
│  Step 4: Check Refinery Compatibility                               │
│  ├─ Crude attributes: API gravity, sulfur content vs refinery spec │
│  ├─ Refinery constraints: nelson_complexity_index, accepted types  │
│  └─ Compatibility score: 0.0 (incompatible) to 1.0 (ideal)        │
│                                                                     │
│  Step 5: Rank Alternatives                                          │
│  ├─ Multi-objective: cost, risk, transit time, reliability          │
│  ├─ User-configurable weights                                       │
│  └─ Pareto frontier: dominated alternatives removed                │
│                                                                     │
│  Step 6: Generate Output                                            │
│  ├─ Ranked alternatives with scores and breakdowns                  │
│  ├─ Confidence score per alternative                                │
│  ├─ Executable RFQ template: "Contact Supplier X, request          │
│     Y barrels of Z grade at spot price + freight"                   │
│  └─ Explanation: "Route A is ranked #1 because 20% lower risk      │
│     outweighs 5% higher cost vs Route B"                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.3 Scoring Formula (Revised)

```
overall_score = Σ weight_i × normalized_score_i

Where:
  cost_score = 1 - (price_per_bbl - min_price) / (max_price - min_price)
  risk_score = 1 - route_risk_score  (from Risk Agent)
  transit_score = 1 - (transit_days - min_days) / (max_days - min_days)
  reliability_score = supplier_reliability  (from historical data)
  compatibility_score = refinery_compatibility  (from crude × refinery matching)
  sanctions_penalty = 0 if compliant, -100 if sanctioned (hard filter)

Default weights (configurable):
  cost: 0.30
  risk: 0.25
  transit: 0.15
  reliability: 0.15
  compatibility: 0.15
```

### 10.4 API Schema

```json
// POST /api/v1/intelligence/procurement/orchestrate
// Request
{
  "trigger": "disruption",
  "disruption_signal_uuid": "uuid-here",
  "refinery_uuids": ["jamnagar", "mangalore", "kochi"],
  "crude_grade": "brent_crude",
  "volume_bpd": 500000,
  "preferences": {
    "cost_weight": 0.30,
    "risk_weight": 0.25,
    "transit_weight": 0.15,
    "reliability_weight": 0.15,
    "compatibility_weight": 0.15
  },
  "constraints": {
    "max_risk_score": 0.7,
    "max_transit_days": 45,
    "exclude_sanctioned": true,
    "exclude_countries": ["iran", "russia"]
  }
}

// Response
{
  "query_id": "uuid",
  "generated_at": "2026-07-05T12:00:00Z",
  "total_alternatives_evaluated": 12,
  "ranked_alternatives": [
    {
      "rank": 1,
      "overall_score": 0.87,
      "recommendation": "Contact Saudi Aramco for 500K bpd Arabian Light via Ras Tanura → Arabian Sea → Jamnagar",
      "supplier": {
        "uuid": "...", "name": "Saudi Aramco", "country": "Saudi Arabia",
        "reliability_score": 0.92, "sanctions_status": "clear"
      },
      "route": {
        "description": "Ras Tanura → Strait of Hormuz → Arabian Sea → Gulf of Khambhat → Jamnagar",
        "distance_nm": 2450, "transit_days": 14,
        "chokepoints": ["Strait of Hormuz"],
        "route_risk_score": 0.35
      },
      "pricing": {
        "spot_price_bbl": 72.50,
        "freight_bbl": 3.20,
        "total_landed_bbl": 75.70,
        "vs_current_premium": 8.50,
        "vs_current_premium_pct": 12.6
      },
      "tanker_available": true,
      "tanker_type": "VLCC",
      "tanker_daily_rate": 45000,
      "port_congestion_origin": {"port": "Ras Tanura", "wait_hours": 12},
      "port_congestion_destination": {"port": "Jamnagar", "wait_hours": 8},
      "refinery_compatibility": {
        "refinery": "Jamnagar",
        "crude": "Arabian Light",
        "compatibility_score": 0.95,
        "notes": "Primary design crude. 100% compatible."
      },
      "breakdown": {
        "cost_score": 0.82,
        "risk_score": 0.75,
        "transit_score": 0.80,
        "reliability_score": 0.95,
        "compatibility_score": 0.95
      },
      "confidence": 0.85,
      "explanation": "Preferred despite 12.6% premium because Saudi Aramco has 92% reliability score and route risk is moderate (0.35). Second option (Iraq via Basra) is 5% cheaper but risk score is 0.55 due to Basra port congestion."
    }
  ]
}
```

---

## 11. Strategic Reserve Optimizer

### 11.1 Critique of Current Design

The current SPR Optimizer is `inventory / daily_draw = days_remaining`. This is too simple for:
1. **Multiple SPRs with different rates** — Vishakhapatnam can draw 100K bpd, Mangalore 50K bpd. They're not interchangeable.
2. **Refinery-specific demand** — Not all refineries can draw from all SPRs. Pipeline connectivity matters.
3. **Minimum reserve requirements** — SPRs should not be fully depleted. India maintains strategic minimums.
4. **Replenishment windows** — If you draw down, when can you replenish? At what price?
5. **Multi-period optimization** — Optimal drawdown changes day by day as new information arrives.

### 11.2 Redesigned SPR Optimizer

#### Optimization Formulation

```
Objective: Maximize Σ days_of_cover (across all refineries)

Subject to:
  Per-SPR:
    draw_rate_spr[t] ≤ max_drawdown_rate_spr  (∀ t)
    inventory_spr[t] = inventory_spr[t-1] - draw_rate_spr[t]  (∀ t)
    inventory_spr[t] ≥ minimum_reserve_spr  (∀ t)
    inventory_spr[0] = current_inventory_spr

  Per-Refinery:
    supply_to_refinery[r][t] = Σ draw_rate_spr[t] × connectivity[spr][r]
    throughput_refinery[r][t] = min(demand[r], supply_to_refinery[r][t] + other_supply[t])
    days_of_cover[r] = first t where throughput_refinery[r][t] < demand[r] × threshold

  Aggregate:
    total_days_of_cover = min(days_of_cover[r] across all refineries)
```

#### Implementation

```
Algorithm: Multi-SPR Linear Programming (simplified greedy for hackathon)

1. Sort SPRs by: (max_drawdown_rate, distance_to_refinery) — nearest with highest rate first
2. For each day:
   a. Calculate total supply gap = total_refinery_demand - unaffected_supply
   b. For each SPR (in priority order):
      - Allocate draw = min(SPR_remaining_draw_capacity, remaining_gap)
      - Update SPR inventory
      - Update remaining gap
   c. For each refinery:
      - Allocate SPR supply based on connectivity
      - If refinery gap > 0 → mark "at risk"
   d. Check: any refinery inventory < 7 days → "critical"
   e. Check: total SPR inventory < 30 days → "warning"
3. Output:
   - Drawdown schedule (barrels/day per SPR, per day)
   - Days until first refinery at risk
   - Days until any refinery idle
   - Days until SPR depleted (excluding minimum reserve)
   - Replenishment: volume_needed = initial_inventory - final_inventory
   - Replenishment: days_needed = volume_needed / max_replenishment_rate
   - Replenishment: estimated_cost = volume_needed × forecast_price
```

### 11.3 API Schema

```json
// POST /api/v1/intelligence/spr/optimize
// Request
{
  "scenario_uuid": "uuid-from-scenario-engine",
  "or": {
    "supply_gap_bpd": 3500000,
    "duration_days": 30,
    "affected_refinery_uuids": ["jamnagar", "mangalore", "kochi"]
  },
  "constraints": {
    "minimum_reserve_days": 30,
    "use_all_sprs": true,
    "spr_uuids": []
  }
}

// Response
{
  "run_id": "uuid",
  "status": "completed",
  "input": {
    "total_import_demand_bpd": 4500000,
    "affected_supply_bpd": 3500000,
    "unaffected_supply_bpd": 1000000,
    "net_gap_bpd": 2500000
  },
  "spr_status": [
    {
      "spr": "Vishakhapatnam SPR",
      "capacity_barrels": 5330000,
      "current_inventory": 4800000,
      "max_drawdown_bpd": 100000,
      "replenishment_bpd": 20000,
      "days_of_cover_at_optimal": 28,
      "optimal_daily_draw": 85000
    },
    {
      "spr": "Mangalore SPR",
      "capacity_barrels": 3300000,
      "current_inventory": 2970000,
      "max_drawdown_bpd": 80000,
      "replenishment_bpd": 15000,
      "days_of_cover_at_optimal": 25,
      "optimal_daily_draw": 75000
    }
  ],
  "refinery_impact": [
    {
      "refinery": "Jamnagar",
      "normal_demand_bpd": 1240000,
      "unaffected_supply": 400000,
      "spr_supply": 350000,
      "gap_bpd": 490000,
      "days_until_idle": 0,
      "days_at_reduced_capacity": 38,
      "status": "at_risk"
    }
  ],
  "aggregate": {
    "total_days_cover_without_spr": 0,
    "total_days_cover_with_optimal_draw": 38,
    "critical_date": "2026-08-12",
    "depletion_date": "2026-09-15",
    "total_spr_draw_bpd": 850000,
    "remaining_gap_bpd": 1650000
  },
  "replenishment_plan": {
    "total_volume_barrels": 38500000,
    "at_current_replenishment_rate_days": 385,
    "estimated_cost_at_spot": 2772000000,
    "cost_currency": "USD"
  }
}
```

---

## 12. Executive Dashboard

### 12.1 Design Principles

- **One glance, one answer:** "Is India's energy supply secure right now?"
- **Crisis mode:** When disruption detected, dashboard auto-activates crisis layout
- **Drill-down from 10,000ft to 10ft:** National view → Corridor view → Asset view
- **Action-oriented:** Every widget has a call-to-action button
- **Time-aware:** Show current state + trajectory (improving/worsening/stable)

### 12.2 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ INDIA ENERGY RESILIENCE POSTURE          ⚠ CRISIS ACTIVE            │
│ Last updated: 2026-07-05 14:30 IST                                  │
├─────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│ │ RISK     │ │ SUPPLY   │ │ DAYS OF  │ │ GDP      │ │ PROCUREMENT│ │
│ │ INDEX    │ │ GAP      │ │ COVER    │ │ IMPACT   │ │ ACTIONS   │ │
│ │          │ │          │ │          │ │          │ │           │ │
│ │ CRITICAL │ │ 2.5M BPD │ │ 38 DAYS  │ │ $2.1B    │ │ 4 OPEN    │ │
│ │ ████████ │ │ ████████ │ │ ████████ │ │ ████████ │ │ ████████  │ │
│ │ 78/100   │ │  -56%    │ │ ⬆ +28    │ │  -0.6%   │ │ Review >  │ │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Threat Map ───────────────────────────────────────────────────┐ │
│ │  [Leaflet/Mapbox map showing:]                                  │ │
│ │  • Vessel positions (moving dots along shipping routes)        │ │
│ │  • Port congestion (color-coded circles)                       │ │
│ │  • High-risk corridors (red/yellow/green lines)                │ │
│ │  • Refinery status (green=ok, yellow=at risk, red=idle)       │ │
│ │  • SPR locations with fill levels (pie chart markers)          │ │
│ │  • Active disruption signals (pulsing red icons)               │ │
│ │  • Click: opens asset detail sidebar                           │ │
│ └────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Supply Gap Timeline ───┐ ┌─ Refinery Status ──────────────────┐ │
│ │                         │ │                                     │ │
│ │  Gap (BPD) ▲            │ │  Jamnagar       ██░░░░░  40%       │ │
│ │  3M ┤╱╲                   │ │  Mangalore      ██████   60%      │ │
│ │  2M ┤╱  ╲                  │ │  Kochi          ████░░  55%      │ │
│ │  1M ┤╱    ╲                 │ │  BPCL Mumbai    ██░░░░  35%     │ │
│ │  0M ┼────────────────      │ │  HPCL Visakha   ████░░  50%     │ │
│ │     Day 0   15   30        │ │                                     │ │
│ └────────────────────────┘ └─────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Active Disruption Signals ───────────────────────────────────┐ │
│ │  ⚠ HIGH  Strait of Hormuz — IRGC activity detected     2 min │ │
│ │  ⚠ MED   Basra Port — Congestion 48hr+                15 min │ │
│ │  ℹ LOW   Oman — Tanker insurance +5%                   2 hrs │ │
│ └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.3 Widget Specifications

| Widget | Data Source | Refresh | Action |
|--------|-------------|---------|--------|
| **Risk Index** | Risk Agent aggregated | Real-time | Click → Risk Dashboard |
| **Supply Gap** | Scenario Engine / Digital Twin | On scenario change | Click → Scenario Details |
| **Days of Cover** | SPR Optimizer | On scenario change | Click → SPR Dashboard |
| **GDP Impact** | Scenario Engine | On scenario change | Click → Impact Breakdown |
| **Procurement Actions** | Procurement Orchestrator | On new recommendation | Click → Procurement Dashboard |
| **Threat Map** | GeoJSON from Energy Service + AIS | Real-time | Click asset → sidebar |
| **Supply Gap Timeline** | Scenario Engine output | On scenario change | — |
| **Refinery Status** | Digital Twin state | Per tick | Click → refinery detail |
| **Disruption Signals** | `disruption_signals` table | Real-time (Kafka → WS) | Click → investigate |

---

## 13. Analyst Dashboard

### 13.1 Design Principles

- **Signal-first:** The most important thing is what the system detected
- **Investigation workflow:** Detect → Analyze → Respond → Monitor
- **Evidence depth:** Every signal links to source data (article, AIS ping, price chart)
- **Confidence is explicit:** Every signal, every recommendation shows confidence

### 13.2 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ ENERGY INTELLIGENCE ANALYST                            [Crisis Mode]│
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Signal Feed (Real-time) ───────────────────────────────────────┐ │
│ │                                                                  │ │
│ │ ⚠ 14:28  Strait of Hormuz — IRGC vessel activity detected       │ │
│ │          Confidence: 78% | Source: AIS + News (3 articles)      │ │
│ │          [Investigate] [Escalate] [Dismiss]                     │ │
│ │                                                                  │ │
│ │ ⚠ 14:15  Brent crude +3.2% in last 4 hours                     │ │
│ │          Confidence: 65% | Source: OilPriceAPI                  │ │
│ │          [Investigate] [Escalate] [Dismiss]                     │ │
│ │                                                                  │ │
│ │ ℹ 13:00  OFAC adds 2 Iranian entities to SDN list              │ │
│ │          Source: OFAC RSS feed                                   │ │
│ │          [View Entity] [Check Impact]                           │ │
│ │                                                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Investigation Panel ──────────────────────────────────────────┐ │
│ │  [selected: Strait of Hormuz — IRGC activity]                   │ │
│ │                                                                  │ │
│ │  Signal Details:                                                 │ │
│ │  ┌─────────────────────────────────────────────────────┐        │ │
│ │  │ Type: ais_anomaly + news_correlation                │        │ │
│ │  │ First detected: 2026-07-05 14:26:30 IST            │        │ │
│ │  │ Sources: AIS (3 vessels off-course), News (3 arts) │        │ │
│ │  │ Affected: Strait of Hormuz, 12 tankers in transit  │        │ │
│ │  │ Similar to: 2025 US-Iran standoff pattern          │        │ │
│ │  └─────────────────────────────────────────────────────┘        │ │
│ │                                                                  │ │
│ │  Impact Assessment:                                              │ │
│ │  ┌─────────────────────────────────────────────────────┐        │ │
│ │  │ Scenario: 80% throughput reduction, 30 days         │        │ │
│ │  │ Supply gap: 2.5M BPD (56% of imports)              │        │ │
│ │  │ GDP impact: $2.1B (−0.6%)                          │        │ │
│ │  │ Refineries at risk: Jamnagar (Day 0), 4 more (Wk2)│        │ │
│ │  │ Procurement alternatives: 4 identified             │        │ │
│ │  │ [Run Full Simulation] [Compare Scenarios]          │        │ │
│ │  └─────────────────────────────────────────────────────┘        │ │
│ │                                                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Evidence Panel ────────────────────────────────────────────────┐ │
│ │                                                                  │ │
│ │  AIS Anomalies (Last 6 hours)                                    │ │
│ │  ┌─────────────────────────────────────────────────────┐        │ │
│ │  │ Tanker "MT Mumbai Express" — off-course by 12nm     │        │ │
│ │  │ Tanker "MT Gulf Explorer" — AIS off for 4 hours    │        │ │
│ │  │ Tanker "MT Hormuz Voyager" — loitering near 26.5N  │        │ │
│ │  └─────────────────────────────────────────────────────┘        │ │
│ │                                                                  │ │
│ │  Related News Articles                                           │ │
│ │  ┌─────────────────────────────────────────────────────┐        │ │
│ │  │ "IRGC deploys fast attack craft near Hormuz"       │ │        │ │
│ │  │   — Reuters, 2 hours ago [Read]                    │ │        │ │
│ │  │ "US Navy reports increased IRGC activity in Gulf" │ │        │ │
│ │  │   — AP News, 3 hours ago [Read]                   │ │        │ │
│ │  │ "Brent spikes 3% on Gulf tensions"                │ │        │ │
│ │  │   — Bloomberg, 1 hour ago [Read]                  │ │        │ │
│ │  └─────────────────────────────────────────────────────┘        │ │
│ │                                                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 14. Copilot Redesign

### 14.1 Critique of Current Design

The current Copilot is a single-turn QA system:
1. User asks a question
2. System does semantic search → gets articles
3. Applies rule-based threat + energy scoring
4. Returns structured summary

**Problems:**
- **No conversation memory** — Can't ask follow-up questions
- **No tool use** — Can't query databases, run simulations, or check real-time data
- **No proactive capability** — Can't alert the user to new risks
- **No visualization** — Returns text only

### 14.2 Redesigned Copilot (Energy Intelligence Assistant)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENERGY INTELLIGENCE ASSISTANT                     │
│                                                                     │
│  Architecture:                                                       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  LLM (GPT-4 / Claude)                                 │           │
│  │    ↓ Tool Layer                                       │           │
│  │  ┌────────────────────────────────────────────┐      │           │
│  │  │ Available Tools:                            │      │           │
│  │  │  • search_articles(query, filters)          │      │           │
│  │  │  • search_energy_entities(type, query)      │      │           │
│  │  │  • get_entity_details(type, uuid)            │      │           │
│  │  │  • get_supply_chain(type, uuid)              │      │           │
│  │  │  • get_risk_scores(type, uuid)               │      │           │
│  │  │  • get_current_prices(commodity)             │      │           │
│  │  │  • run_simulation(scenario_config)           │      │           │
│  │  │  • check_sanctions(entity_name)              │      │           │
│  │  │  • get_ais_vessel(vessel_name_or_imo)        │      │           │
│  │  │  • get_port_congestion(port_name)             │      │           │
│  │  │  • get_active_signals()                      │      │           │
│  │  │  • generate_report(template, data)            │      │           │
│  │  └────────────────────────────────────────────┘      │           │
│  │    ↓                                                │           │
│  │  Memory: Conversation history + session context     │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                     │
│  Interaction Examples:                                              │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ User: "What's the current risk posture for India?"   │           │
│  │                                                      │           │
│  │ Assistant: "I'll check our real-time risk assessment │           │
│  │  and active signals." → calls get_active_signals(),  │           │
│  │  get_risk_scores('location', 'india')                │           │
│  │                                                      │           │
│  │ "India's energy risk index is currently 78/100       │           │
│  │  (CRITICAL). We have 3 active disruption signals:    │           │
│  │  ⚠ Strait of Hormuz — IRGC activity                 │           │
│  │  ⚠ Basra Port — Congestion                          │           │
│  │  ℹ Oman — Tanker insurance +5%                      │           │
│  │                                                      │           │
│  │  With optimal SPR drawdown, India has 38 days of     │           │
│  │  cover. Without SPR, 0 days. Would you like me to   │           │
│  │  run a full scenario simulation?"                    │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ User: "Which refineries are most at risk?"            │           │
│  │                                                      │           │
│  │ Assistant: → calls get_supply_chain('refinery', ...) │           │
│  │  for top refineries, checks risk scores              │           │
│  │                                                      │           │
│  │ "Ranked by risk exposure:                            │           │
│  │  1. Jamnagar (Reliance) — 40% capacity — depends    │           │
│  │     on Hormuz transit for 60% of crude              │           │
│  │  2. Mangalore (MRPL) — 60% capacity — alternative   │           │
│  │     sourcing from Oman available                    │           │
│  │  3. Kochi (BPCL) — 55% capacity — least affected    │           │
│  │     as it sources primarily from Gulf via Red Sea   │           │
│  │                                                      │           │
│  │  Procurement alternatives available for Jamnagar.    │           │
│  │  Would you like to review them?"                     │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                     │
│  Proactive Mode:                                                    │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ System → User: "⚠ Risk escalation detected:          │           │
│  │  Strait of Hormuz disruption confidence now 85%      │           │
│  │  (was 78% 30 min ago). Impact assessment updated:    │           │
│  │  GDP impact revised from $1.8B to $2.4B.             │           │
│  │  4 procurement alternatives generated.               │           │
│  │  [View on Dashboard] [Acknowledge]"                  │           │
│  └──────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.3 Key Improvements Over Current

| Aspect | Current | Redesigned |
|--------|---------|------------|
| Interaction | Single-turn QA | Multi-turn conversation with memory |
| Capabilities | Semantic search only | 12 tools: search, query, simulate, check, report |
| Data access | Articles only | Articles + entities + supply chain + risk + prices + AIS + sanctions |
| Proactivity | None | Detects escalation thresholds, pushes alerts |
| Visualization | Text only | Tool outputs can include chart data/URLs |
| Confidence | Binary | Explicit confidence on every answer |

---

## 15. Final Implementation Roadmap

### 15.1 Revised Phasing

The original 4-phase, 8-week plan is too conservative. For a hackathon, this needs to be 3 sprints:

| Sprint | Focus | Duration | Builds On |
|--------|-------|----------|-----------|
| **Sprint 1** | Foundation + Risk Intelligence | Week 1 | Existing Energy Service |
| **Sprint 2** | Supply Chain + Digital Twin + Simulation | Week 2 | Sprint 1 |
| **Sprint 3** | Procurement + SPR + Dashboards + Polish | Week 3 | Sprint 2 |

### Sprint 1: Foundation + Risk Intelligence (Week 1)

**Database:**
- Create all new tables: risk_factors, risk_scores, disruption_signals, response_telemetry, commodity_prices
- Create ENUM: risk_dimension
- Add PostGIS extension (if not already)
- Seed risk_factors table (15 factors)

**Data Ingestion:**
- Build commodity price ingestor (poll EIA/OilAPI every 5 min → Kafka `commodity_prices`)
- Build OFAC sanctions ingestor (download CSV → parse → insert → `energy.sanctions`)
- Build AIS simulator (generate vessel positions along shipping routes → Kafka `ais_signals`)
- Build `disruption_signals` Kafka topic + producer

**Risk Intelligence Agent:**
- Build signal detection service (reads from: news pipeline, commodity_prices, ais_signals, sanctions_updates)
- Build risk scoring engine (per-entity, per-dimension, persists to `energy.risk_scores`)
- Build escalation logic (confidence × severity → alert)

**API:**
- Extend modular-api proxy with `/api/v1/intelligence/*`
- Add `/api/v1/intelligence/risk/*` endpoints
- Add `/api/v1/intelligence/events/*` endpoints
- Add `/api/v1/intelligence/signals/*` endpoints

**Frontend:**
- Replace SVG map with Leaflet/Mapbox
- Add vessel position layer with animated movement
- Add port congestion heat map layer
- Build Analyst Dashboard (signal feed + investigation panel)
- Build Risk Dashboard (heatmap of risk scores)

**Integration:**
- Wire Agent Orchestrator background service into Energy Service lifespan
- Connect Risk Agent to existing energy_entity_mappings for NER→asset linking
- Wire response_telemetry throughout the pipeline

### Sprint 2: Supply Chain + Digital Twin + Scenario Engine (Week 2)

**Database:**
- Create: supply_chain_edges, risk_propagation, simulation_scenarios, simulation_runs, simulation_tick_events, simulation_entity_state, scenario_assumptions
- Seed supply chain edges from existing entity_relationships + manual curation

**Supply Chain Graph:**
- Build auto-builder: traverse entity_relationships → create directed supply_chain_edges
- Build risk propagation engine (BFS from risk source, decay factor per edge)
- Build path finding (Dijkstra on supply chain edges)

**Digital Twin:**
- Implement flow network model in Python (NumPy-optimized)
- Implement cascade rules (upstream failure → downstream impact)
- Implement alternative route finding during simulation
- Implement economic impact layer (supply gap → GDP → fuel price → power)

**Scenario Engine:**
- Implement scenario configurator + validator
- Build 5 pre-built scenario templates (Hormuz, sanctions, cyclone, Suez, supply disruption)
- Build scenario comparison engine (side-by-side metrics)
- Build assumption registry (document every parameter + justification)

**API:**
- Add `/api/v1/intelligence/supply-chain/*` endpoints
- Add `/api/v1/intelligence/digital-twin/*` endpoints
- Add `/api/v1/intelligence/scenarios/*` endpoints

**Frontend:**
- Build Digital Twin Playground (scenario configurator + simulator + results)
- Build Scenario Comparison view (side-by-side)
- Build Supply Chain Graph Explorer (interactive D3.js directed graph)
- Add supply chain overlay to map (edge lines with utilization color)

**Agent Integration:**
- Wire Scenario Modeling Agent to Digital Twin
- Wire Scenario Agent to Risk Agent (auto-trigger on escalation)

### Sprint 3: Procurement + SPR + Dashboards + Polish (Week 3)

**Database:**
- Create: refinery_crude_compatibility, procurement_recommendations, spr_optimization_runs, port_congestion, tanker_availability
- Seed refinery_crude_compatibility based on crude_types_accepted × commodity attributes

**Procurement Orchestrator:**
- Build alternative supplier finder
- Build route evaluator (risk, distance, tanker availability, port congestion)
- Build refinery compatibility checker
- Build multi-objective ranker (Pareto frontier)
- Build RFQ template generator

**SPR Optimizer:**
- Build multi-SPR LP optimizer
- Build refinery demand disaggregator
- Build replenishment planner
- Build confidence/report generator

**Executive Dashboard:**
- Build single-pane-of-glass layout
- Build threat map (Leaflet with all layers)
- Build KPI bar (risk index, supply gap, days of cover, GDP impact)
- Build crisis mode (auto-activates on high-severity signal)
- Build drill-down navigation (national → corridor → asset)

**Copilot:**
- Upgrade to multi-turn conversation with memory
- Integrate all 12 tools
- Add proactive alert capability

**Demo Preparation:**
- Build demo data pipeline (pre-seeded scenarios, pre-recorded signal sequence)
- Record 5-minute demo video script
- Prepare architecture diagram (C4 model)
- Prepare presentation deck

### 15.2 What to De-Prioritize (or Cut)

| Feature | Verdict | Justification |
|---------|---------|---------------|
| Bulk Import/Export UI | **Cut** | Useful but no judging impact |
| Capacity History Charts | **Cut** | Nice-to-have, no judging criteria |
| SVG Map (current) | **Keep as fallback** | Replace with Leaflet as primary |
| Power plants / Gas fields detail | **Deprioritize** | Oil import focus for hackathon |
| Refinery compatibility seed data | **Manual seed** | Don't spend time on comprehensive API |
| Historical validation | **Brief only** | Validate 2025 US-Iran if data available |

---

## 16. ML Platform Plan

### 16.1 Models for Future Implementation

| # | Model | Phase | Problem | Training Data | Features | Labels | Metric | Deployment |
|---|-------|-------|---------|-------------|----------|--------|--------|------------|
| 1 | **XGBoost Corridor Risk** | 3A | Predict corridor disruption probability (binary) | Historical disruptions (2020-2026), news events, sanctions, AIS anomalies | Event count (30d), sentiment trend, sanctions active, AIS anomaly count, insurance change, seasonality | Disruption occurred (0/1) | AUC-ROC, Precision@K | ML Platform, 15-min batch |
| 2 | **Prophet/LightGBM Price Forecast** | 3A | Brent crude 7-day price forecast | Daily Brent prices (10yr), inventory levels, risk score trend, geopolitical event calendar | Price history, risk index, days since last disruption, OPEC meeting schedule | Price t+7 | MAE, MAPE | ML Platform, daily |
| 3 | **LightGBM Supplier Reliability** | 3B | Supplier reliability score (0-1) | Supplier attributes, delivery history, country risk, sanctions | Market share, country risk, org type, sanctions count, historical delivery rate | Reliability rating | RMSE, Calibration | ML Platform, weekly batch |
| 4 | **LambdaMART Procurement Ranker** | 3B | Rank procurement alternatives | Historical procurement decisions, simulation results, human preferences | Cost, risk, transit, compatibility, reliability, sanctions flag | Human rank order | NDCG@5, MRR | ML Platform, on-demand |
| 5 | **Isolation Forest AIS Anomaly** | 3A | Detect anomalous vessel behavior | AIS position history, route patterns, port calls | Speed deviation, route deviation, loitering time, AIS off duration | Anomaly score (0-1) | Precision@K, F1@K | Streaming (Flink) |
| 6 | **LLM Fine-tune (Signal Extraction)** | 3C | Extract geopolitical signals from news | Labeled news articles (signal vs no-signal, escalation type) | Article text, headline, source, published date | Signal type + confidence | F1, Precision | LLM API + cache |
| 7 | **GNN Supply Chain Vulnerability** | 3C | Identify critical nodes in supply chain | Supply chain graph, historical disruption propagation, entity attributes | Node features + graph topology + edge weights | Node criticality score | NDCG@K | ML Platform, weekly batch |

### 16.2 Inference Pipeline (Future)

```
Data Stream ──► Feature Store ──► Model Registry ──► Prediction API ──► Intelligence Layer
                      │                  │
                      ▼                  ▼
               Feature Vectors      Model Versions
                  (ml.feature         (ml.model_versions)
                   _definitions)
```

### 16.3 ML Platform Requirements (Not Implemented Yet)

The existing `ml.` schema already has: `feature_definitions`, `datasets`, `model_versions`, `predictions`. The ML Platform (port 8007) already has training pipeline code. When Phase 3 begins:
1. Add feature pipelines for each model
2. Add training jobs (scheduled or triggered)
3. Add batch inference pipelines
4. Add online inference API
5. Add model monitoring (drift detection, performance decay)

---

## 17. Deliverables & Architect's Sign-Off

### 17.1 Submission Deliverables Checklist

| Deliverable | Status | Owner |
|------------|--------|-------|
| **Working Prototype** | Phase 1: ✓ | Phase 2: Build in Sprints 1-3 |
| **Architecture Diagram** | C4 Context + Container + Component + Code diagrams | Create during Sprint 1 |
| **Presentation Deck** | Executive (5 slides) + Technical (10 slides) + Demo (5 slides) | Create during Sprint 3 |
| **Demo Video** | 5 minutes covering all 5 judging criteria | Script during Sprint 3, record at end |

### 17.2 Architecture Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Multi-agent system | 4 agents with tool-calling | Problem requires agentic AI; 4 agents cover all capabilities without overlap |
| Streaming pipeline | Kafka + lightweight consumers | Batch-only fails "lead time" criterion; streaming enables real-time risk |
| Digital twin engine | Flow network with NumPy | Simple enough for hackathon, powerful enough for real use |
| Scenario simulation | Deterministic + assumption registry | "Testable assumptions" is a judging criterion |
| LLM integration | API-based with abstraction layer | Enables demo with GPT-4, production swap to fine-tuned Llama |
| ML model progression | Rule-based → XGBoost → GNN | Build for data collection first, then improve with ML |
| Geospatial visualization | Leaflet/Mapbox | Real map tiles for "geospatial evidence depth" criterion |
| Frontend dashboards | Executive + Analyst + Crisis Mode | Two distinct user types with different needs |

### 17.3 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AIS API unavailable | Medium | High | Build AIS simulator with realistic vessel movement |
| LLM API rate limits | Medium | Medium | Cache common queries, fallback to rule-based |
| Digital twin too slow | Low | Medium | NumPy vectorization, limit tick count to 90 |
| Data insufficient for ML | High | Medium | Use rule-based as fallback, collect data for Phase 3 |
| Real-time pipeline latency | Medium | Medium | Keep it simple: Kafka → consumer → DB → WS push |
| Leaflet performance with 5000+ assets | Medium | Low | Use clustering, limit visible asset types |

### 17.4 Future Roadmap

```
Phase 1 (Done)     Phase 2 (Hackathon)      Phase 3 (Production)
══════════════     ═══════════════════      ═══════════════════
Energy Service     Risk Intelligence        ML Models (7 models)
Kafka Pipeline     Supply Chain Graph       Fine-tuned LLM
Article Pipeline   Digital Twin             AIS Real Integration
Frontend Pages     Scenario Engine          Contract Database
                   Procurement Engine       Real-time Dashboard
                   SPR Optimizer            Mobile App
                   Executive Dashboard      Government Deployment
                   Copilot Upgrade          MeitY/NeGP Standards
```

### 17.5 Architect's Sign-Off

**Architecture Stability Assessment:**

The revised architecture is **stable and ready for implementation** under the following conditions:

1. **Sprint 1** can begin immediately on the foundation layer (all new tables, data ingestion, risk agent prototype). These are independent of Sprints 2-3 decisions.

2. **Sprint 2** (digital twin, scenario engine, supply chain graph) depends on Sprint 1's data infrastructure but the algorithmic design is well-understood (flow network, shortest path, deterministic simulation).

3. **Sprint 3** (procurement, SPR, dashboards, copilot) depends on Sprints 1-2 being complete but the UI design and optimization algorithms are well-understood.

4. **No architectural rewrites are anticipated** between sprints. Each sprint extends, does not replace.

5. **The only open question** is AIS API availability. If a real AIS API is available, the ingestion layer needs minor adjustment. If not, the simulator covers the same interface.

**Verdict:** ✅ **Begin implementation. The architecture is stable.**

---

> **End of Architectural Review**
>
> Total changes from original Phase 2 roadmap:
> - Added: 5 new data sources, 8 new database tables, 3 new Kafka topics, 3 new agents, 2 new dashboards, 1 geospatial layer, 1 scenario engine, 1 telemetry pipeline
> - Removed: SVG map as primary (replaced by Leaflet), capacity history charts, bulk import/export UI
> - Modified: Digital Twin (from tick counter to flow network), Procurement (from ranker to orchestrator), SPR (from formula to LP optimizer), Copilot (from QA to assistant)
> - Preserved: All existing Phase 1 code, Energy Service, Kafka pipeline, article enrichment, modular API pattern, frontend framework

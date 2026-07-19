# ProxyDefence Founding Engineer Interview Playbook

This is an interview preparation document for a founding-engineer, technical
co-founder, or early product-engineering role. It is written around
ProxyDefence, an India-first energy supply-chain resilience product. Use the
answers as structure, not as a script: answer in your own voice and never
claim customer outcomes, real-time coverage, accuracy, or revenue that has not
been validated.

## 1. The 60-second introduction

> I built ProxyDefence because an import-dependent economy cannot make a crude
> supply decision from a single news alert. A refinery planner needs to know
> which corridor is affected, what the supply gap could be, whether strategic
> reserves help, which crude alternatives fit the refinery, and what evidence
> supports the decision. ProxyDefence turns that chain into one auditable
> workflow: monitor a signal, assess a disruption scenario, produce a
> refinery-specific decision brief, record human approval, and retain the
> evidence and latency for learning. The first use case is a Hormuz disruption
> affecting Indian refiners. The product is decision support, not autonomous
> trading or reserve release.

## 2. The two-minute project walkthrough

Use this sequence in a demo or technical interview.

1. **Problem:** A disruption is not actionable until it is translated from a
   signal into a refinery and procurement decision.
2. **Signal:** News enters through the ingestion pipeline and is enriched into
   topic, entities, sentiment, and disruption-risk information.
3. **Assess:** The energy service matches a transparent scenario such as a
   partial Hormuz closure, then runs the digital twin.
4. **Decide:** The system models supply gap, SPR coverage, alternative sources,
   route/grade compatibility, risk, cost assumptions, and lead time.
5. **Approve:** The response creates a durable evidence bundle plus a human
   lifecycle: draft, reviewed, approved, executed, and outcome recorded.
6. **Learn:** Telemetry and historical replays make it possible to inspect
   latency, assumptions, and response consistency.

End with the boundary:

> The public demo is deliberately source-aware. Every input is marked live,
> cached, replayed, fallback, or disabled. It does not pretend that public data
> is a customer’s live cargo, inventory, assay, or approval system.

## 3. Product narrative and founder answers

| Question | Strong answer |
| --- | --- |
| What problem are you solving? | High-consequence energy supply decisions are fragmented across alerts, spreadsheets, operators, shipping tools, contracts, and calls. We make the decision path faster, reviewable, and auditable. |
| Who is the first buyer? | Indian refinery procurement and supply-planning teams. The initial user is the person preparing a disruption response, with management and risk/compliance as approvers. |
| Why start with Hormuz? | It is a concentrated, understandable, high-impact corridor risk for India and maps cleanly to a narrow decision workflow. Narrow scope produces an executable product instead of a generic geopolitical dashboard. |
| Why not use an existing supply-chain suite? | Generic tools track assets and forecasts, but the differentiator is the chain from geopolitical signal to scenario, refinery constraints, alternatives, evidence, and approval. Integration is a future requirement, not a reason to avoid the workflow wedge. |
| Why now? | Geopolitical and shipping risk make planning less predictable, while public intelligence, operational data connectors, and AI-assisted workflow software make a traceable decision layer technically possible. |
| What is the moat? | Not generic news summarisation. It is the accumulating configuration and outcome data: refinery constraints, approved decision logic, evidence trails, user feedback, and event outcomes—collected only with customer permission. |
| What is the business model? | Start with a paid pilot for one refinery/site, then an annual software subscription plus implementation/integration for approved internal data. Price only after discovery identifies workflow value and data-integration effort. |
| What do you refuse to claim? | Predictive accuracy, realised cost savings, headcount reduction, sanctions clearance, live AIS coverage, or autonomous execution without a measured customer baseline and validated data. |

## 4. Technical architecture in one answer

> ProxyDefence is an event-driven microservice application. News flows from an
> ingest service through Kafka to ML enrichment, then to PostgreSQL and
> Elasticsearch. The energy service is the domain decision engine: it owns the
> infrastructure catalog, source-status records, risk calculations, digital
> twin, SPR logic, procurement optimizer, historical replays, evidence bundles,
> and telemetry. A FastAPI modular gateway provides authentication and
> aggregates protected APIs for a React command center. PostgreSQL is the
> authoritative decision store; Elasticsearch is search; Kafka is transport.
> The frontend is deliberately workflow-shaped: Monitor → Assess → Decide →
> Approve → Learn.

### Service map

| Component | Port | Interview explanation |
| --- | ---: | --- |
| React frontend | 8080 | Operator command center and decision review UI. |
| Modular API | 8000 | JWT-protected gateway, Copilot/RAG, composition layer. |
| Ingest service | 8001 | Fetches configured news and publishes `raw_articles`. |
| Database service | 8003 | Processes enriched article records and search indexing. |
| Embedding service | 8005 | Vector/embedding processing. |
| Energy service | 8006 | Core resilience decision engine. |
| ML platform | 8007 | Dataset/model registry, risk serving, enrichment consumer. |
| PostgreSQL / Kafka / Elasticsearch | 5434 / 9092 / 9200 | State, event transport, and search. |

For the authoritative code map, read [Codebase Guide](11_CODEBASE_GUIDE.md).

## 5. Deep technical questions and answers

### System design

**Why microservices instead of a monolith?**

The product already has distinct operational boundaries: ingestion, article
processing, model serving, decisioning, and UI. Kafka isolates article traffic
from request-time decisions. I would not choose microservices merely for
fashion; at an earlier stage I would keep shared schemas, a single deployment
runbook, and a narrow golden path so complexity is justified by the workflow.

**What happens when Kafka is unavailable?**

New article ingestion/enrichment is delayed, but existing catalog state,
persisted signals, source status, historical replays, and evidence remain
available. The UI must show freshness and mode, not silently treat stale data
as current. A production design adds consumer lag alerts, a retry/dead-letter
strategy, and operational runbooks.

**Why PostgreSQL and Elasticsearch?**

PostgreSQL stores authoritative, relational, auditable records: source
provenance, scenarios, telemetry, approvals, and evidence. Elasticsearch is
optimised for article search. The system must never require a search index to
reconstruct a decision record.

**How do you make a decision reproducible?**

Persist the selected signal, scenario assumptions, model/formula versions,
source observation/ingestion times, freshness/mode, twin output, SPR output,
procurement alternatives, approval history, and timing in an evidence bundle.

**How would you scale it?**

First measure bottlenecks. Then independently scale Kafka consumers, make
connector jobs idempotent, partition high-volume time series, cache immutable
catalog reads, queue expensive scenario jobs, and use explicit workload limits
per tenant. Keep decision records immutable/versioned and add tenant isolation
before serving multiple operators.

**How do you avoid a single slow external connector breaking a response?**

Connectors have bounded timeouts, cached/persisted observations, source modes,
freshness fields, and fallback reasons. Request-time decisioning uses the last
known, clearly labelled input rather than blocking indefinitely or inventing a
live result.

### Data and ML

**Which parts are ML and which are rules?**

Article enrichment and disruption-risk scoring use trained models. Corridor
risk blends model output and transparent dimensions. Scenario selection,
network flow, SPR drawdown, and procurement constraints are largely explicit
and deterministic by design. That is appropriate because operators need to
inspect assumptions and override them.

**Why not make the entire system an LLM agent?**

An LLM is useful for extracting and explaining unstructured intelligence, but
it should not fabricate a supply gap, reserve release, or cargo compatibility.
Numerical calculations, constraints, provenance, and approvals belong in
deterministic services and data models.

**How do you evaluate predictive quality?**

Separate offline model metrics from operational value. Use time-split historical
replays, calibration, stability under small input changes, source freshness,
and outcome review. With a design partner, measure time-to-brief, handoffs,
evidence completeness, user acceptance, and the quality of post-event review.

**What is data leakage here?**

Using future prices, later article publication, known event outcomes, or a
post-disruption cargo decision as a feature for a pre-disruption prediction.
Prevent it with event-time joins, time-based splits, source timestamps, and
strictly versioned replay windows.

**How do you handle concept drift?**

Monitor source mix, missingness, entity distribution, score distribution,
prediction confidence, and delayed outcome labels. Retraining should be a
governed event with dataset/model versioning and a rollback path—not an
automatic overwrite of a production model.

**What does a 0.73 AUC mean?**

It is an offline discrimination metric for a specific labelled dataset and
split, not proof that the application predicts real geopolitical events at 73%
accuracy. Explain the label definition, horizon, class balance, calibration,
and baseline before citing any metric.

### Digital twin and procurement

**Is this a real digital twin?**

It is a scenario-driven network-flow simulation/digital-twin prototype. It
models infrastructure relationships and cascades using explicit assumptions.
It becomes a customer-grade twin only after it is configured and calibrated
against approved refinery, inventory, berth, grade, and contractual data.

**How do you calculate the supply gap?**

The scenario changes corridor/supplier availability and flow constraints; the
twin compares available supply with demand/run-rate assumptions over simulated
ticks. The response exposes the scenario assumptions so a user can challenge
them.

**How do you determine crude compatibility?**

The prototype compares catalog-level crude labels and refinery accepted grades.
That is a screening constraint, not a verified cargo assay. Customer data must
provide assay, blend, yield, unit constraints, and commercial approvals before
using it as a trade recommendation.

**Why is SPR optimisation sensitive?**

Reserve use is a policy and operational decision. The product recommends a
scenario-bound schedule; it never executes a release. In production, include
authorisation, reserve rules, replenishment economics, and human sign-off.

**How do you prevent procurement alternatives from double counting volume?**

Ranked alternatives are choices, not committed purchases. The orchestration
logic caps recommended volume against the modelled supply gap and stores the
distinction in the evidence bundle.

## 6. Security, reliability, and operations questions

**How is authentication handled?**

The modular API uses JWT authentication; protected routes require a bearer
token. Production/staging reject placeholder or short JWT secrets. Passwords
use bcrypt-based hashing. In production, secrets must come from a secret
manager and be rotated.

**What did you do to harden local infrastructure?**

Kafka, PostgreSQL, and Elasticsearch development mappings are bound to
`127.0.0.1`. API middleware adds `nosniff`, frame denial, referrer policy, and
permissions policy headers. This is a baseline, not full internet-exposure
security.

**What remains before a production deployment?**

Private networking, TLS, service authentication, least-privilege database
roles, backup/restore testing, audit-log retention, rate limits, ingress HSTS,
security monitoring, secret rotation, dependency scanning in CI, and a
customer security review.

**How do you test it?**

Use deterministic unit/integration tests, browser coverage for the command
center, authenticated pilot replay verification, service health checks, and a
live validation runner. The validation record distinguishes passed checks from
external-dependency warnings. See [Security and Validation Status](13_SECURITY_AND_VALIDATION.md).

**Tell me about a bug you found.**

The validator treated a valid Copilot response as empty because it looked for
`response`, `answer`, or `content`, while the API contract used `summary`. I
fixed the validator rather than changing a stable API into an inconsistent one,
then re-ran authenticated API checks. This is a good example of tracing a
contract mismatch before changing production behaviour.

## 7. Product-engineering trade-off questions

**What would you cut if you had two weeks?**

Keep only the Hormuz-to-refinery command path, three historical replays,
evidence bundle, approval lifecycle, and demo reliability. Defer generic RAG,
dashboard expansion, broad catalog features, and nonessential visualisations.

**What would you build next?**

1. Design-partner discovery and a data-permission plan.
2. Import the partner’s approved refinery configuration and decision workflow.
3. Add a continuous, contractually licensed AIS/sanctions connector.
4. Build a customer-specific replay/evaluation baseline.
5. Integrate with the customer’s approval and procurement systems only after
   security design and human-control agreement.

**What would make you stop pursuing this idea?**

If procurement teams do not treat disruption-response preparation as a costly,
urgent workflow; if their existing tools already solve it better; or if data
access and procurement cycles make the wedge uneconomic. Test these with
discovery before expanding engineering scope.

**How do you decide between accuracy and explainability?**

In a high-consequence workflow, traceability is a product requirement. I would
prefer an interpretable, calibrated, testable recommendation with clear
limitations over a marginally higher offline score that an operator cannot
challenge.

## 8. Behavioural interview bank

Use **Situation → Task → Action → Result → Learning**. Keep each answer under
two minutes.

| Prompt | ProxyDefence angle |
| --- | --- |
| Tell me about an ambiguous problem. | Turned a broad energy-security theme into one sharp workflow: Hormuz disruption to refinery-specific brief. |
| Tell me about a hard technical decision. | Used deterministic scenario/procurement calculations with ML as a bounded input instead of delegating safety-critical numbers to an LLM. |
| Tell me about a failure. | A full validator initially passed a stale process or reported a contract mismatch; fixed the checks and made the verifier validate every service and frontend. |
| Tell me about moving fast without breaking trust. | Added source modes and fallback reasons rather than using flashy but false “live intelligence” labels. |
| Tell me about disagreement. | Frame the discussion around the user decision, measurable risk, smallest experiment, and reversible versus irreversible choices. |
| Tell me about ownership. | Own the full path: infrastructure, API contracts, UI, reproducibility, docs, security gates, and demo evidence. |
| Tell me about customer empathy. | Do not assume a refinery wants automation; ask how a planner currently creates a brief, who approves it, and what data is trusted. |
| Tell me about quality. | Give concrete test evidence, state limitations, and avoid claims the data cannot support. |

## 9. Rapid-fire question bank

Prepare one-minute answers for each.

### Engineering

- How would you design multi-tenant isolation?
- How would you migrate schemas without downtime?
- How would you implement idempotent Kafka consumers?
- How do you version an API used by a frontend and a customer integration?
- How would you debug consumer lag?
- How do you handle duplicate articles and late-arriving events?
- What are SLOs for this product?
- How would you add distributed tracing?
- How would you test a failure of PostgreSQL, Kafka, Elasticsearch, or an
  external data provider?
- How would you protect against prompt injection in article content?
- How would you retain and delete customer data?
- How would you control model/model-feature rollout and rollback?

### Data, ML, and AI

- Explain precision, recall, ROC-AUC, PR-AUC, calibration, and thresholding.
- Why is a temporal holdout necessary?
- How would you build a ground-truth disruption dataset?
- How do you evaluate a ranking model?
- How do you detect hallucination in a decision brief?
- How do you cite and rank sources?
- Why do you need a knowledge graph rather than just vector search?
- What is the difference between a forecast, a scenario, and a recommendation?
- When should a model abstain?
- How would you make an LLM answer auditable?

### Product and business

- What is the smallest paid pilot?
- Who signs, who uses, and who blocks a purchase?
- What makes the buyer switch from spreadsheets?
- What data is necessary on day one versus later?
- What would you charge, and why?
- How will you measure ROI without inventing savings?
- What is the procurement/security review path?
- What competitors or substitutes exist?
- Why is this venture-scale or why is it not?
- What does success look like in 30, 90, and 365 days?

### Founder mindset

- Why are you the person to build this?
- What are you uniquely opinionated about?
- What is your unfair advantage, and what is not?
- What is the riskiest assumption?
- What do you need from a co-founder or founding engineer partner?
- How do you operate with no customer data yet?
- How do you choose what not to build?
- What would you do if the first pilot says no?

## 10. Questions you should ask the interviewer

Ask at least three.

- What is the company’s sharpest unsolved customer problem today?
- Which metric would make this hire an obvious success after six months?
- Where is engineering speed currently constrained: product clarity, data,
  reliability, hiring, sales, or process?
- How are customer requests prioritised against technical debt?
- What decisions would I own without waiting for approval?
- How close are engineers to users and customer calls?
- What is the current security/compliance bar and who owns it?
- What does a difficult disagreement look like in this team?
- What is the company willing to stop doing to win its primary wedge?

## 11. Mock interview plan

### Session 1 — Founder/product (45 minutes)

1. Give the 60-second introduction.
2. Whiteboard the user workflow and first buyer.
3. Defend the market wedge and explain what you would test first.
4. Answer five behavioural questions.

### Session 2 — System design (60 minutes)

1. Draw signal → decision → evidence.
2. Explain ownership of every service and datastore.
3. Design for a tenfold increase in customers and events.
4. Walk through one connector outage and one bad recommendation.

### Session 3 — Code and reliability (60 minutes)

1. Run the pilot verifier.
2. Show a historical replay and its evidence bundle.
3. Explain one test, one security control, and one known limitation.
4. Describe exactly what customer data you would need next.

### Session 4 — Tough panel (45 minutes)

Have someone challenge every claim: accuracy, data freshness, market size,
customer willingness to pay, execution risk, and security. Practice saying
“we do not know yet; here is the experiment that would answer it.”

## 12. Final interview checklist

- Know the 60-second, two-minute, and ten-minute versions of the story.
- Demo the Hormuz replay; do not depend on an unpredictable live news event.
- State source modes before an interviewer has to ask.
- Know the difference between data that is public, cached, replayed, fallback,
  and customer-only.
- Bring the pilot runbook and evidence bundle.
- Never imply that the system executes a procurement trade or SPR release.
- Do not quote savings, accuracy, or headcount impact without customer evidence.
- End with the next concrete ask: a discovery call, design partner, or
  technical evaluation using approved data.

## Supporting project documents

- [Codebase Guide](11_CODEBASE_GUIDE.md)
- [Business Case](12_BUSINESS_CASE.md)
- [Public Demo Profile](10_PUBLIC_DEMO_PROFILE.md)
- [Pilot Demo Runbook](08_PILOT_DEMO_RUNBOOK.md)
- [Pilot Package](09_PILOT_PACKAGE.md)
- [Security and Validation Status](13_SECURITY_AND_VALIDATION.md)

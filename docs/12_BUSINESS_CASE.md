# ProxyDefence Business Case

## Problem

Indian refiners make time-sensitive crude-sourcing decisions during corridor
disruption, sanctions changes, and supply outages. The decision combines
geopolitical context, supply routes, refinery constraints, reserve availability,
commercial alternatives, and human approval. These inputs are commonly spread
across alerts, spreadsheets, logistics tools, and calls.

The initial buyer is a refinery procurement or supply-planning team. The initial
job is not "predict geopolitics"; it is to compress the path from a material
disruption signal to a reviewable, source-traceable decision brief.

## Product answer

ProxyDefence chains five steps in one operational record:

1. Detect or replay a disruption signal.
2. Select a transparent scenario and simulate its network impact.
3. Quantify supply gap, refinery run-rate implications, and SPR coverage.
4. Rank procurement alternatives by cost, risk, lead time, and available
   catalog constraints.
5. Save an evidence bundle and human approval lifecycle.

For public demonstrations, the workflow is explicitly based on sourced,
cached, replayed, or fallback inputs. It never represents an illustrative result
as a live trade instruction.

## Public evidence base

- PPAC lists 33.0 MMTPA for RIL Jamnagar (DTA), 35.2 MMTPA for RPL Jamnagar
  (SEZ), and 258.116 MMTPA total installed Indian refining capacity as of its
  current capacity table.
- ISPRL describes Phase-I strategic storage at Visakhapatnam, Mangalore, and
  Padur; its public facility pages list 1.33, 1.50, and 2.50 MMT respectively.
- The IEA states that in 2025 nearly 20 mb/d of oil transited Hormuz and most
  flowed to Asia; India is one of the principal importers.

Sources are linked in [Public Demo Profile](10_PUBLIC_DEMO_PROFILE.md).

## What has been demonstrated

| Measure | Evidence | Interpretation |
| --- | --- | --- |
| Response execution | Authenticated replay through the API gateway | The engines can create a persistent decision record |
| Historical cases | Abqaiq 2019, Russia sanctions 2022, Red Sea 2024 | Scenario-selection/replay coverage, not predictive accuracy |
| Operator flow | Playwright command-center test | A user can target a refinery, run a response, inspect evidence, and mark review |
| Decision traceability | Evidence bundle, source modes, approval history, telemetry | Enables audit and post-event learning |
| Frontend dependency audit | `npm audit --omit=dev` | Zero current production frontend advisories after remediation |

## Metrics we will and will not claim

### Measured in the prototype

- Pipeline latency for each response, stored in `energy.response_telemetry`.
- Scenario run duration, supply gap, SPR coverage, and recommendation output.
- Historical replay directional scenario-selection checks.
- Source freshness/mode and evidence-bundle completeness.

### Not yet validated

- Predictive disruption accuracy or economic impact accuracy.
- Headcount savings, cost savings, or refinery-margin improvement.
- Cargo execution rate, real-time AIS coverage, or sanctions-compliance coverage.
- A customer-specific compatible-cargo recommendation.

Those claims require a design partner's baseline process, approved operational
data, and observed outcomes. Until then, the appropriate value claim is **faster,
more traceable decision preparation**, not guaranteed commercial performance.

## Claim-status scorecard

| Topic | What the public prototype can evidence | What it cannot truthfully claim yet |
| --- | --- | --- |
| Disruption accuracy | Replay scenario selection and source-mode traceability | Forward-looking disruption-prediction accuracy or calibrated probability accuracy |
| Decision efficiency | Timed software pipeline stages in `energy.response_telemetry` | End-to-end operator time saved versus a refinery's current process |
| Cost / margin impact | Ranked, explicitly assumption-bound options | Realised savings, avoided premiums, or refinery-margin improvement |
| Headcount | A reusable brief/evidence workflow that may reduce manual coordination | Headcount reduction, FTE savings, or staffing recommendations |
| Compliance and execution | Human approval state is retained; no trade is issued | Sanctions clearance, cargo nomination, reserve release, or autonomous execution |

For a pilot, measure the missing business outcomes against the customer's
existing process: signal-to-brief time, number of manual handoffs, evidence
completeness, operator acceptance, and outcome after an approved tabletop or
live event. Do not convert those measurements into public claims without the
customer's permission and a documented baseline.

## Pilot offer

Offer a six-week, one-refinery public/approved-data pilot:

1. Configure approved refinery constraints and approval workflow.
2. Run weekly intelligence briefs.
3. Conduct a Hormuz or Red Sea tabletop event.
4. Measure time-to-brief, evidence completeness, scenario usefulness, and
   operator feedback.

Success is a documented operator decision workflow and a decision on whether to
integrate approved internal data—not an autonomous procurement deployment.

## YC positioning

ProxyDefence starts with a narrow operational wedge: Indian refinery teams need
to make defensible sourcing decisions during disruption. Its compounding asset is
not generic news summarisation; it is the evolving combination of refinery
configuration, decision evidence, approvals, and observed outcomes, collected
with customer permission.

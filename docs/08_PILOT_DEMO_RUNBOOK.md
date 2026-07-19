# Pilot Demo Runbook

## Purpose

Demonstrate an evidence-backed response to a historical Hormuz-related supply disruption. The demo is decision support; it does not execute a purchase, reserve release, or operational change.

## Start

1. Start and verify the complete pilot stack with `scripts/demo/start-pilot.ps1`. It waits for the authenticated gateway replay, evidence bundle, and telemetry checks.
2. Run `scripts/demo/run-hormuz-replay.ps1 -Case abqaiq-2019` if you want the complete JSON response printed in the recording terminal.

## Demo Narrative

1. Open `/command` and identify the replayed disruption signal.
2. Trigger the response; show the scenario, supply gap, SPR coverage, and procurement summary.
3. Open **Decision evidence**. Explain each source badge: live, cached, replay, fallback, or disabled.
4. Mark the recommendation reviewed. This records a human approval action; it does not execute a trade.
5. Open the map, SPR, and procurement views to inspect the supporting simulation and alternatives.

## Recording Script (2–3 Minutes)

- **0:00–0:20:** India refinery problem and the Hormuz exposure.
- **0:20–0:50:** Show the replayed signal and source-provenance badges.
- **0:50–1:35:** Run the response pipeline and explain supply-gap/twin output.
- **1:35–2:10:** Show SPR drawdown and procurement trade-offs.
- **2:10–2:35:** Show the evidence bundle and operator review record.
- **2:35–3:00:** State limits: replay/cached data is labeled; no trade is automatically executed.

## Acceptance

The run is valid only when the telemetry record, evidence-bundle UUID, and decision-source modes are present. Do not claim live AIS or country-level sanctions intelligence unless the source-status endpoint reports it.

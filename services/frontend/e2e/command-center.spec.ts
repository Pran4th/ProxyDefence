import { expect, test } from "@playwright/test";

const signal = { uuid: "11111111-1111-4111-8111-111111111111", title: "Replay: Strait of Hormuz shipping disruption", severity: "critical", created_at: "2026-07-19T08:00:00Z" };
const responseBundle = {
  signal,
  scenario: { uuid: "22222222-2222-4222-8222-222222222222", name: "Strait of Hormuz Partial Closure", severity: "critical" },
  twin_run: { run_uuid: "33333333-3333-4333-8333-333333333333", ticks_executed: 7, execution_time_ms: 320, aggregate_impacts: { max_supply_gap_bpd: 4115000, economic_impact_usd: 1200000000, gdp_impact_pct: 0.2 } },
  spr_run: { results: { coverage_pct: 22, days_until_depletion: 9 }, recommendations: [{ title: "Release Indian SPR", summary: "Release only Indian SPR inventory against the forecast gap.", severity: "high" }] },
  procurement_run: { executive_summary: "Select the compatible alternative crude option within the stated supply gap.", recommendations_count: 4, pareto_count: 2, total_risk_score: 0.31 },
  evidence_bundle: { uuid: "44444444-4444-4444-8444-444444444444", mode: "fallback", input_provenance: [{ source: "ais", display_name: "AIS snapshot", mode: "cached", observed_at: "2026-07-18T00:00:00Z", freshness_seconds: 86400, fallback_reason: "Snapshot feed; not real-time AIS." }], decision_brief: {} },
  telemetry: { uuid: "55555555-5555-4555-8555-555555555555", signal_detected_at: "2026-07-19T08:00:00Z", analysis_started_at: "2026-07-19T08:00:01Z", analysis_completed_at: "2026-07-19T08:00:02Z", recommendation_generated_at: "2026-07-19T08:00:02Z", total_latency_seconds: 1.1, pipeline_latency_seconds: 1.1 },
};

test("operator can run and review an evidence-backed Hormuz decision", async ({ page }) => {
  let commandPayload: Record<string, unknown> | undefined;
  await page.addInitScript(() => {
    localStorage.setItem("proxydefence.token", "e2e-token");
    localStorage.setItem("proxydefence.user", JSON.stringify({ id: 1, email: "operator@example.test", username: "operator", role: "operator", created_at: "2026-07-19T00:00:00Z" }));
  });
  await page.route("http://localhost:8000/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/auth/me") return respond({ id: 1, email: "operator@example.test", username: "operator", role: "operator", created_at: "2026-07-19T00:00:00Z" });
    if (path.endsWith("/signals")) return respond({ items: [signal], total: 1, limit: 12, offset: 0 });
    if (path.endsWith("/command/telemetry")) return respond({ items: [], total: 0, pipeline_latency_p50_seconds: null, pipeline_latency_p95_seconds: null });
    if (path.endsWith("/corridors")) return respond({ corridors: [], assumptions: [], ais_snapshot_at: null, computed_at: "2026-07-19T00:00:00Z" });
    if (path.endsWith("/energy/refineries")) return respond({ items: [{ uuid: "66666666-6666-4666-8666-666666666666", name: "Jamnagar Refinery", capacity_bpd: 1240000, nelson_complexity_index: 14, crude_types_accepted: ["arab_light"] }], total: 1, limit: 100, offset: 0 });
    if (path.endsWith("/command/respond") && route.request().method() === "POST") {
      commandPayload = route.request().postDataJSON() as Record<string, unknown>;
      return respond(responseBundle);
    }
    if (path.endsWith("/approval") && route.request().method() === "POST") return respond({ status: "reviewed" });
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: `Unexpected route ${path}` }) });
  });
  await page.goto("/command");
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await page.getByRole("combobox").click();
  await page.getByRole("option", { name: "Jamnagar Refinery" }).click();
  await page.getByRole("button", { name: "Respond to top threat" }).click();
  expect(commandPayload).toMatchObject({ auto: true, refinery_uuid: "66666666-6666-4666-8666-666666666666" });
  await expect(page.getByText("Signal → executable recommendation in 1.1s")).toBeVisible();
  await expect(page.getByText("4.1M bpd")).toBeVisible();
  await expect(page.getByText("AIS snapshot")).toBeVisible();
  await expect(page.getByText("Snapshot feed; not real-time AIS.")).toBeVisible();
  await page.getByRole("button", { name: "Mark reviewed" }).click();
  await expect(page.getByText("Decision marked reviewed", { exact: true })).toBeVisible();
});

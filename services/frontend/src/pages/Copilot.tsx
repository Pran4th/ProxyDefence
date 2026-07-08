import { useState } from "react";
import AppShell from "@/components/AppShell";
import EnergyImpactCard from "@/components/EnergyImpactCard";
import { queryCopilot } from "@/lib/api";

const Copilot = () => {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const runQuery = async () => {
    if (!question.trim()) return;

    try {
      setLoading(true);

      const data = await queryCopilot(question);

      setResult(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const getThreatColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case "critical":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      case "high":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30";
      case "medium":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      default:
        return "bg-green-500/20 text-green-400 border-green-500/30";
    }
  };

  return (
    <AppShell
      title="Intelligence Copilot"
      subtitle="AI-assisted geopolitical analysis and threat assessment"
    >
      <div className="space-y-6">

        <div className="rounded-3xl border border-border bg-card p-6">
          <div className="flex gap-4">
            <input
              type="text"
              placeholder="Ask Intelligence Copilot... (e.g. What is happening with Iran?)"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  runQuery();
                }
              }}
              className="flex-1 rounded-2xl border border-border bg-background px-4 py-4 text-sm outline-none"
            />

            <button
              onClick={runQuery}
              disabled={loading}
              className="rounded-2xl bg-blue-600 px-6 py-4 font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>
        </div>

        {result && (
          <div className="space-y-6">

            <div className="rounded-3xl border border-border bg-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-2xl font-bold">
                  Intelligence Assessment
                </h2>

                <span
                  className={`rounded-full border px-4 py-2 text-sm font-semibold ${getThreatColor(
                    result.threat_level
                  )}`}
                >
                  {result.threat_level?.toUpperCase() || "UNKNOWN"}
                </span>
              </div>

              <div className="whitespace-pre-line text-muted-foreground leading-7">
                {result.summary}
              </div>
            </div>

            {result.energy_impact && (
              <EnergyImpactCard impact={result.energy_impact} assessment={result.energy_assessment} />
            )}

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="mb-5 text-2xl font-bold">
                Key Actors
              </h2>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {result.entities?.map((entity: any) => (
                  <div
                    key={`${entity.entity_text}-${entity.entity_type}`}
                    className="rounded-2xl border border-border bg-background p-4"
                  >
                    <div className="text-lg font-semibold">
                      {entity.entity_text}
                    </div>

                    <div className="mt-2 text-sm text-muted-foreground">
                      Type: {entity.entity_type}
                    </div>

                    <div className="mt-1 text-sm text-muted-foreground">
                      Mentions: {entity.mentions}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="mb-5 text-2xl font-bold">
                Intelligence Reports
              </h2>

              <div className="space-y-4">
                {result.articles?.map((article: any) => (
                  <div
                    key={article.id}
                    className="rounded-2xl border border-border bg-background p-5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="font-semibold">
                          {article.title}
                        </h3>

                        <div className="mt-2 text-sm text-muted-foreground">
                          {article.source}
                        </div>
                      </div>

                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          article.risk_level === "critical"
                            ? "bg-red-500/20 text-red-400"
                            : article.risk_level === "high"
                            ? "bg-orange-500/20 text-orange-400"
                            : article.risk_level === "medium"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-green-500/20 text-green-400"
                        }`}
                      >
                        {article.risk_level}
                      </span>
                    </div>

                    <div className="mt-3 line-clamp-3 text-sm text-muted-foreground">
                      {article.summary}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="mb-5 text-2xl font-bold">
                Relationships
              </h2>

              <div className="space-y-3">
                {result.relationships?.map(
                  (relationship: any, index: number) => (
                    <div
                      key={index}
                      className="rounded-2xl border border-border bg-background p-4"
                    >
                      <div className="font-medium">
                        {relationship.source_entity}
                        <span className="mx-2 text-primary">→</span>
                        {relationship.target_entity}
                      </div>

                      <div className="mt-2 text-sm text-muted-foreground">
                        Relationship: {relationship.relationship_type}
                      </div>

                      <div className="text-sm text-muted-foreground">
                        Confidence:{" "}
                        {Math.round(
                          (relationship.confidence || 0) * 100
                        )}
                        %
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>

          </div>
        )}
      </div>
    </AppShell>
  );
};

export default Copilot;
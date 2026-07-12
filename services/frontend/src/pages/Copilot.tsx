import { useState } from "react";
import { Link } from "react-router-dom";
import { Bookmark, Loader2, Search as SearchIcon, Sparkles } from "lucide-react";
import AppShell from "@/components/AppShell";
import EnergyImpactCard from "@/components/EnergyImpactCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { queryCopilot, saveCopilotAnswerToCase, fetchCases, createCase, type Case, type CopilotResponse } from "@/lib/api";

const threatTone: Record<string, string> = {
  critical: "bg-destructive/15 text-destructive border-destructive/30",
  high: "bg-accent/15 text-accent border-accent/30",
  medium: "bg-warning/15 text-warning border-warning/30",
};

const riskTone: Record<string, string> = {
  critical: "bg-destructive/15 text-destructive",
  high: "bg-accent/15 text-accent",
  medium: "bg-warning/15 text-warning",
};

const Copilot = () => {
  const { toast } = useToast();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [cases, setCases] = useState<Case[]>([]);
  const [newCaseTitle, setNewCaseTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const runQuery = async () => {
    if (!question.trim()) return;
    setLoading(true);
    try {
      const data = await queryCopilot(question);
      setResult(data);
    } catch (error) {
      console.error(error);
      toast({ title: "Copilot query failed", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const openSaveDialog = async () => {
    setSaveOpen(true);
    try {
      setCases(await fetchCases());
    } catch (error) {
      console.error("Failed to load cases", error);
    }
  };

  const saveToExistingCase = async (caseId: number) => {
    if (!result) return;
    setSaving(true);
    try {
      await saveCopilotAnswerToCase({ case_id: caseId, question, answer: result });
      toast({ title: "Saved to case" });
      setSaveOpen(false);
    } catch (error) {
      console.error(error);
      toast({ title: "Failed to save to case", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const saveToNewCase = async () => {
    if (!result || !newCaseTitle.trim()) return;
    setSaving(true);
    try {
      const newCase = await createCase({ title: newCaseTitle });
      await saveCopilotAnswerToCase({ case_id: newCase.id, question, answer: result });
      toast({ title: "Case created and answer saved" });
      setSaveOpen(false);
      setNewCaseTitle("");
    } catch (error) {
      console.error(error);
      toast({ title: "Failed to create case", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell
      title="Intelligence Copilot"
      subtitle="Ask a question, get a synthesized analysis with sources, entities, and relationships"
    >
      <div className="space-y-6">
        <Card className="rounded-3xl border-border bg-card">
          <CardContent className="pt-6">
            <div className="mb-4 flex items-start gap-2 rounded-2xl border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <p>
                Copilot <strong className="text-foreground">reasons</strong> over the intelligence
                base and writes a synthesized answer — slower, but connects entities, articles, and
                relationships for you. Looking for a specific article or entity instead?{" "}
                <Link to="/search" className="text-primary hover:underline">
                  Use Search
                </Link>{" "}
                for fast keyword lookups.
              </p>
            </div>
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="e.g. What is happening with Iran and how does it affect oil markets?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runQuery()}
                className="flex-1 rounded-2xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
              />
              <Button onClick={runQuery} disabled={loading} className="gap-2 rounded-2xl px-6">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchIcon className="h-4 w-4" />}
                {loading ? "Analyzing…" : "Analyze"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {result && (
          <div className="space-y-6">
            <Card className="rounded-3xl border-border bg-card">
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
                <CardTitle className="text-xl">Intelligence Assessment</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge className={`border ${threatTone[result.threat_level?.toLowerCase()] ?? "bg-success/15 text-success border-success/30"}`}>
                    {result.threat_level?.toUpperCase() || "LOW"}
                  </Badge>
                  <Button size="sm" variant="outline" className="gap-1.5" onClick={openSaveDialog}>
                    <Bookmark className="h-3.5 w-3.5" /> Save to Case
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-line leading-7 text-muted-foreground">{result.summary}</p>
              </CardContent>
            </Card>

            {result.energy_impact && (
              <EnergyImpactCard impact={result.energy_impact} assessment={result.energy_assessment} />
            )}

            {result.entities?.length > 0 && (
              <Card className="rounded-3xl border-border bg-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Key Actors</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {result.entities.map((entity) => (
                    <div
                      key={`${entity.entity_text}-${entity.entity_type}`}
                      className="rounded-2xl border border-border bg-background p-4"
                    >
                      <p className="font-semibold">{entity.entity_text}</p>
                      <p className="mt-1 text-xs text-muted-foreground">Type: {entity.entity_type}</p>
                      <p className="text-xs text-muted-foreground">Mentions: {entity.mentions}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {result.articles?.length > 0 && (
              <Card className="rounded-3xl border-border bg-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Source Articles</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {result.articles.map((article) => (
                    <Link
                      key={article.id}
                      to={`/article/${article.id}`}
                      className="block rounded-2xl border border-border bg-background p-4 transition hover:border-primary/50"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-semibold">{article.title}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{article.source}</p>
                        </div>
                        <Badge className={riskTone[article.risk_level ?? ""] ?? "bg-success/15 text-success"}>
                          {article.risk_level}
                        </Badge>
                      </div>
                      {article.summary && (
                        <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{article.summary}</p>
                      )}
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {result.relationships?.length > 0 && (
              <Card className="rounded-3xl border-border bg-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Relationships</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {result.relationships.map((rel, i) => (
                    <div key={i} className="rounded-2xl border border-border bg-background p-3">
                      <p className="text-sm font-medium">
                        {rel.source_entity} <span className="mx-2 text-primary">→</span> {rel.target_entity}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {rel.relationship_type} · confidence {Math.round((rel.confidence || 0) * 100)}%
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save answer to a case</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {cases.length > 0 && (
              <div className="max-h-52 space-y-1.5 overflow-y-auto">
                {cases.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => void saveToExistingCase(c.id)}
                    disabled={saving}
                    className="flex w-full items-center justify-between rounded-xl border border-border bg-background px-3 py-2 text-left text-sm hover:border-primary/50 disabled:opacity-50"
                  >
                    {c.title}
                  </button>
                ))}
              </div>
            )}
            <div className="flex gap-2 border-t border-border pt-3">
              <input
                type="text"
                placeholder="Or create a new case…"
                value={newCaseTitle}
                onChange={(e) => setNewCaseTitle(e.target.value)}
                className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none"
              />
              <Button size="sm" onClick={() => void saveToNewCase()} disabled={saving || !newCaseTitle.trim()}>
                Create &amp; Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
};

export default Copilot;

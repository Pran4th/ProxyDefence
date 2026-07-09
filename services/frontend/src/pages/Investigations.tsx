import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import {
  fetchCases,
  fetchCase,
  createCase,
  addCaseNote,
  generateCaseReport,
  fetchReports,
  type Case,
  type IntelligenceReport,
} from "@/lib/api";
import { Shield, Plus, FileText, StickyNote, Loader2 } from "lucide-react";

const priorityVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  low: "secondary",
  medium: "outline",
  high: "default",
  critical: "destructive",
};

function CaseDetail({
  caseId,
  onReportGenerated,
}: {
  caseId: number;
  onReportGenerated: () => void;
}) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState("");
  const [submittingNote, setSubmittingNote] = useState(false);
  const [generating, setGenerating] = useState(false);
  const { toast } = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchCase(caseId);
      setDetail(data);
    } catch (err) {
      toast({ title: "Failed to load case", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  const handleAddNote = async () => {
    if (!note.trim()) return;
    setSubmittingNote(true);
    try {
      await addCaseNote(caseId, note);
      setNote("");
      await load();
      toast({ title: "Note added" });
    } catch {
      toast({ title: "Failed to add note", variant: "destructive" });
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleGenerateReport = async () => {
    setGenerating(true);
    try {
      await generateCaseReport(caseId);
      await load();
      onReportGenerated();
      toast({ title: "Intelligence brief generated" });
    } catch {
      toast({ title: "Failed to generate report", variant: "destructive" });
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <Skeleton className="h-32 w-full" />;
  if (!detail) return <p className="text-sm text-muted-foreground">Unable to load case.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-muted-foreground">
          {detail.items?.length ?? 0} linked items · {detail.notes_count ?? 0} notes ·{" "}
          {detail.reports?.length ?? 0} reports
        </span>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold">Notes</h4>
        <div className="space-y-2">
          {(detail.notes ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">No notes yet.</p>
          )}
          {(detail.notes ?? []).map((n: any) => (
            <div key={n.id} className="rounded-lg border border-border bg-background p-3 text-sm">
              <p>{n.note_text}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {new Date(n.created_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <Textarea
            placeholder="Add investigation note..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="min-h-[60px]"
          />
          <Button onClick={handleAddNote} disabled={submittingNote || !note.trim()} size="sm">
            {submittingNote ? <Loader2 className="h-4 w-4 animate-spin" /> : <StickyNote className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold">Generated reports</h4>
        {(detail.reports ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No intelligence brief generated yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {detail.reports.map((r: any) => (
              <li key={r.id} className="text-muted-foreground">
                {r.title} <span className="text-xs">({new Date(r.created_at).toLocaleDateString()})</span>
              </li>
            ))}
          </ul>
        )}
        <Button onClick={handleGenerateReport} disabled={generating} className="mt-3" size="sm">
          {generating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
            </>
          ) : (
            <>
              <FileText className="mr-2 h-4 w-4" /> Generate Intelligence Brief
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

export default function Investigations() {
  const [cases, setCases] = useState<Case[]>([]);
  const [reports, setReports] = useState<IntelligenceReport[]>([]);
  const [loadingCases, setLoadingCases] = useState(true);
  const [loadingReports, setLoadingReports] = useState(true);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [creating, setCreating] = useState(false);
  const { toast } = useToast();

  const loadCases = async () => {
    setLoadingCases(true);
    try {
      const data = await fetchCases();
      setCases(data);
    } catch {
      toast({ title: "Failed to load cases", variant: "destructive" });
    } finally {
      setLoadingCases(false);
    }
  };

  const loadReports = async () => {
    setLoadingReports(true);
    try {
      const data = await fetchReports();
      setReports(data);
    } catch {
      toast({ title: "Failed to load reports", variant: "destructive" });
    } finally {
      setLoadingReports(false);
    }
  };

  useEffect(() => {
    loadCases();
    loadReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateCase = async () => {
    if (title.trim().length < 3) {
      toast({ title: "Title must be at least 3 characters", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      await createCase({ title, description: description || undefined, priority });
      setTitle("");
      setDescription("");
      setPriority("medium");
      await loadCases();
      toast({ title: "Case created" });
    } catch {
      toast({ title: "Failed to create case", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  return (
    <AppShell
      title="Cases & Reports"
      subtitle="Investigation workspaces and the intelligence briefs generated from them."
    >
      <Tabs defaultValue="cases" className="space-y-6">
        <TabsList>
          <TabsTrigger value="cases">Cases</TabsTrigger>
          <TabsTrigger value="reports">All Reports</TabsTrigger>
        </TabsList>

        <TabsContent value="cases" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Open Investigation</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-4">
                <Input
                  placeholder="Case title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="md:col-span-2"
                />
                <Input
                  placeholder="Description (optional)"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <Select value={priority} onValueChange={setPriority}>
                  <SelectTrigger>
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleCreateCase} disabled={creating} className="mt-3">
                {creating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                Create Case
              </Button>
            </CardContent>
          </Card>

          {loadingCases ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : cases.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No cases yet. Open one above to start an investigation.
              </CardContent>
            </Card>
          ) : (
            <Accordion type="single" collapsible className="space-y-3">
              {cases.map((item) => (
                <AccordionItem key={item.id} value={String(item.id)} className="rounded-xl border border-border bg-card px-4">
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex flex-1 items-center justify-between pr-4">
                      <div className="flex items-center gap-3 text-left">
                        <Shield className="h-4 w-4 text-primary shrink-0" />
                        <div>
                          <p className="font-medium">{item.title}</p>
                          <p className="text-xs text-muted-foreground">{item.description}</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Badge variant="outline">{item.status}</Badge>
                        <Badge variant={priorityVariant[item.priority] ?? "outline"}>{item.priority}</Badge>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <CaseDetail caseId={item.id} onReportGenerated={loadReports} />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </TabsContent>

        <TabsContent value="reports" className="space-y-4">
          {loadingReports ? (
            <div className="space-y-3">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : reports.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No intelligence briefs generated yet. Generate one from a case.
              </CardContent>
            </Card>
          ) : (
            reports.map((report) => (
              <Card key={report.id}>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-primary" />
                    <CardTitle className="text-base">{report.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">{report.executive_summary}</p>
                  <div>
                    <h4 className="text-sm font-semibold">Threat Assessment</h4>
                    <p className="mt-1 text-sm text-muted-foreground">{report.threat_assessment}</p>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span>
                      Confidence: <strong>{report.confidence_score?.toFixed(0)}%</strong>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}

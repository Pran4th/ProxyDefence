import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Area,
  AreaChart,
  Legend,
} from "recharts";
import {
  ShoppingCart,
  AlertTriangle,
  BarChart3,
  DollarSign,
  Globe,
  RefreshCw,
  Truck,
  Shield,
  TrendingUp,
  CheckCircle,
  Zap,
  FileText,
  Play,
} from "lucide-react";

import {
  fetchProcurementHealth,
  fetchSuppliers,
  fetchProcurementRuns,
  enrichSuppliers,
  computeCompatibility,
  computeRouteCosts,
  runProcurementOrchestrator,
  fetchProcurementRun,
  fetchProcurementRecommendations,
  fetchExecutiveCards,
  acknowledgeExecutiveCard,
  type SimulationRun,
} from "@/lib/api";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/use-toast";

type TabValue = "overview" | "suppliers" | "compatibility" | "optimize" | "executive";

export default function Procurement() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabValue>("overview");

  const [runUuid, setRunUuid] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  // New run form
  const [simRunUuid, setSimRunUuid] = useState("");
  const [supplyGap, setSupplyGap] = useState("500000");
  const [optGoal, setOptGoal] = useState("balanced");
  const [maxCost, setMaxCost] = useState("100");
  const [maxRisk, setMaxRisk] = useState("0.8");
  const [maxLead, setMaxLead] = useState("60");

  const healthQuery = useQuery({
    queryKey: ["procurement-health"],
    queryFn: fetchProcurementHealth,
    refetchInterval: 30000,
  });

  const suppliersQuery = useQuery({
    queryKey: ["procurement-suppliers"],
    queryFn: fetchSuppliers,
  });

  const runsQuery = useQuery({
    queryKey: ["procurement-runs"],
    queryFn: () => fetchProcurementRuns(),
  });

  const runDetailQuery = useQuery({
    queryKey: ["procurement-run", selectedRun],
    queryFn: () => fetchProcurementRun(selectedRun!),
    enabled: !!selectedRun,
  });

  const recommendationsQuery = useQuery({
    queryKey: ["procurement-recommendations", selectedRun],
    queryFn: () => fetchProcurementRecommendations(selectedRun || undefined),
  });

  const execCardsQuery = useQuery({
    queryKey: ["procurement-exec-cards"],
    queryFn: () => fetchExecutiveCards(),
  });

  const mutationErrorToast = (title: string) => (err: any) =>
    toast({
      title,
      description: err?.response?.data?.detail ?? "Could not reach the energy service. Check that it's running.",
      variant: "destructive" as const,
    });

  const enrichMutation = useMutation({
    mutationFn: enrichSuppliers,
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["procurement-suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["procurement-health"] });
      toast({
        title: "Supplier enrichment complete",
        description: data?.enriched
          ? `${data.enriched} supplier profile(s) enriched with real signals.`
          : "All supplier profiles are already enriched -- nothing new to update.",
      });
    },
    onError: mutationErrorToast("Supplier enrichment failed"),
  });

  const compatMutation = useMutation({
    mutationFn: computeCompatibility,
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["procurement-health"] });
      toast({
        title: "Compatibility matrix computed",
        description: `${data?.refineries_evaluated ?? 0} refineries x ${data?.commodities_evaluated ?? 0} commodities evaluated` +
          (data?.pairs_created ? ` -- ${data.pairs_created} new pair(s) scored.` : " -- already up to date."),
      });
    },
    onError: mutationErrorToast("Compatibility computation failed"),
  });

  const routeMutation = useMutation({
    mutationFn: computeRouteCosts,
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["procurement-health"] });
      toast({
        title: "Route costs computed",
        description: `${data?.routes_evaluated ?? 0} routes evaluated` +
          (data?.route_costs_created ? ` -- ${data.route_costs_created} new route(s) priced.` : " -- already up to date."),
      });
    },
    onError: mutationErrorToast("Route cost computation failed"),
  });

  const runMutation = useMutation({
    mutationFn: (body: any) => runProcurementOrchestrator(body),
    onSuccess: (data: any) => {
      setRunUuid(data.run_uuid);
      setSelectedRun(data.run_uuid);
      queryClient.invalidateQueries({ queryKey: ["procurement-runs"] });
      queryClient.invalidateQueries({ queryKey: ["procurement-health"] });
      setActiveTab("executive");
      toast({ title: "Procurement run complete", description: "Executive recommendations are ready." });
    },
    onError: mutationErrorToast("Procurement run failed"),
  });

  const ackMutation = useMutation({
    mutationFn: (cardUuid: string) => acknowledgeExecutiveCard(cardUuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["procurement-exec-cards"] });
      if (selectedRun) {
        queryClient.invalidateQueries({ queryKey: ["procurement-run", selectedRun] });
      }
      toast({ title: "Recommendation acknowledged" });
    },
    onError: mutationErrorToast("Failed to acknowledge recommendation"),
  });

  const handleRun = () => {
    runMutation.mutate({
      simulation_run_uuid: simRunUuid || undefined,
      supply_gap_bpd: parseInt(supplyGap) || 500000,
      optimization_goal: optGoal,
      max_cost_bbl: parseFloat(maxCost) || 100,
      max_risk_score: parseFloat(maxRisk) || 0.8,
      max_lead_days: parseInt(maxLead) || 60,
      name: `Procurement Run - ${new Date().toLocaleString()}`,
    });
  };

  const health = healthQuery.data;
  const suppliers = suppliersQuery.data?.items || [];
  const runs = runsQuery.data?.items || [];
  const runDetail = runDetailQuery.data;
  const recommendations = recommendationsQuery.data?.items || [];
  const execCards = execCardsQuery.data?.items || [];

  const renderSkeleton = () => (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );

  return (
    <AppShell title="Procurement Orchestrator" subtitle="Adaptive supply procurement optimization">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)}>
        <TabsList className="mb-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="suppliers">Supplier Intelligence</TabsTrigger>
          <TabsTrigger value="compatibility">Compatibility</TabsTrigger>
          <TabsTrigger value="optimize">Optimization</TabsTrigger>
          <TabsTrigger value="executive">Executive Cards</TabsTrigger>
        </TabsList>

        {/* ═══ OVERVIEW ═══ */}
        <TabsContent value="overview">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Procurement Runs</CardTitle>
                <ShoppingCart className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.procurement_runs ?? "-"}</div>
                <p className="text-xs text-muted-foreground">
                  Latest: {health?.latest_run || "none"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Recommendations</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.recommendations ?? "-"}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Executive Cards</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.executive_cards ?? "-"}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Suppliers with Intel</CardTitle>
                <Globe className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.suppliers_with_intel ?? "-"}/{suppliers.length}</div>
                <p className="text-xs text-muted-foreground">
                  {health?.refinery_crude_pairs ?? 0} compatibility pairs
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-4 w-4" /> Supplier Intelligence
                </CardTitle>
                <CardDescription>Enrich supplier profiles with procurement attributes</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={() => enrichMutation.mutate()}
                  disabled={enrichMutation.isPending}
                  className="w-full"
                >
                  {enrichMutation.isPending ? "Enriching..." : "Enrich All Suppliers"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-4 w-4" /> Refinery Compatibility
                </CardTitle>
                <CardDescription>Compute crude-refinery compatibility matrix</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={() => compatMutation.mutate()}
                  disabled={compatMutation.isPending}
                  className="w-full"
                >
                  {compatMutation.isPending ? "Computing..." : "Compute Compatibility"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Truck className="h-4 w-4" /> Route Costs
                </CardTitle>
                <CardDescription>Calculate transport costs from network graph</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={() => routeMutation.mutate()}
                  disabled={routeMutation.isPending}
                  className="w-full"
                >
                  {routeMutation.isPending ? "Computing..." : "Compute Route Costs"}
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Recent Procurement Runs</CardTitle>
              </CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No procurement runs yet. Run an optimization to get started.</p>
                ) : (
                  <div className="space-y-2">
                    {runs.slice(0, 5).map((run: any) => (
                      <div
                        key={run.uuid}
                        className="flex items-center justify-between rounded-lg border p-3 cursor-pointer hover:bg-accent"
                        onClick={() => { setSelectedRun(run.uuid); setActiveTab("executive"); }}
                      >
                        <div>
                          <p className="font-medium">{run.name}</p>
                          <p className="text-xs text-muted-foreground">
                            Gap: {(run.total_supply_gap_bpd || 0).toLocaleString()} bpd | Cost: ${(run.total_cost_estimate_usd || 0).toLocaleString()} | Risk: {(run.total_risk_score || 0).toFixed(2)}
                          </p>
                        </div>
                        <Badge variant={run.status === "completed" ? "default" : "secondary"}>{run.status}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ═══ SUPPLIERS ═══ */}
        <TabsContent value="suppliers">
          <div className="mb-4">
            <Button onClick={() => enrichMutation.mutate()} disabled={enrichMutation.isPending}>
              {enrichMutation.isPending ? "Enriching..." : "Enrich All Suppliers"}
            </Button>
          </div>

          {suppliersQuery.isLoading ? (
            renderSkeleton()
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {suppliers.map((s: any) => (
                <Card key={s.uuid}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span className="text-sm">{s.name}</span>
                      <Badge variant={s.sanctions_exposure ? "destructive" : "secondary"}>
                        {s.sanctions_exposure ? "SANCTIONS" : s.supplier_type}
                      </Badge>
                    </CardTitle>
                    <CardDescription>{s.country} | {s.market_share_pct?.toFixed(1)}% share</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Reliability</span>
                        <span>{(s.reliability_score * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Composite Score</span>
                        <span className="font-medium">{(s.composite_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Criticality</span>
                        <Badge variant={s.criticality === "critical" ? "destructive" : "outline"} className="text-xs">
                          {s.criticality}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ═══ COMPATIBILITY ═══ */}
        <TabsContent value="compatibility">
          <div className="mb-4">
            <Button onClick={() => compatMutation.mutate()} disabled={compatMutation.isPending}>
              {compatMutation.isPending ? "Computing..." : "Compute All Compatibility"}
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Refinery-Crude Compatibility</CardTitle>
              <CardDescription>
                {health?.refinery_crude_pairs
                  ? `${health.refinery_crude_pairs} compatibility pairs evaluated`
                  : "Run compatibility computation first"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Compatibility is determined by NCI (Nelson Complexity Index), crude types accepted,
                API gravity, and sulfur content. Use the API for detailed compatibility queries.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ OPTIMIZE ═══ */}
        <TabsContent value="optimize">
          <Card>
            <CardHeader>
              <CardTitle>Procurement Optimization Run</CardTitle>
              <CardDescription>Configure and execute a multi-objective procurement optimization</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Digital Twin Simulation Run UUID (optional)</Label>
                  <Input
                    placeholder="Leave empty for standalone run"
                    value={simRunUuid}
                    onChange={(e) => setSimRunUuid(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Supply Gap (bpd)</Label>
                  <Input
                    type="number"
                    value={supplyGap}
                    onChange={(e) => setSupplyGap(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Optimization Goal</Label>
                  <Select value={optGoal} onValueChange={setOptGoal}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="balanced">Balanced</SelectItem>
                      <SelectItem value="cost">Minimize Cost</SelectItem>
                      <SelectItem value="risk">Minimize Risk</SelectItem>
                      <SelectItem value="speed">Minimize Lead Time</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Max Cost ($/bbl)</Label>
                  <Input type="number" value={maxCost} onChange={(e) => setMaxCost(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Max Risk Score</Label>
                  <Input type="number" step="0.1" value={maxRisk} onChange={(e) => setMaxRisk(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Max Lead Time (days)</Label>
                  <Input type="number" value={maxLead} onChange={(e) => setMaxLead(e.target.value)} />
                </div>
              </div>

              <Button
                onClick={handleRun}
                disabled={runMutation.isPending}
                className="w-full"
              >
                {runMutation.isPending ? (
                  <>Running Optimization...</>
                ) : (
                  <><Play className="mr-2 h-4 w-4" /> Run Procurement Optimization</>
                )}
              </Button>

              {runUuid && (
                <Alert>
                  <CheckCircle className="h-4 w-4" />
                  <AlertTitle>Optimization Complete</AlertTitle>
                  <AlertDescription>
                    Run UUID: {runUuid}. View results under Executive Cards.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ EXECUTIVE CARDS ═══ */}
        <TabsContent value="executive">
          <div className="space-y-6">
            {selectedRun && runDetail && (
              <Card>
                <CardHeader>
                  <CardTitle>{runDetail.run?.name}</CardTitle>
                  <CardDescription>
                    Supply Gap: {(runDetail.run?.total_supply_gap_bpd || 0).toLocaleString()} bpd |
                    Cost: ${(runDetail.run?.total_cost_estimate_usd || 0).toLocaleString()} |
                    Risk: {(runDetail.run?.total_risk_score || 0).toFixed(2)} |
                    Exec Time: {runDetail.run?.execution_time_ms?.toFixed(0)}ms
                  </CardDescription>
                </CardHeader>
              </Card>
            )}

            {selectedRun && runDetail?.recommendations && runDetail.recommendations.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ShoppingCart className="h-4 w-4" /> Procurement Recommendations
                  </CardTitle>
                  <CardDescription>{runDetail.recommendations.length} recommendations</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {runDetail.recommendations.map((rec: any) => (
                      <div key={rec.uuid} className="rounded-lg border p-4">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium">{rec.title}</h4>
                          <div className="flex gap-2">
                            <Badge variant={
                              rec.priority === "critical" ? "destructive" :
                              rec.priority === "high" ? "default" :
                              rec.priority === "medium" ? "secondary" : "outline"
                            }>{rec.priority}</Badge>
                            <Badge variant="outline">{rec.urgency}</Badge>
                          </div>
                        </div>
                        <p className="text-sm text-muted-foreground">{rec.description}</p>
                        <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
                          <span>Volume: {(rec.volume_bpd || 0).toLocaleString()} bpd</span>
                          <span>Cost: ${(rec.unit_cost_usd || 0).toFixed(2)}/bbl</span>
                          <span>Risk: {(rec.risk_score || 0).toFixed(2)}</span>
                          <span>Confidence: {((rec.confidence || 0) * 100).toFixed(0)}%</span>
                        </div>
                        {rec.expected_impact && (
                          <p className="mt-1 text-xs text-muted-foreground italic">
                            Impact: {rec.expected_impact}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {(selectedRun ? runDetail?.executive_cards : execCards).length > 0 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" /> Executive Recommendation Cards
                </h3>
                {(selectedRun ? runDetail.executive_cards : execCards).map((card: any) => (
                  <Card
                    key={card.uuid}
                    className={
                      card.severity === "critical" ? "border-destructive/50" :
                      card.severity === "warning" ? "border-warning/50" : ""
                    }
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                          {card.severity === "critical" ? (
                            <AlertTriangle className="h-5 w-5 text-destructive" />
                          ) : card.severity === "warning" ? (
                            <AlertTriangle className="h-5 w-5 text-warning" />
                          ) : (
                            <BarChart3 className="h-5 w-5 text-primary" />
                          )}
                          {card.title}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant={
                            card.severity === "critical" ? "destructive" :
                            card.severity === "warning" ? "secondary" : "outline"
                          }>{card.severity}</Badge>
                          <Badge variant="outline">{card.category}</Badge>
                          {!card.is_acknowledged && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => ackMutation.mutate(card.uuid)}
                            >
                              <CheckCircle className="mr-1 h-3 w-3" /> Acknowledge
                            </Button>
                          )}
                          {card.is_acknowledged && (
                            <Badge variant="default" className="bg-success text-success-foreground">
                              <CheckCircle className="mr-1 h-3 w-3" /> Acknowledged
                            </Badge>
                          )}
                        </div>
                      </div>
                      <CardDescription>
                        Strategic Importance: {(card.strategic_importance * 100).toFixed(0)}% |
                        Confidence: {(card.confidence * 100).toFixed(0)}% |
                        Horizon: {card.time_horizon}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm">{card.summary}</p>

                      {card.financial_impact && typeof card.financial_impact === "object" && (
                        <div className="rounded-lg bg-muted p-3">
                          <p className="text-xs font-medium mb-1 flex items-center gap-1">
                            <DollarSign className="h-3 w-3" /> Financial Impact
                          </p>
                          <div className="text-xs text-muted-foreground space-y-1">
                            {Object.entries(card.financial_impact).map(([key, val]) => (
                              <div key={key} className="flex justify-between">
                                <span>{key.replace(/_/g, " ")}</span>
                                <span>{typeof val === "number" ? (
                                  key.includes("cost") ? `$${(val as number).toLocaleString()}` : (val as number).toFixed(2)
                                ) : String(val)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {card.operational_impact && typeof card.operational_impact === "object" && (
                        <div className="rounded-lg bg-muted p-3">
                          <p className="text-xs font-medium mb-1 flex items-center gap-1">
                            <Zap className="h-3 w-3" /> Operational Impact
                          </p>
                          <div className="text-xs text-muted-foreground space-y-1">
                            {Object.entries(card.operational_impact).map(([key, val]) => (
                              <div key={key} className="flex justify-between">
                                <span>{key.replace(/_/g, " ")}</span>
                                <span>{typeof val === "number" ? (
                                  key.includes("bpd") ? `${(val as number).toLocaleString()} bpd` :
                                  key.includes("pct") ? `${(val as number).toFixed(1)}%` :
                                  (val as number).toFixed(2)
                                ) : String(val)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {card.recommended_actions && Array.isArray(card.recommended_actions) && (
                        <div>
                          <p className="text-xs font-medium mb-1">Recommended Actions:</p>
                          <ul className="list-disc pl-4 text-sm text-muted-foreground space-y-1">
                            {card.recommended_actions.map((action: string, i: number) => (
                              <li key={i}>{action}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {!selectedRun && execCards.length === 0 && (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  <BarChart3 className="mx-auto h-12 w-12 mb-4 opacity-50" />
                  <p>No executive cards yet. Run a procurement optimization first.</p>
                </CardContent>
              </Card>
            )}

            {selectedRun && !runDetail && (
              <div className="text-center text-muted-foreground py-8">
                Loading run details...
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}

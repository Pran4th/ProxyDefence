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
  Droplets,
  BarChart3,
  DollarSign,
  RefreshCw,
  Clock,
  Shield,
  TrendingUp,
  CheckCircle,
  Play,
  Gauge,
  Warehouse,
  Route,
  ShoppingCart,
} from "lucide-react";

import {
  fetchSPRHealth,
  fetchSPRFacilities,
  fetchSPRInventory,
  fetchSPRPolicies,
  fetchSPRRuns,
  fetchSPRRun,
  runSPRAnalysis,
  computeSPRDemand,
  acknowledgeSPRCard,
  initSPR,
  type SimulationRun,
} from "@/lib/api";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/use-toast";

type TabValue = "overview" | "facilities" | "release" | "timeline" | "decisions";

export default function SPR() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabValue>("overview");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  // Release planner form
  const [disruptionReason, setDisruptionReason] = useState("supply_disruption");
  const [disruptionDays, setDisruptionDays] = useState("90");
  const [supplyGap, setSupplyGap] = useState("");
  const [strategy, setStrategy] = useState("balanced");
  const [policyName, setPolicyName] = useState("default");
  const [simRunUuid, setSimRunUuid] = useState("");

  const healthQuery = useQuery({
    queryKey: ["spr-health"],
    queryFn: fetchSPRHealth,
    refetchInterval: 30000,
  });

  const facilitiesQuery = useQuery({
    queryKey: ["spr-facilities"],
    queryFn: fetchSPRFacilities,
  });

  const policiesQuery = useQuery({
    queryKey: ["spr-policies"],
    queryFn: fetchSPRPolicies,
  });

  const runsQuery = useQuery({
    queryKey: ["spr-runs"],
    queryFn: () => fetchSPRRuns(),
  });

  const runDetailQuery = useQuery({
    queryKey: ["spr-run", selectedRun],
    queryFn: () => fetchSPRRun(selectedRun!),
    enabled: !!selectedRun,
  });

  const runAnalysisMutation = useMutation({
    mutationFn: (body: any) => runSPRAnalysis(body),
    onSuccess: (data: any) => {
      setSelectedRun(data.run_uuid);
      queryClient.invalidateQueries({ queryKey: ["spr-runs"] });
      queryClient.invalidateQueries({ queryKey: ["spr-health"] });
      setActiveTab("timeline");
      toast({ title: "SPR analysis complete", description: "Release plan and recommendations are ready." });
    },
    onError: (err: any) => {
      if (err?.response?.status === 402) {
        toast({
          title: "Premium feature",
          description: "SPR release-plan analysis requires a Premium account. Upgrade from your Profile page to run it.",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "SPR analysis failed",
        description: err?.response?.data?.detail ?? "Could not reach the energy service. Check that it's running.",
        variant: "destructive",
      });
    },
  });

  const ackMutation = useMutation({
    mutationFn: (cardUuid: string) => acknowledgeSPRCard(cardUuid),
    onSuccess: () => {
      if (selectedRun) {
        queryClient.invalidateQueries({ queryKey: ["spr-run", selectedRun] });
      }
      toast({ title: "Recommendation acknowledged" });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to acknowledge recommendation",
        description: err?.response?.data?.detail ?? "Please try again.",
        variant: "destructive",
      });
    },
  });

  const initMutation = useMutation({
    mutationFn: initSPR,
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["spr-facilities"] });
      queryClient.invalidateQueries({ queryKey: ["spr-health"] });
      toast({
        title: "SPR facilities synchronized",
        description: data?.facilities_initialized
          ? `${data.facilities_initialized} new facility record(s) created (${data.total_facilities} total).`
          : `Already up to date -- ${data?.total_facilities ?? 0} facilities on file.`,
      });
    },
    onError: (err: any) => {
      toast({
        title: "SPR initialization failed",
        description: err?.response?.data?.detail ?? "Could not reach the energy service. Check that it's running.",
        variant: "destructive",
      });
    },
  });

  const demandQuery = useQuery({
    queryKey: ["spr-demand"],
    queryFn: computeSPRDemand,
    enabled: activeTab === "release",
  });

  const handleRun = () => {
    runAnalysisMutation.mutate({
      name: `SPR Release Plan - ${new Date().toLocaleString()}`,
      description: `${disruptionReason} for ${disruptionDays} days`,
      simulation_run_uuid: simRunUuid || undefined,
      disruption_reason: disruptionReason,
      disruption_days: parseInt(disruptionDays) || 90,
      supply_gap_bpd: supplyGap ? parseInt(supplyGap) : undefined,
      strategy,
      policy_name: policyName,
    });
  };

  const health = healthQuery.data;
  const facilities = facilitiesQuery.data?.items || [];
  const activeFacilityCount = facilities.filter((f: any) => f.operational_status === "active").length;
  const policies = policiesQuery.data?.items || [];
  const runs = runsQuery.data?.items || [];
  const runDetail = runDetailQuery.data;
  const demand = demandQuery.data;

  const renderSkeleton = () => (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );

  return (
    <AppShell title="SPR Decision Intelligence" subtitle="Strategic Petroleum Reserve — Release, Refill & Policy Optimization">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)}>
        <TabsList className="mb-6">
          <TabsTrigger value="overview">Reserve Dashboard</TabsTrigger>
          <TabsTrigger value="facilities">Facility Status</TabsTrigger>
          <TabsTrigger value="release">Release Planner</TabsTrigger>
          <TabsTrigger value="timeline">Executive Timeline</TabsTrigger>
          <TabsTrigger value="decisions">Decision Cards</TabsTrigger>
        </TabsList>

        {/* ═══ OVERVIEW ═══ */}
        <TabsContent value="overview">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Facilities</CardTitle>
                <Warehouse className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.spr_facilities ?? "-"}</div>
                <p className="text-xs text-muted-foreground">
                  Active: {activeFacilityCount}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Total Capacity</CardTitle>
                <Gauge className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.total_capacity_barrels ? `${(health.total_capacity_barrels / 1e6).toFixed(1)}M` : "-"}</div>
                <p className="text-xs text-muted-foreground">barrels</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Current Inventory</CardTitle>
                <Droplets className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.total_inventory_barrels ? `${(health.total_inventory_barrels / 1e6).toFixed(1)}M` : "-"}</div>
                <p className="text-xs text-muted-foreground">
                  {health?.overall_fill_pct !== undefined ? `${health.overall_fill_pct.toFixed(1)}% utilized` : ""}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Release Runs</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{health?.optimization_runs ?? "-"}</div>
                <p className="text-xs text-muted-foreground">
                  Latest: {health?.latest_run || "none"}
                </p>
              </CardContent>
            </Card>
          </div>

          {initMutation.isPending && (
            <Card className="mt-4">
              <CardContent className="py-4">
                <p className="text-sm text-muted-foreground">Initializing SPR facilities...</p>
              </CardContent>
            </Card>
          )}

          {policies.length > 0 && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Shield className="h-4 w-4" /> Active Policies
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-3">
                  {policies.map((p: any) => (
                    <Card key={p.uuid} className={p.name === "default" ? "border-primary/50" : ""}>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm capitalize">{p.name}</CardTitle>
                        <CardDescription>
                          Reserve: {(p.min_reserve_threshold_pct || 0).toFixed(0)}% | Daily: {(p.max_daily_release_bpd || 0).toLocaleString()} bpd
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="text-xs text-muted-foreground space-y-1">
                          <div className="flex justify-between">
                            <span>Emergency only</span>
                            <span>{p.emergency_only ? "Yes" : "No"}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Strategic preservation</span>
                            <span>{p.strategic_preservation ? "Yes" : "No"}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Refill trigger</span>
                            <span>{p.refill_trigger_pct ?? "-"}%</span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <RefreshCw className="h-4 w-4" /> Initialize
              </CardTitle>
              <CardDescription>Synchronize SPR facilities from strategic petroleum reserves data</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => initMutation.mutate()} disabled={initMutation.isPending}>
                {initMutation.isPending ? "Initializing..." : "Initialize SPR"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ FACILITIES ═══ */}
        <TabsContent value="facilities">
          {facilitiesQuery.isLoading ? renderSkeleton() : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">{facilities.length} Facilities</h3>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {facilities.map((f: any) => (
                  <Card key={f.uuid} className={
                    f.operational_status === "active" ? "" :
                    f.operational_status === "maintenance" ? "border-yellow-500/50" :
                    "border-destructive/50"
                  }>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm">{f.name}</CardTitle>
                        <Badge variant={
                          f.operational_status === "active" ? "default" :
                          f.operational_status === "maintenance" ? "secondary" : "destructive"
                        }>{f.operational_status}</Badge>
                      </div>
                      <CardDescription>{f.location || f.country}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-muted-foreground">Capacity</span>
                          <p className="font-medium">{(f.storage_capacity_barrels || 0).toLocaleString()} bbl</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Inventory</span>
                          <p className="font-medium">{(f.current_inventory_barrels || 0).toLocaleString()} bbl</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Drawdown Rate</span>
                          <p className="font-medium">{(f.max_drawdown_rate_bpd || 0).toLocaleString()} bpd</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Utilization</span>
                          <p className="font-medium">{f.fill_pct !== undefined ? `${f.fill_pct.toFixed(1)}%` : "-"}</p>
                        </div>
                      </div>
                      {f.criticality && (
                        <Badge variant="outline" className="mt-2 text-xs">{f.criticality}</Badge>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </TabsContent>

        {/* ═══ RELEASE PLANNER ═══ */}
        <TabsContent value="release">
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Play className="h-4 w-4" /> Run SPR Analysis
                </CardTitle>
                <CardDescription>Configure release strategy and execute</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Disruption Reason</Label>
                  <Select value={disruptionReason} onValueChange={setDisruptionReason}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="supply_disruption">Supply Disruption</SelectItem>
                      <SelectItem value="geopolitical_crisis">Geopolitical Crisis</SelectItem>
                      <SelectItem value="natural_disaster">Natural Disaster</SelectItem>
                      <SelectItem value="infrastructure_failure">Infrastructure Failure</SelectItem>
                      <SelectItem value="price_spike">Price Spike</SelectItem>
                      <SelectItem value="war_conflict">War / Conflict</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Duration (days)</Label>
                  <Input type="number" value={disruptionDays} onChange={(e) => setDisruptionDays(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Supply Gap (bpd, optional)</Label>
                  <Input type="number" value={supplyGap} onChange={(e) => setSupplyGap(e.target.value)} placeholder="Auto from demand model" />
                </div>
                <div className="space-y-2">
                  <Label>Strategy</Label>
                  <Select value={strategy} onValueChange={setStrategy}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="balanced">Balanced</SelectItem>
                      <SelectItem value="conservative">Conservative</SelectItem>
                      <SelectItem value="aggressive">Aggressive</SelectItem>
                      <SelectItem value="economic">Economic Protection</SelectItem>
                      <SelectItem value="strategic_preservation">Strategic Preservation</SelectItem>
                      <SelectItem value="critical_infrastructure_first">Critical Infrastructure First</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Policy</Label>
                  <Select value={policyName} onValueChange={setPolicyName}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {policies.map((p: any) => (
                        <SelectItem key={p.uuid} value={p.name}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Simulation Run UUID (optional)</Label>
                  <Input type="text" value={simRunUuid} onChange={(e) => setSimRunUuid(e.target.value)} placeholder="Link to Digital Twin run" />
                </div>
                <Button className="w-full" onClick={handleRun} disabled={runAnalysisMutation.isPending}>
                  {runAnalysisMutation.isPending ? "Running Analysis..." : "Run SPR Analysis"}
                </Button>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" /> Demand Overview
                </CardTitle>
                <CardDescription>National demand from Digital Twin profiles</CardDescription>
              </CardHeader>
              <CardContent>
                {demand ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-lg bg-muted p-3 text-center">
                        <p className="text-xs text-muted-foreground">National Demand</p>
                        <p className="text-xl font-bold">{(demand.total_national_demand_bpd || 0).toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">bpd</p>
                      </div>
                      <div className="rounded-lg bg-muted p-3 text-center">
                        <p className="text-xs text-muted-foreground">Strategic Reserve</p>
                        <p className="text-xl font-bold">{(demand.total_spr_inventory || 0).toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">barrels</p>
                      </div>
                      <div className="rounded-lg bg-muted p-3 text-center">
                        <p className="text-xs text-muted-foreground">Coverage Days</p>
                        <p className="text-xl font-bold">{demand.days_of_supply_remaining?.toFixed(0) ?? "-"}</p>
                        <p className="text-xs text-muted-foreground">days at current rate</p>
                      </div>
                    </div>
                    {demand.regional_demands && demand.regional_demands.length > 0 && (
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={demand.regional_demands}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="region" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="daily_demand_bpd" fill="hsl(var(--primary))" name="Demand (bpd)" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-8">
                    <TrendingUp className="mx-auto h-12 w-12 mb-4 opacity-50" />
                    <p>Configure and run demand analysis</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {runAnalysisMutation.data && (
            <Card className="mt-4 border-green-500/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-green-500">
                  <CheckCircle className="h-4 w-4" /> Analysis Complete
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">
                  Run UUID: <code className="rounded bg-muted px-1">{runAnalysisMutation.data.run_uuid}</code>
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  View results in the Executive Timeline tab.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ═══ EXECUTIVE TIMELINE ═══ */}
        <TabsContent value="timeline">
          <div className="grid gap-6 lg:grid-cols-4">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4" /> Runs
                </CardTitle>
                <CardDescription>Select an analysis run</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {runs.map((r: any) => (
                  <Card
                    key={r.uuid}
                    className={`cursor-pointer transition-colors hover:bg-muted ${selectedRun === r.uuid ? "border-primary" : ""}`}
                    onClick={() => setSelectedRun(r.uuid)}
                  >
                    <CardHeader className="p-3">
                      <CardTitle className="text-xs">{r.name}</CardTitle>
                      <CardDescription className="text-[10px]">
                        {r.disruption_reason} | {r.duration_days || r.disruption_days}d
                      </CardDescription>
                    </CardHeader>
                  </Card>
                ))}
                {runs.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">No runs yet</p>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Route className="h-4 w-4" /> Decision Timeline
                </CardTitle>
                <CardDescription>Immediate → Short-term → Medium-term → Long-term</CardDescription>
              </CardHeader>
              <CardContent>
                {selectedRun && runDetail?.timeline_entries && runDetail.timeline_entries.length > 0 ? (
                  <div className="space-y-6">
                    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {[...runDetail.timeline_entries]
                        .sort((a: any, b: any) => (a.sequence_order ?? 0) - (b.sequence_order ?? 0))
                        .map((entry: any) => (
                          <Card key={entry.uuid} className={
                            entry.phase === "immediate" ? "border-destructive/50" :
                            entry.phase === "short_term" ? "border-warning/50" :
                            entry.phase === "medium_term" ? "border-primary/50" :
                            "border-success/50"
                          }>
                            <CardHeader className="p-2 pb-0">
                              <CardTitle className="text-[10px] uppercase tracking-wider">
                                {entry.timing_label || entry.phase}
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-1 p-2 text-[10px]">
                              <p className="font-medium">{entry.action}</p>
                              {entry.details && <p className="text-muted-foreground">{entry.details}</p>}
                              {entry.facility && (
                                <p className="text-muted-foreground">Facility: {entry.facility}</p>
                              )}
                              {entry.volume_barrels > 0 && (
                                <p className="text-muted-foreground">
                                  Volume: {entry.volume_barrels.toLocaleString()} bbl
                                </p>
                              )}
                              <p className="text-muted-foreground">{entry.expected_impact}</p>
                              <p className="text-muted-foreground">
                                Confidence: {entry.confidence !== undefined ? `${(entry.confidence * 100).toFixed(0)}%` : "-"}
                              </p>
                            </CardContent>
                          </Card>
                        ))}
                    </div>

                    {runDetail.release_plans && runDetail.release_plans.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium mb-2">Release Plan by Facility</h4>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={runDetail.release_plans.map((p: any) => ({
                              facility: p.reason?.replace("Strategic release from ", "") || p.facility_uuid,
                              volume: p.release_volume_barrels,
                              cost: p.total_cost_usd,
                            }))}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="facility" tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 11 }} />
                              <Tooltip />
                              <Bar dataKey="volume" fill="hsl(var(--primary))" name="Release Volume (bbl)" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-8">
                    <Route className="mx-auto h-12 w-12 mb-4 opacity-50" />
                    <p>Select a run to view the decision timeline</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ═══ DECISION CARDS ═══ */}
        <TabsContent value="decisions">
          <div className="grid gap-6 lg:grid-cols-4">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4" /> Runs
                </CardTitle>
                <CardDescription>Select a run to view cards</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {runs.map((r: any) => (
                  <Card
                    key={r.uuid}
                    className={`cursor-pointer transition-colors hover:bg-muted ${selectedRun === r.uuid ? "border-primary" : ""}`}
                    onClick={() => setSelectedRun(r.uuid)}
                  >
                    <CardHeader className="p-3">
                      <CardTitle className="text-xs">{r.name}</CardTitle>
                      <CardDescription className="text-[10px]">
                        {r.strategy} | {(r.supply_gap_bpd || 0).toLocaleString()} bpd
                      </CardDescription>
                    </CardHeader>
                  </Card>
                ))}
                {runs.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">No runs yet</p>
                )}
              </CardContent>
            </Card>

            <div className="lg:col-span-3 space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <BarChart3 className="h-4 w-4" /> SPR Recommendations
              </h3>

              {selectedRun && runDetail?.recommendations_list && runDetail.recommendations_list.length > 0 ? (
                runDetail.recommendations_list.map((rec: any) => (
                  <Card key={rec.uuid} className={
                    rec.severity === "critical" ? "border-destructive/50" :
                    rec.severity === "warning" ? "border-warning/50" : ""
                  }>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                          {rec.recommendation_type === "release" ? (
                            <Droplets className="h-5 w-5 text-primary" />
                          ) : rec.recommendation_type === "procurement" ? (
                            <ShoppingCart className="h-5 w-5 text-warning" />
                          ) : rec.recommendation_type === "refill" ? (
                            <RefreshCw className="h-5 w-5 text-success" />
                          ) : (
                            <Shield className="h-5 w-5 text-primary" />
                          )}
                          {rec.title}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant={
                            rec.severity === "critical" ? "destructive" :
                            rec.severity === "warning" ? "secondary" : "outline"
                          }>{rec.severity}</Badge>
                          <Badge variant="outline">{rec.recommendation_type}</Badge>
                          {!rec.is_acknowledged && (
                            <Button size="sm" variant="outline" onClick={() => ackMutation.mutate(rec.uuid)}>
                              <CheckCircle className="mr-1 h-3 w-3" /> Acknowledge
                            </Button>
                          )}
                          {rec.is_acknowledged && (
                            <Badge variant="default" className="bg-success text-success-foreground">
                              <CheckCircle className="mr-1 h-3 w-3" /> Acknowledged
                            </Badge>
                          )}
                        </div>
                      </div>
                      <CardDescription>
                        Confidence: {rec.confidence !== undefined ? `${(rec.confidence * 100).toFixed(0)}%` : "-"}
                        {rec.expected_supply_extension_days ? ` | Extends supply by ${rec.expected_supply_extension_days} days` : ""}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm">{rec.summary}</p>

                      <div className="rounded-lg bg-muted p-3">
                        <p className="mb-1 flex items-center gap-1 text-xs font-medium">
                          <DollarSign className="h-3 w-3" /> Impact
                        </p>
                        <div className="space-y-1 text-xs text-muted-foreground">
                          {rec.release_volume_barrels > 0 && (
                            <div className="flex justify-between">
                              <span>Volume</span>
                              <span>{rec.release_volume_barrels.toLocaleString()} bbl</span>
                            </div>
                          )}
                          {rec.primary_facility && (
                            <div className="flex justify-between">
                              <span>Primary facility</span>
                              <span>{rec.primary_facility}</span>
                            </div>
                          )}
                          {rec.economic_savings_usd > 0 && (
                            <div className="flex justify-between">
                              <span>Economic savings</span>
                              <span>${rec.economic_savings_usd.toLocaleString()}</span>
                            </div>
                          )}
                          {rec.alternative_cost_delta > 0 && (
                            <div className="flex justify-between">
                              <span>Alternative cost delta</span>
                              <span>${rec.alternative_cost_delta.toLocaleString()}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {rec.reason && <p className="text-xs text-muted-foreground">{rec.reason}</p>}

                      {rec.alternative_strategy && (
                        <div>
                          <p className="mb-1 text-xs font-medium">Alternative Strategy:</p>
                          <p className="text-sm text-muted-foreground">{rec.alternative_strategy}</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    <BarChart3 className="mx-auto h-12 w-12 mb-4 opacity-50" />
                    <p>No decision cards yet. Run an SPR analysis first.</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}

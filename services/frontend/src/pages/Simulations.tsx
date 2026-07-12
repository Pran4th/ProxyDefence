import { useState, useCallback } from "react";
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
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
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
  Activity,
  AlertTriangle,
  BarChart3,
  DollarSign,
  Droplets,
  Globe,
  Network,
  Play,
  RefreshCw,
  Shield,
  Zap,
} from "lucide-react";

import {
  fetchDigitalTwinHealth,
  fetchScenarios,
  fetchSimulationRuns,
  fetchRunTimeline,
  fetchRunImpacts,
  fetchNetworkGraph,
  fetchFlows,
  fetchRecommendations,
  fetchDemandProfiles,
  runSimulation,
  createScenario,
  deleteSimulationRun,
  fetchAssets,
  type SimulationRun,
  type SimulationScenario,
} from "@/lib/api";
import AppShell from "@/components/AppShell";
import { useToast } from "@/hooks/use-toast";

type TabValue = "overview" | "scenarios" | "results" | "network" | "impacts";

export default function Simulations() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<TabValue>("overview");
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [simDuration, setSimDuration] = useState([30]);
  const [simName, setSimName] = useState("Simulation Run");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const healthQuery = useQuery({
    queryKey: ["dt-health"],
    queryFn: fetchDigitalTwinHealth,
    refetchInterval: 30000,
  });

  const scenariosQuery = useQuery({
    queryKey: ["dt-scenarios"],
    queryFn: () => fetchScenarios(),
  });

  const runsQuery = useQuery({
    queryKey: ["dt-runs"],
    queryFn: () => fetchSimulationRuns(),
    refetchInterval: 10000,
  });

  const runTimelineQuery = useQuery({
    queryKey: ["dt-timeline", selectedRun],
    queryFn: () => fetchRunTimeline(selectedRun!),
    enabled: !!selectedRun,
  });

  const runImpactsQuery = useQuery({
    queryKey: ["dt-impacts", selectedRun],
    queryFn: () => fetchRunImpacts(selectedRun!),
    enabled: !!selectedRun,
  });

  const networkQuery = useQuery({
    queryKey: ["dt-network"],
    queryFn: fetchNetworkGraph,
  });

  const flowsQuery = useQuery({
    queryKey: ["dt-flows"],
    queryFn: fetchFlows,
  });

  const assetsQuery = useQuery({
    queryKey: ["dt-assets"],
    queryFn: () => fetchAssets(),
  });

  const recsQuery = useQuery({
    queryKey: ["dt-recs", selectedRun],
    queryFn: () => fetchRecommendations(selectedRun || undefined),
  });

  const runSimMutation = useMutation({
    mutationFn: runSimulation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dt-runs"] });
    },
    onError: (err: any) => {
      toast({
        title: "Simulation run failed",
        description: err?.response?.data?.detail ?? "Could not reach the energy service. Check that it's running.",
        variant: "destructive",
      });
    },
  });

  const deleteRunMutation = useMutation({
    mutationFn: deleteSimulationRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dt-runs"] });
      setSelectedRun(null);
    },
    onError: (err: any) => {
      toast({
        title: "Failed to delete run",
        description: err?.response?.data?.detail ?? "Please try again.",
        variant: "destructive",
      });
    },
  });

  const handleRunSimulation = useCallback(async () => {
    const scenario = scenariosQuery.data?.items?.find(
      (s: SimulationScenario) => s.uuid === selectedScenario
    );
    const result = await runSimMutation.mutateAsync({
      scenario_uuid: selectedScenario || undefined,
      name: simName || scenario?.name || "Simulation Run",
      max_ticks: simDuration[0],
      tick_interval: "day",
      config: scenario?.config || {},
    });
    if (result?.run_uuid) {
      setSelectedRun(result.run_uuid);
      setActiveTab("results");
    }
  }, [selectedScenario, simName, simDuration, scenariosQuery.data, runSimMutation]);

  const health = healthQuery.data;
  const network = networkQuery.data;
  const timeline = runTimelineQuery.data?.timeline || [];
  const impacts = runImpactsQuery.data;
  const scenarios = scenariosQuery.data?.items || [];
  const runs = runsQuery.data?.items || [];
  const flows = flowsQuery.data?.items || [];
  const recs = recsQuery.data?.recommendations || [];

  const formatCurrency = (v: number) =>
    v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${(v / 1e3).toFixed(0)}K`;

  const formatBPD = (v: number) =>
    v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${v.toFixed(0)}`;

  return (
    <AppShell
      title="Scenario Simulations"
      subtitle="Live digital-twin simulation engine for India's energy supply chain — run what-if scenarios and stress-test disruption paths."
    >
      <div className="space-y-6">
        <div className="flex items-center justify-end gap-2">
          <Badge
            variant={health?.status === "ok" ? "default" : "destructive"}
            className="text-xs"
          >
            {health?.status === "ok" ? "Online" : "Offline"}
          </Badge>
          {health && (
            <span className="text-xs text-muted-foreground">
              {health.nodes} nodes / {health.edges} edges
            </span>
          )}
        </div>

        {/* Summary cards */}
        {health && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <Network className="h-4 w-4 text-primary" />
                  <span className="text-xs text-muted-foreground">Network</span>
                </div>
                <p className="text-2xl font-bold mt-1">{health.nodes}</p>
                <p className="text-xs text-muted-foreground">{health.edges} connections</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <Play className="h-4 w-4 text-success" />
                  <span className="text-xs text-muted-foreground">Simulations</span>
                </div>
                <p className="text-2xl font-bold mt-1">{health.simulation_runs}</p>
                <p className="text-xs text-muted-foreground">{health.scenarios} scenarios</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-warning" />
                  <span className="text-xs text-muted-foreground">Scenarios</span>
                </div>
                <p className="text-2xl font-bold mt-1">{health.scenario_templates}</p>
                <p className="text-xs text-muted-foreground">pre-built templates</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-accent" />
                  <span className="text-xs text-muted-foreground">Status</span>
                </div>
                <p className="text-2xl font-bold mt-1 text-green-600">Operational</p>
                <p className="text-xs text-muted-foreground">All systems nominal</p>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabValue)}
          className="space-y-4"
        >
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="scenarios">Scenarios</TabsTrigger>
            <TabsTrigger value="results">Results</TabsTrigger>
            <TabsTrigger value="network">Network</TabsTrigger>
            <TabsTrigger value="impacts">Impact Dashboard</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Play className="h-5 w-5 text-success" />
                  Run Simulation
                </CardTitle>
                <CardDescription>
                  Select a scenario, configure parameters, and run a what-if simulation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Scenario Template</Label>
                  <Select value={selectedScenario} onValueChange={setSelectedScenario}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a scenario..." />
                    </SelectTrigger>
                    <SelectContent>
                      {scenarios
                        .filter((s: SimulationScenario) => s.is_template)
                        .map((s: SimulationScenario) => (
                          <SelectItem key={s.uuid} value={s.uuid}>
                            {s.name} ({s.severity})
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Simulation Duration: {simDuration[0]} days</Label>
                  <Slider
                    value={simDuration}
                    onValueChange={setSimDuration}
                    min={7}
                    max={180}
                    step={1}
                  />
                </div>
                <Button
                  onClick={handleRunSimulation}
                  disabled={runSimMutation.isPending}
                  className="w-full"
                >
                  {runSimMutation.isPending ? (
                    <>Running Simulation...</>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Run Simulation
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Recent Simulation Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No simulation runs yet. Run one above.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {runs.slice(0, 5).map((run: SimulationRun) => (
                      <div
                        key={run.uuid}
                        className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-accent ${
                          selectedRun === run.uuid ? "border-primary" : ""
                        }`}
                        onClick={() => {
                          setSelectedRun(run.uuid);
                          setActiveTab("results");
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <Badge
                            variant={
                              run.status === "completed"
                                ? "default"
                                : run.status === "running"
                                ? "secondary"
                                : "outline"
                            }
                            className="w-20 text-center"
                          >
                            {run.status}
                          </Badge>
                          <div>
                            <p className="text-sm font-medium">{run.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {run.current_tick}/{run.max_ticks} ticks
                            </p>
                          </div>
                        </div>
                        <div className="text-right text-xs text-muted-foreground">
                          {run.execution_time_ms > 0 && (
                            <p>{run.execution_time_ms.toFixed(0)}ms</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-warning" />
                  Recommendations
                </CardTitle>
                {recs.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Preliminary suggestions from simulation results — not a cost-optimized ranking.
                  </p>
                )}
              </CardHeader>
              <CardContent>
                {recs.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Run a simulation to generate recommendations
                  </p>
                ) : (
                  <div className="space-y-2">
                    {recs.map((rec: any, i: number) => (
                      <Alert key={i} variant={rec.priority === "critical" ? "destructive" : "default"}>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle className="text-sm capitalize">{rec.type}</AlertTitle>
                        <AlertDescription className="text-xs">
                          {rec.recommendation}
                        </AlertDescription>
                      </Alert>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Scenarios Tab */}
          <TabsContent value="scenarios" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {scenarios
                .filter((s: SimulationScenario) => s.is_template)
                .map((scenario: SimulationScenario) => (
                  <Card key={scenario.uuid}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={
                            scenario.severity === "critical"
                              ? "destructive"
                              : scenario.severity === "high"
                              ? "default"
                              : "secondary"
                          }
                        >
                          {scenario.severity}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {scenario.category}
                        </Badge>
                      </div>
                      <CardTitle className="text-base mt-2">{scenario.name}</CardTitle>
                      <CardDescription className="text-xs">
                        {scenario.description}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <p>Duration: {scenario.config?.duration_days || "N/A"} days</p>
                        <p>Severity: {(scenario.config?.severity || 0) * 100}%</p>
                        {scenario.config?.affected_routes && (
                          <p>Routes: {scenario.config.affected_routes.join(", ")}</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
            </div>
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results" className="space-y-4">
            {!selectedRun ? (
              <Card>
                <CardContent className="pt-6 text-center text-muted-foreground">
                  <p>Select a simulation run to view results</p>
                </CardContent>
              </Card>
            ) : runSimMutation.isPending ? (
              <Card>
                <CardContent className="pt-6 text-center">
                  <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
                  <p className="text-muted-foreground">Simulation running...</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {impacts && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-4">
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Droplets className="h-3 w-3" /> Supply Gap
                        </p>
                        <p className="text-xl font-bold">
                          {formatBPD(impacts.supply_gap_bpd)} bpd
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <DollarSign className="h-3 w-3" /> Economic Impact
                        </p>
                        <p className="text-xl font-bold">
                          {formatCurrency(impacts.economic_impact_usd)}
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Globe className="h-3 w-3" /> GDP Impact
                        </p>
                        <p className="text-xl font-bold">
                          {impacts.gdp_impact_pct?.toFixed(2)}%
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4">
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Zap className="h-3 w-3" /> Execution
                        </p>
                        <p className="text-xl font-bold">
                          {impacts.execution_time_ms?.toFixed(0)}ms
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Supply Gap Timeline</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {timeline.length === 0 ? (
                      <Skeleton className="h-[300px]" />
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={timeline}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="tick" label={{ value: "Day", position: "bottom" }} />
                          <YAxis label={{ value: "Barrels/Day", angle: -90, position: "left" }} />
                          <Tooltip />
                          <Area
                            type="monotone"
                            dataKey="supply_gap_bpd"
                            stroke="hsl(var(--destructive))"
                            fill="hsl(var(--destructive))"
                            fillOpacity={0.2}
                            name="Supply Gap (bpd)"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Inventory Level Over Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {timeline.length === 0 ? (
                      <Skeleton className="h-[300px]" />
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={timeline}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="tick" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="total_inventory_barrels"
                            stroke="hsl(var(--primary))"
                            name="Inventory (barrels)"
                            strokeWidth={2}
                          />
                          <Line
                            type="monotone"
                            dataKey="total_flow_bpd"
                            stroke="hsl(var(--success))"
                            name="Flow (bpd)"
                            strokeWidth={2}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => deleteRunMutation.mutate(selectedRun)}
                  >
                    Delete Run
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setActiveTab("impacts")}
                  >
                    View Full Impact Analysis
                  </Button>
                </div>
              </>
            )}
          </TabsContent>

          {/* Network Tab */}
          <TabsContent value="network" className="space-y-4">
            {networkQuery.isLoading ? (
              <Skeleton className="h-[400px]" />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="pt-4">
                      <p className="text-xs text-muted-foreground">Total Nodes</p>
                      <p className="text-2xl font-bold">{network?.node_count || 0}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <p className="text-xs text-muted-foreground">Total Edges</p>
                      <p className="text-2xl font-bold">{network?.edge_count || 0}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <p className="text-xs text-muted-foreground">Active Flows</p>
                      <p className="text-2xl font-bold">{flows.length}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <p className="text-xs text-muted-foreground">Flow Utilization</p>
                      <p className="text-2xl font-bold">
                        {flows.length > 0
                          ? `${(flows.reduce((s: number, f: any) => s + (f.utilization_pct || 0), 0) / flows.length).toFixed(0)}%`
                          : "N/A"}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Network Flows</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {flows.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        No flows established yet. Run 'estimate-baseline' to initialize.
                      </p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b">
                              <th className="text-left py-2 px-2">Source</th>
                              <th className="text-left py-2 px-2">Target</th>
                              <th className="text-left py-2 px-2">Type</th>
                              <th className="text-right py-2 px-2">Flow (bpd)</th>
                              <th className="text-right py-2 px-2">Capacity</th>
                              <th className="text-right py-2 px-2">Utilization</th>
                            </tr>
                          </thead>
                          <tbody>
                            {flows.map((f: any) => (
                              <tr key={f.id} className="border-b hover:bg-accent/50">
                                <td className="py-2 px-2">{f.source_name}</td>
                                <td className="py-2 px-2">{f.target_name}</td>
                                <td className="py-2 px-2">
                                  <Badge variant="outline" className="text-xs">
                                    {f.edge_type}
                                  </Badge>
                                </td>
                                <td className="text-right py-2 px-2">
                                  {formatBPD(f.current_flow_bpd || 0)}
                                </td>
                                <td className="text-right py-2 px-2">
                                  {formatBPD(f.max_capacity_bpd || 0)}
                                </td>
                                <td className="text-right py-2 px-2">
                                  <span
                                    className={
                                      (f.utilization_pct || 0) > 80
                                        ? "text-destructive"
                                        : (f.utilization_pct || 0) > 60
                                        ? "text-warning"
                                        : "text-success"
                                    }
                                  >
                                    {(f.utilization_pct || 0).toFixed(0)}%
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Asset Inventory</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {assetsQuery.isLoading ? (
                      <Skeleton className="h-[200px]" />
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b">
                              <th className="text-left py-2 px-2">Name</th>
                              <th className="text-left py-2 px-2">Type</th>
                              <th className="text-left py-2 px-2">Category</th>
                              <th className="text-left py-2 px-2">Country</th>
                              <th className="text-left py-2 px-2">Status</th>
                              <th className="text-right py-2 px-2">Capacity (bpd)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(assetsQuery.data?.items || []).slice(0, 20).map((n: any) => (
                              <tr key={n.id} className="border-b hover:bg-accent/50">
                                <td className="py-2 px-2 font-medium">{n.name}</td>
                                <td className="py-2 px-2">{n.node_type}</td>
                                <td className="py-2 px-2">{n.category}</td>
                                <td className="py-2 px-2">{n.country || "-"}</td>
                                <td className="py-2 px-2">
                                  <Badge
                                    variant={
                                      n.operational_status === "active"
                                        ? "default"
                                        : "secondary"
                                    }
                                    className="text-xs"
                                  >
                                    {n.operational_status}
                                  </Badge>
                                </td>
                                <td className="text-right py-2 px-2">
                                  {n.capacity_bpd ? formatBPD(n.capacity_bpd) : "-"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* Impact Dashboard Tab */}
          <TabsContent value="impacts" className="space-y-4">
            {!impacts ? (
              <Card>
                <CardContent className="pt-6 text-center text-muted-foreground">
                  <p>Select a completed simulation run to view impact analysis</p>
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Supply Chain Impact</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                          <span>Supply Gap</span>
                          <span className="font-bold text-destructive">
                            {formatBPD(impacts.supply_gap_bpd)} bpd
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Maximum Gap</span>
                          <span className="font-bold">
                            {formatBPD(impacts.max_supply_gap_bpd)} bpd
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Idle Refineries</span>
                          <span className="font-bold">{impacts.idle_refineries || 0}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Refinery Capacity Lost</span>
                          <span className="font-bold text-destructive">
                            {formatBPD(impacts.total_refinery_capacity_lost_bpd || 0)} bpd
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Economic Impact</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                          <span>Total Economic Loss</span>
                          <span className="font-bold text-destructive">
                            {formatCurrency(impacts.economic_impact_usd)}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>GDP Impact</span>
                          <span className="font-bold text-destructive">
                            {impacts.gdp_impact_pct?.toFixed(3)}%
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Crude Price Assumption</span>
                          <span className="font-bold">${impacts.crude_price_assumption_bpd || 85}/bbl</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Days Affected</span>
                          <span className="font-bold">{impacts.total_days_affected || 0}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Impact Over Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {timeline.length === 0 ? (
                      <Skeleton className="h-[300px]" />
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={timeline}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="tick" label={{ value: "Day", position: "bottom" }} />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar
                            dataKey="supply_gap_bpd"
                            fill="hsl(var(--destructive))"
                            name="Supply Gap (bpd)"
                            opacity={0.8}
                          />
                          <Bar
                            dataKey="idle_nodes"
                            fill="#f59e0b"
                            name="Idle Nodes"
                            opacity={0.8}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}

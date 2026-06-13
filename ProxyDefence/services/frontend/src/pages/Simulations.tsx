import { useState } from "react";
import { Cpu, Play, RefreshCw, Shield, Sparkles } from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";

const Simulations = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [autoResponse, setAutoResponse] = useState(true);
  const { toast } = useToast();

  const handleRunSimulation = () => {
    setIsRunning(true);
    toast({
      title: "Simulation Started",
      description: "Running what-if scenario analysis...",
    });
    setTimeout(() => {
      setIsRunning(false);
      toast({
        title: "Simulation Complete",
        description: "Results are ready for review.",
      });
    }, 3000);
  };

  return (
    <AppShell
      title="Scenario simulations"
      subtitle="Stress-test automated response logic and explore what-if paths before actors escalate."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="mb-8 rounded-lg border border-border bg-card p-6 shadow-elevation lg:col-span-2">
          <h3 className="mb-4 text-lg font-semibold">Scenario Configuration</h3>

          <div className="space-y-6">
            <div>
              <Label className="mb-3 block text-base">Attack Type</Label>
              <div className="grid grid-cols-2 gap-3">
                <Button variant="outline" className="h-auto justify-start py-3">
                  <div className="text-left">
                    <p className="text-sm font-semibold">DDoS Attack</p>
                    <p className="text-xs text-muted-foreground">Distributed denial of service</p>
                  </div>
                </Button>
                <Button variant="outline" className="h-auto justify-start py-3">
                  <div className="text-left">
                    <p className="text-sm font-semibold">Proxy Chain</p>
                    <p className="text-xs text-muted-foreground">Multi-layer proxies</p>
                  </div>
                </Button>
                <Button variant="outline" className="h-auto justify-start py-3">
                  <div className="text-left">
                    <p className="text-sm font-semibold">Port Scan</p>
                    <p className="text-xs text-muted-foreground">Infrastructure mapping</p>
                  </div>
                </Button>
                <Button variant="outline" className="h-auto justify-start py-3">
                  <div className="text-left">
                    <p className="text-sm font-semibold">Combined Attack</p>
                    <p className="text-xs text-muted-foreground">Multi-vector assault</p>
                  </div>
                </Button>
              </div>
            </div>

            <div>
              <Label className="mb-3 block text-base">Threat Intensity</Label>
              <div className="flex gap-3">
                <Button variant="outline" size="sm">Low</Button>
                <Button variant="default" size="sm">Medium</Button>
                <Button variant="outline" size="sm">High</Button>
                <Button variant="outline" size="sm">Critical</Button>
              </div>
            </div>

            <div>
              <Label className="mb-3 block text-base">Simulation Options</Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label htmlFor="auto-response" className="cursor-pointer">
                    Automatic Response System
                  </Label>
                  <Switch
                    id="auto-response"
                    checked={autoResponse}
                    onCheckedChange={setAutoResponse}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="ml-prediction" className="cursor-pointer">
                    ML Prediction Mode
                  </Label>
                  <Switch id="ml-prediction" defaultChecked />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="real-time" className="cursor-pointer">
                    Real-time Monitoring
                  </Label>
                  <Switch id="real-time" defaultChecked />
                </div>
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <Button
                variant="hero"
                className="flex-1"
                disabled={isRunning}
                onClick={handleRunSimulation}
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Run Simulation
                  </>
                )}
              </Button>
              <Button variant="outline">Reset</Button>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
            <h4 className="mb-4 font-semibold">Simulation Stats</h4>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-muted-foreground">Total Runs</p>
                <p className="text-2xl font-bold">127</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Success Rate</p>
                <p className="text-2xl font-bold text-success">94%</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Avg Duration</p>
                <p className="text-2xl font-bold">2.4s</p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-warning/30 bg-warning/5 p-6">
            <Sparkles className="mb-3 h-8 w-8 text-warning" />
            <h4 className="mb-2 font-semibold text-warning">AI Training Mode</h4>
            <p className="text-sm text-muted-foreground">
              Simulations help train our ML models to predict and prevent future attacks.
            </p>
          </div>

          <div className="rounded-lg border border-primary/30 bg-primary/5 p-6">
            <Shield className="mb-3 h-8 w-8 text-primary" />
            <h4 className="mb-2 font-semibold">Operational use</h4>
            <p className="text-sm text-muted-foreground">
              Use simulation outcomes to rehearse escalation paths for cyber, economic, and kinetic flashpoints.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card shadow-elevation">
        <div className="border-b border-border p-6">
          <h3 className="text-lg font-semibold">Recent Simulations</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-6 py-3 text-left text-sm font-semibold">Scenario</th>
                <th className="px-6 py-3 text-left text-sm font-semibold">Intensity</th>
                <th className="px-6 py-3 text-left text-sm font-semibold">Result</th>
                <th className="px-6 py-3 text-left text-sm font-semibold">Duration</th>
                <th className="px-6 py-3 text-left text-sm font-semibold">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="px-6 py-4 text-sm">DDoS Attack</td>
                <td className="px-6 py-4">
                  <span className="rounded border border-accent/30 bg-accent/10 px-2 py-1 text-xs text-accent">
                    High
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="rounded border border-success/30 bg-success/10 px-2 py-1 text-xs text-success">
                    Success
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-muted-foreground">2.1s</td>
                <td className="px-6 py-4 text-sm text-muted-foreground">2 hours ago</td>
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm">Proxy Chain</td>
                <td className="px-6 py-4">
                  <span className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-xs text-warning">
                    Medium
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="rounded border border-success/30 bg-success/10 px-2 py-1 text-xs text-success">
                    Success
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-muted-foreground">1.8s</td>
                <td className="px-6 py-4 text-sm text-muted-foreground">5 hours ago</td>
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm">Combined Attack</td>
                <td className="px-6 py-4">
                  <span className="rounded border border-destructive/30 bg-destructive/10 px-2 py-1 text-xs text-destructive">
                    Critical
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-xs text-warning">
                    Partial
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-muted-foreground">4.2s</td>
                <td className="px-6 py-4 text-sm text-muted-foreground">1 day ago</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
};

export default Simulations;

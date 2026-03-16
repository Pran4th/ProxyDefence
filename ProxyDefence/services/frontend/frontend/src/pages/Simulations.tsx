import { Link } from "react-router-dom";
import { Activity, Shield, Settings, LogOut, BarChart3, Cpu, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";
import logo from "@/assets/logo.png";

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
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        <div className="p-6 border-b border-border">
          <Link to="/" className="flex items-center gap-3">
            <img src={logo} alt="ProxyDefence" className="h-8 w-8" />
            <span className="font-bold text-lg">ProxyDefence</span>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          <Link
            to="/dashboard"
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors"
          >
            <Activity className="h-5 w-5" />
            Dashboard
          </Link>
          <Link
            to="/analytics"
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors"
          >
            <BarChart3 className="h-5 w-5" />
            Analytics
          </Link>
          <Link
            to="/simulations"
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary/10 text-primary font-medium"
          >
            <Cpu className="h-5 w-5" />
            Simulations
          </Link>
          <Link
            to="/profile"
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors"
          >
            <Settings className="h-5 w-5" />
            Settings
          </Link>
        </nav>

        <div className="p-4 border-t border-border">
          <Link to="/">
            <Button variant="ghost" className="w-full justify-start" size="sm">
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">What-If Simulations</h1>
            <p className="text-muted-foreground">
              Test defense strategies against hypothetical attack scenarios
            </p>
          </div>

          {/* Simulation Controls */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="lg:col-span-2 rounded-lg border border-border bg-card p-6 shadow-elevation">
              <h3 className="text-lg font-semibold mb-4">Scenario Configuration</h3>
              
              <div className="space-y-6">
                <div>
                  <Label className="text-base mb-3 block">Attack Type</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <Button variant="outline" className="justify-start h-auto py-3">
                      <div className="text-left">
                        <p className="font-semibold text-sm">DDoS Attack</p>
                        <p className="text-xs text-muted-foreground">Distributed denial of service</p>
                      </div>
                    </Button>
                    <Button variant="outline" className="justify-start h-auto py-3">
                      <div className="text-left">
                        <p className="font-semibold text-sm">Proxy Chain</p>
                        <p className="text-xs text-muted-foreground">Multi-layer proxies</p>
                      </div>
                    </Button>
                    <Button variant="outline" className="justify-start h-auto py-3">
                      <div className="text-left">
                        <p className="font-semibold text-sm">Port Scan</p>
                        <p className="text-xs text-muted-foreground">Infrastructure mapping</p>
                      </div>
                    </Button>
                    <Button variant="outline" className="justify-start h-auto py-3">
                      <div className="text-left">
                        <p className="font-semibold text-sm">Combined Attack</p>
                        <p className="text-xs text-muted-foreground">Multi-vector assault</p>
                      </div>
                    </Button>
                  </div>
                </div>

                <div>
                  <Label className="text-base mb-3 block">Threat Intensity</Label>
                  <div className="flex gap-3">
                    <Button variant="outline" size="sm">Low</Button>
                    <Button variant="default" size="sm">Medium</Button>
                    <Button variant="outline" size="sm">High</Button>
                    <Button variant="outline" size="sm">Critical</Button>
                  </div>
                </div>

                <div>
                  <Label className="text-base mb-3 block">Simulation Options</Label>
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
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        Run Simulation
                      </>
                    )}
                  </Button>
                  <Button variant="outline">Reset</Button>
                </div>
              </div>
            </div>

            {/* Simulation Stats */}
            <div className="space-y-6">
              <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
                <h4 className="font-semibold mb-4">Simulation Stats</h4>
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
                <h4 className="font-semibold mb-2 text-warning">AI Training Mode</h4>
                <p className="text-sm text-muted-foreground">
                  Simulations help train our ML models to predict and prevent future attacks.
                </p>
              </div>
            </div>
          </div>

          {/* Recent Simulations */}
          <div className="rounded-lg border border-border bg-card shadow-elevation">
            <div className="p-6 border-b border-border">
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
                      <span className="px-2 py-1 rounded text-xs bg-accent/10 text-accent border border-accent/30">
                        High
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 rounded text-xs bg-success/10 text-success border border-success/30">
                        Success
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">2.1s</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">2 hours ago</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4 text-sm">Proxy Chain</td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 rounded text-xs bg-warning/10 text-warning border border-warning/30">
                        Medium
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 rounded text-xs bg-success/10 text-success border border-success/30">
                        Success
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">1.8s</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">5 hours ago</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4 text-sm">Combined Attack</td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 rounded text-xs bg-destructive/10 text-destructive border border-destructive/30">
                        Critical
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 rounded text-xs bg-warning/10 text-warning border border-warning/30">
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
        </div>
      </main>
    </div>
  );
};

export default Simulations;

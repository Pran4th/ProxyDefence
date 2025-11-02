import { Link } from "react-router-dom";
import { Activity, Shield, Settings, LogOut, BarChart3, Cpu, TrendingUp, TrendingDown, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import logo from "@/assets/logo.png";

const Analytics = () => {
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
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary/10 text-primary font-medium"
          >
            <BarChart3 className="h-5 w-5" />
            Analytics
          </Link>
          <Link
            to="/simulations"
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors"
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
            <h1 className="text-3xl font-bold mb-2">Threat Analytics</h1>
            <p className="text-muted-foreground">Deep dive into security metrics and trends</p>
          </div>

          {/* Time Period Selector */}
          <div className="flex gap-2 mb-8">
            <Button variant="default" size="sm">24 Hours</Button>
            <Button variant="outline" size="sm">7 Days</Button>
            <Button variant="outline" size="sm">30 Days</Button>
            <Button variant="outline" size="sm">Custom</Button>
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Threat Trends Chart */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Threat Trends</h3>
                <TrendingUp className="h-5 w-5 text-accent" />
              </div>
              <div className="aspect-video bg-muted/20 rounded-lg flex items-center justify-center">
                <p className="text-sm text-muted-foreground">Line chart visualization</p>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-accent">+23%</p>
                  <p className="text-xs text-muted-foreground">vs last week</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-primary">1,847</p>
                  <p className="text-xs text-muted-foreground">Total threats</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-success">98%</p>
                  <p className="text-xs text-muted-foreground">Blocked</p>
                </div>
              </div>
            </div>

            {/* Geographic Distribution */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Geographic Distribution</h3>
                <Target className="h-5 w-5 text-primary" />
              </div>
              <div className="aspect-video bg-muted/20 rounded-lg flex items-center justify-center">
                <p className="text-sm text-muted-foreground">World map heatmap</p>
              </div>
              <div className="mt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Eastern Europe</span>
                  <span className="font-semibold">34%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>East Asia</span>
                  <span className="font-semibold">28%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>North America</span>
                  <span className="font-semibold">18%</span>
                </div>
              </div>
            </div>

            {/* Attack Types */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Attack Types</h3>
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>DDoS</span>
                    <span>42%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-accent w-[42%]" />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Proxy Chain</span>
                    <span>31%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-primary w-[31%]" />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Port Scanning</span>
                    <span>18%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-threat w-[18%]" />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Other</span>
                    <span>9%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-muted-foreground w-[9%]" />
                  </div>
                </div>
              </div>
            </div>

            {/* Response Performance */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Response Performance</h3>
                <TrendingDown className="h-5 w-5 text-success" />
              </div>
              <div className="aspect-video bg-muted/20 rounded-lg flex items-center justify-center mb-4">
                <p className="text-sm text-muted-foreground">Area chart visualization</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-3 rounded-lg bg-success/10 border border-success/30">
                  <p className="text-2xl font-bold text-success">0.3s</p>
                  <p className="text-xs text-muted-foreground">Avg Response</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-primary/10 border border-primary/30">
                  <p className="text-2xl font-bold text-primary">99.7%</p>
                  <p className="text-xs text-muted-foreground">Success Rate</p>
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Stats Table */}
          <div className="rounded-lg border border-border bg-card shadow-elevation">
            <div className="p-6 border-b border-border">
              <h3 className="text-lg font-semibold">Detailed Statistics</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-semibold">Metric</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">Current</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">Previous</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  <tr>
                    <td className="px-6 py-4 text-sm">Total Threats Detected</td>
                    <td className="px-6 py-4 text-sm font-medium">1,847</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">1,502</td>
                    <td className="px-6 py-4 text-sm text-accent">+23%</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4 text-sm">Threats Blocked</td>
                    <td className="px-6 py-4 text-sm font-medium">1,810</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">1,468</td>
                    <td className="px-6 py-4 text-sm text-success">+23.3%</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4 text-sm">False Positives</td>
                    <td className="px-6 py-4 text-sm font-medium">5</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">12</td>
                    <td className="px-6 py-4 text-sm text-success">-58%</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4 text-sm">Average Response Time</td>
                    <td className="px-6 py-4 text-sm font-medium">0.3s</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">0.35s</td>
                    <td className="px-6 py-4 text-sm text-success">-14%</td>
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

export default Analytics;
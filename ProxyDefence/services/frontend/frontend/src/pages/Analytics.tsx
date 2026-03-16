import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Activity, Shield, Settings, LogOut, BarChart3, Cpu, TrendingUp, Target, TrendingDown } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import logo from "@/assets/logo.png";
import { fetchAnalyticsSummary, AnalyticsSummary } from "@/lib/api";

// Mock time-series data (until backend has a /timeseries endpoint)
const mockTimeSeriesData = [
  { time: "00:00", threats: 45, blocked: 42 },
  { time: "04:00", threats: 82, blocked: 78 },
  { time: "08:00", threats: 156, blocked: 151 },
  { time: "12:00", threats: 247, blocked: 240 },
  { time: "16:00", threats: 198, blocked: 195 },
  { time: "20:00", threats: 110, blocked: 108 },
  { time: "24:00", threats: 65, blocked: 63 },
];

const Analytics = () => {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const data = await fetchAnalyticsSummary();
        setSummary(data);
      } catch (error) {
        console.error("Failed to load analytics:", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Format sentiment data from backend for the BarChart
  const sentimentData = summary ? [
    { name: "Critical (Negative)", count: summary.sentiment_distribution?.negative || 0, fill: "hsl(var(--destructive))" },
    { name: "Medium (Neutral)", count: summary.sentiment_distribution?.neutral || 0, fill: "hsl(var(--warning))" },
    { name: "Low (Positive)", count: summary.sentiment_distribution?.positive || 0, fill: "hsl(var(--success))" },
  ] : [];

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
          <Link to="/dashboard" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors">
            <Activity className="h-5 w-5" /> Dashboard
          </Link>
          <Link to="/analytics" className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary/10 text-primary font-medium">
            <BarChart3 className="h-5 w-5" /> Analytics
          </Link>
          <Link to="/simulations" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors">
            <Cpu className="h-5 w-5" /> Simulations
          </Link>
          <Link to="/profile" className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors">
            <Settings className="h-5 w-5" /> Settings
          </Link>
        </nav>
        <div className="p-4 border-t border-border">
          <Link to="/">
            <Button variant="ghost" className="w-full justify-start" size="sm">
              <LogOut className="h-4 w-4 mr-2" /> Sign Out
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

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            
            {/* 1. Threat Trends Area Chart */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Threat Trends (24h)</h3>
                <TrendingUp className="h-5 w-5 text-accent" />
              </div>
              
              <div className="flex-1 min-h-[250px] w-full">
                <ChartContainer config={{ threats: { label: "Total Threats", color: "hsl(var(--accent))" }, blocked: { label: "Blocked", color: "hsl(var(--primary))" } }}>
                  <AreaChart data={mockTimeSeriesData} height={300} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorThreats" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--accent))" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="hsl(var(--accent))" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorBlocked" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={10} stroke="hsl(var(--muted-foreground))" />
                    <YAxis tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Area type="monotone" dataKey="threats" stroke="hsl(var(--accent))" fillOpacity={1} fill="url(#colorThreats)" strokeWidth={2} />
                    <Area type="monotone" dataKey="blocked" stroke="hsl(var(--primary))" fillOpacity={1} fill="url(#colorBlocked)" strokeWidth={2} />
                  </AreaChart>
                </ChartContainer>
              </div>

              {/* Stats Footer (Merged from your fragment) */}
              <div className="mt-4 grid grid-cols-3 gap-4 text-center border-t border-border pt-4">
                <div>
                  <p className="text-2xl font-bold text-accent">+{summary?.articles_last_24h || 0}</p>
                  <p className="text-xs text-muted-foreground">Last 24h</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-primary">{summary?.total_articles || 0}</p>
                  <p className="text-xs text-muted-foreground">Total threats</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-success">
                    {summary ? `${(summary.avg_confidence * 100).toFixed(1)}%` : "0%"}
                  </p>
                  <p className="text-xs text-muted-foreground">ML Confidence</p>
                </div>
              </div>
            </div>

            {/* 2. Sentiment Distribution Bar Chart */}
            <div className="rounded-lg border border-border bg-card p-6 shadow-elevation flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Threat Severity Distribution</h3>
                <Shield className="h-5 w-5 text-primary" />
              </div>

              <div className="flex-1 min-h-[250px] w-full flex items-center justify-center">
                {loading ? (
                    <div className="text-muted-foreground">Loading sentiment data...</div>
                ) : (
                    <ChartContainer config={{ 
                        negative: { label: "Critical", color: "hsl(var(--destructive))" }, 
                        neutral: { label: "Medium", color: "hsl(var(--warning))" },
                        positive: { label: "Low", color: "hsl(var(--success))" }
                    }} className="w-full h-[300px]">
                    <BarChart data={sentimentData} layout="vertical" margin={{ top: 0, right: 0, left: 40, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="hsl(var(--border))" />
                        <XAxis type="number" hide />
                        <YAxis dataKey="name" type="category" width={100} tickLine={false} axisLine={false} stroke="hsl(var(--foreground))" fontSize={12} />
                        <ChartTooltip cursor={{fill: 'transparent'}} content={<ChartTooltipContent />} />
                        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={32} />
                    </BarChart>
                    </ChartContainer>
                )}
              </div>
            </div>
          </div>

          {/* 3. Key Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
             <div className="p-6 rounded-lg border bg-card">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-accent/10 rounded-full">
                        <Target className="h-6 w-6 text-accent" />
                    </div>
                    <div>
                        <p className="text-sm text-muted-foreground">Attack Vectors</p>
                        <h4 className="text-2xl font-bold">12 Unique</h4>
                        <p className="text-xs text-accent mt-1 flex items-center">
                            <TrendingUp className="h-3 w-3 mr-1" /> +2 new today
                        </p>
                    </div>
                </div>
             </div>

             <div className="p-6 rounded-lg border bg-card">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-primary/10 rounded-full">
                        <Shield className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                        <p className="text-sm text-muted-foreground">Defense Efficiency</p>
                        <h4 className="text-2xl font-bold">99.8%</h4>
                        <p className="text-xs text-success mt-1 flex items-center">
                            <TrendingUp className="h-3 w-3 mr-1" /> +0.2% improvement
                        </p>
                    </div>
                </div>
             </div>

             <div className="p-6 rounded-lg border bg-card">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-success/10 rounded-full">
                        <TrendingDown className="h-6 w-6 text-success" />
                    </div>
                    <div>
                        <p className="text-sm text-muted-foreground">False Positives</p>
                        <h4 className="text-2xl font-bold">0.4%</h4>
                        <p className="text-xs text-success mt-1 flex items-center">
                            <TrendingDown className="h-3 w-3 mr-1" /> Lowest this week
                        </p>
                    </div>
                </div>
             </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default Analytics;
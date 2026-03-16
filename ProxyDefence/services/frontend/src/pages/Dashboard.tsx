import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Activity, Shield, Zap, AlertTriangle, Settings, LogOut, BarChart3, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import MetricCard from "@/components/MetricCard";
import ThreatMap from "@/components/ThreatMap";
import NewsCard from "@/components/NewsCard";
import logo from "@/assets/logo.png";

// 1. Import your API functions and types
import { fetchAnalyticsSummary, fetchArticles, AnalyticsSummary, Article } from "@/lib/api";

const Dashboard = () => {
  // 2. Set up state for your real data
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [latestThreats, setLatestThreats] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  // 3. Fetch data on mount
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        // Fetch summary metrics and the 4 latest articles in parallel
        const [summaryData, articlesData] = await Promise.all([
          fetchAnalyticsSummary(),
          fetchArticles(4, 0)
        ]);
        setSummary(summaryData);
        setLatestThreats(articlesData);
      } catch (error) {
        console.error("Failed to load dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  // Helper to map backend sentiment to frontend severity
  const getSeverity = (sentiment: string = 'neutral') => {
    switch (sentiment.toLowerCase()) {
      case 'negative': return 'critical';
      case 'positive': return 'low';
      default: return 'medium';
    }
  };

  // Helper for relative time formatting
  const getTimeAgo = (dateString: string) => {
    if (!dateString) return 'Just now';
    const seconds = Math.floor((new Date().getTime() - new Date(dateString).getTime()) / 1000);
    if (seconds < 60) return "Just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} minutes ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hours ago`;
    return `${Math.floor(hours / 24)} days ago`;
  };

  return (
    <div className="min-h-screen flex">
      {/* ... KEEP YOUR EXISTING SIDEBAR CODE HERE ... */}

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Defense Dashboard</h1>
            <p className="text-muted-foreground">Real-time threat monitoring and analysis</p>
          </div>

          {/* 4. Update Metrics Grid with Live Data */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <MetricCard
              title="Active Threats (24h)"
              value={loading ? "..." : (summary?.articles_last_24h || 0)}
              icon={AlertTriangle}
              trend={summary?.articles_last_24h && summary.articles_last_24h > 10 ? "up" : "down"}
              trendValue="Based on latest intel"
              variant="threat"
            />
            <MetricCard
              title="Total Processed Intel"
              value={loading ? "..." : (summary?.total_articles || 0)}
              icon={Shield}
              trend="up"
              trendValue="All time records"
              variant="safe"
            />
            <MetricCard
              title="Avg Threat Confidence"
              value={loading ? "..." : `${((summary?.avg_confidence || 0) * 100).toFixed(1)}%`}
              icon={Zap}
              trend="neutral"
              trendValue="ML Model Certainty"
            />
            <MetricCard
              title="Global Sentiment"
              value={loading ? "..." : (
                Object.entries(summary?.sentiment_distribution || {}).sort((a,b) => b[1]-a[1])[0]?.[0].toUpperCase() || "N/A"
              )}
              icon={Activity}
              trend="down"
              trendValue="Dominant Mood"
              variant="warning"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Main Threat Map Section */}
            <div className="lg:col-span-2">
              <ThreatMap />
              
              {/* Recent Alerts List */}
              <div className="mt-8">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-bold">Recent Intelligence</h3>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/news">View All Intel</Link>
                  </Button>
                </div>
                
                <div className="space-y-4">
                  {loading ? (
                    <p className="text-muted-foreground">Loading intelligence stream...</p>
                  ) : latestThreats.length > 0 ? (
                    latestThreats.map((article) => (
                      <NewsCard
                        key={article.id}
                        title={article.title}
                        description={article.content.substring(0, 120) + "..."}
                        timestamp={getTimeAgo(article.published_at)}
                        severity={getSeverity(article.sentiment)}
                        source={article.source}
                      />
                    ))
                  ) : (
                    <div className="p-8 text-center border rounded-lg bg-muted/10">
                      <p className="text-muted-foreground">No threats detected in the stream.</p>
                      <p className="text-xs text-muted-foreground mt-2">System is monitoring...</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Sidebar Stats */}
            <div className="space-y-6">
              <div className="rounded-lg border bg-card p-6">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  Sentiment Distribution
                </h3>
                <div className="space-y-4">
                  {['negative', 'neutral', 'positive'].map((sent) => {
                     const count = summary?.sentiment_distribution?.[sent] || 0;
                     const total = summary?.total_articles || 1; // avoid div by zero
                     const percentage = Math.round((count / total) * 100);
                     
                     let colorClass = "bg-muted";
                     if (sent === 'negative') colorClass = "bg-destructive";
                     if (sent === 'positive') colorClass = "bg-success";
                     if (sent === 'neutral') colorClass = "bg-warning";

                     return (
                      <div key={sent}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="capitalize">{sent}</span>
                          <span>{percentage}% ({count})</span>
                        </div>
                        <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${colorClass}`} 
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                     );
                  })}
                </div>
              </div>

              <div className="rounded-lg border bg-card p-6">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-primary" />
                  System Status
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Ingest Service</span>
                    <span className="flex h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">ML Pipeline</span>
                    <span className="flex h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Database</span>
                    <span className="flex h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">API Gateway</span>
                    <span className="flex h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
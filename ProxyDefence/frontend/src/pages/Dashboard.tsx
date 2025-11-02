import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Activity, Shield, Zap, AlertTriangle, Settings, LogOut, BarChart3, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import MetricCard from "@/components/MetricCard";
import ThreatMap from "@/components/ThreatMap";
import NewsCard from "@/components/NewsCard";
import logo from "@/assets/logo.png";

const Dashboard = () => {
  const [activeThreats, setActiveThreats] = useState(247);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveThreats((prev) => prev + Math.floor(Math.random() * 10) - 5);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

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
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary/10 text-primary font-medium"
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
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Defense Dashboard</h1>
            <p className="text-muted-foreground">Real-time threat monitoring and analysis</p>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <MetricCard
              title="Active Threats"
              value={activeThreats}
              icon={AlertTriangle}
              trend="down"
              trendValue="-12% last hour"
              variant="threat"
            />
            <MetricCard
              title="Protected Networks"
              value="1,429"
              icon={Shield}
              trend="up"
              trendValue="+8% growth"
              variant="safe"
            />
            <MetricCard
              title="Response Time"
              value="0.3s"
              icon={Zap}
              trend="neutral"
              trendValue="Optimal"
            />
            <MetricCard
              title="Threat Level"
              value="Medium"
              icon={Activity}
              trend="up"
              trendValue="Elevated"
              variant="warning"
            />
          </div>

          {/* Threat Map */}
          <div className="mb-8">
            <ThreatMap />
          </div>

          {/* Recent Activity */}
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">Latest Threats</h2>
              <Link to="/news">
                <Button variant="ghost" size="sm">
                  View All →
                </Button>
              </Link>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <NewsCard
                title="Critical DDoS attack detected on banking infrastructure"
                description="Coordinated attack from 47 proxy nodes targeting financial APIs. Automatic mitigation activated."
                timestamp="12 minutes ago"
                severity="critical"
                source="Real-time Alert"
              />
              <NewsCard
                title="Suspicious proxy chain identified in Eastern Europe"
                description="AI detected anomalous routing patterns consistent with reconnaissance activities."
                timestamp="34 minutes ago"
                severity="high"
                source="ML Detection"
              />
              <NewsCard
                title="New threat signature added to database"
                description="Advanced persistent threat pattern recognized and catalogued for future detection."
                timestamp="1 hour ago"
                severity="medium"
                source="System Update"
              />
              <NewsCard
                title="Weekly security report available"
                description="Comprehensive analysis of threat landscape for the past 7 days now ready for review."
                timestamp="2 hours ago"
                severity="low"
                source="Scheduled Report"
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
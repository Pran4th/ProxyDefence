import Navbar from "@/components/Navbar";
import NewsCard from "@/components/NewsCard";
import { Button } from "@/components/ui/button";
import { Lock, Filter } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";

const News = () => {
  const [selectedFilter, setSelectedFilter] = useState<string>("all");

  const publicNews = [
    {
      title: "Major DDoS attack detected targeting financial sector",
      description: "Multiple banking institutions report coordinated proxy-based attacks originating from distributed sources across 12 countries.",
      timestamp: "2 hours ago",
      severity: "high" as const,
      source: "ProxyDefence Intel",
    },
    {
      title: "New proxy detection algorithm reduces false positives by 89%",
      description: "ProxyDefence AI successfully identifies sophisticated proxy chains with unprecedented accuracy using advanced ML models.",
      timestamp: "5 hours ago",
      severity: "medium" as const,
      source: "Tech Update",
    },
    {
      title: "Global cyber threat level elevated to medium-high",
      description: "International security agencies report increased proxy-based reconnaissance activities targeting critical infrastructure.",
      timestamp: "8 hours ago",
      severity: "high" as const,
      source: "Security Alert",
    },
    {
      title: "ProxyDefence expands coverage to 150+ countries",
      description: "New honeypot deployments enable comprehensive threat monitoring across emerging markets and developing regions.",
      timestamp: "1 day ago",
      severity: "low" as const,
      source: "Company News",
    },
    {
      title: "Sophisticated botnet dismantled in international operation",
      description: "Law enforcement agencies collaborate with ProxyDefence to identify and neutralize major proxy-based botnet infrastructure.",
      timestamp: "2 days ago",
      severity: "medium" as const,
      source: "Breaking News",
    },
  ];

  return (
    <div className="min-h-screen">
      <Navbar />
      
      <div className="pt-24 pb-20">
        <div className="container mx-auto px-4">
          {/* Header */}
          <div className="max-w-4xl mx-auto text-center mb-12 animate-fade-in">
            <h1 className="text-5xl font-bold mb-4 bg-gradient-primary bg-clip-text text-transparent">
              Threat Intelligence Feed
            </h1>
            <p className="text-xl text-muted-foreground">
              Stay informed with the latest cybersecurity threats and defense updates
            </p>
          </div>

          {/* Filter Bar */}
          <div className="mb-8 flex flex-wrap gap-3 items-center justify-between">
            <div className="flex gap-2 flex-wrap">
              <Button
                variant={selectedFilter === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("all")}
              >
                All News
              </Button>
              <Button
                variant={selectedFilter === "critical" ? "threat" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("critical")}
              >
                Critical
              </Button>
              <Button
                variant={selectedFilter === "high" ? "outline" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("high")}
              >
                High
              </Button>
              <Button
                variant={selectedFilter === "medium" ? "outline" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("medium")}
              >
                Medium
              </Button>
            </div>
            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              More Filters
            </Button>
          </div>

          {/* Public News Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
            {publicNews.map((news, index) => (
              <NewsCard key={index} {...news} />
            ))}
          </div>

          {/* Premium Content Teaser */}
          <div className="max-w-4xl mx-auto">
            <div className="p-8 rounded-xl border-2 border-dashed border-primary/30 bg-gradient-to-br from-primary/5 to-accent/5 text-center">
              <Lock className="h-12 w-12 text-primary mx-auto mb-4" />
              <h3 className="text-2xl font-bold mb-3">
                Unlock Full Threat Intelligence
              </h3>
              <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
                Get access to real-time alerts, detailed threat reports, vulnerability assessments,
                and custom intelligence feeds tailored to your organization's needs.
              </p>
              <div className="flex gap-4 justify-center flex-wrap mb-6">
                <div className="px-4 py-2 rounded-lg bg-card border border-border">
                  <p className="text-sm text-muted-foreground">+ Real-time Alerts</p>
                </div>
                <div className="px-4 py-2 rounded-lg bg-card border border-border">
                  <p className="text-sm text-muted-foreground">+ Detailed Reports</p>
                </div>
                <div className="px-4 py-2 rounded-lg bg-card border border-border">
                  <p className="text-sm text-muted-foreground">+ Custom Feeds</p>
                </div>
                <div className="px-4 py-2 rounded-lg bg-card border border-border">
                  <p className="text-sm text-muted-foreground">+ API Access</p>
                </div>
              </div>
              <Link to="/auth">
                <Button variant="hero" size="lg">
                  Sign In to Access Premium Content
                </Button>
              </Link>
            </div>
          </div>

          {/* Info Section */}
          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-lg bg-card border border-border">
              <h4 className="font-semibold mb-2">Real-Time Updates</h4>
              <p className="text-sm text-muted-foreground">
                Premium members receive instant notifications for critical threats affecting their region or industry.
              </p>
            </div>
            <div className="p-6 rounded-lg bg-card border border-border">
              <h4 className="font-semibold mb-2">Expert Analysis</h4>
              <p className="text-sm text-muted-foreground">
                Each threat is analyzed by our security research team with actionable recommendations.
              </p>
            </div>
            <div className="p-6 rounded-lg bg-card border border-border">
              <h4 className="font-semibold mb-2">Historical Data</h4>
              <p className="text-sm text-muted-foreground">
                Access our complete archive of threat intelligence reports dating back 5 years.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default News;

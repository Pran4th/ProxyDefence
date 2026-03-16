import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Shield, Activity, Globe, Zap, Lock, TrendingUp } from "lucide-react";
import Navbar from "@/components/Navbar";
import MetricCard from "@/components/MetricCard";
import NewsCard from "@/components/NewsCard";
import heroBg from "@/assets/hero-bg.png";

// --- Helper Functions for Data Formatting ---
const getSeverity = (sentiment) => {
  if (sentiment === 'negative') return 'high'; // Red
  if (sentiment === 'positive') return 'low';  // Green
  return 'medium';                             // Yellow/Blue
};

const getTimeAgo = (dateString) => {
  if (!dateString) return 'Just now';
  
  // 1. Convert to Date objects
  const now = new Date();
  const past = new Date(dateString);

  // 2. Check if the date is valid before doing math
  if (isNaN(past.getTime())) {
    return 'Just now'; 
  }

  // 3. Use .getTime() to safely get milliseconds
  const seconds = Math.floor((now.getTime() - past.getTime()) / 1000);

  // 4. Handle Future Dates (Clock skew issues)
  if (seconds < 0) return 'Just now';

  let interval = seconds / 3600;
  if (interval > 1) return Math.floor(interval) + " hours ago";
  
  interval = seconds / 60;
  if (interval > 1) return Math.floor(interval) + " minutes ago";
  
  return Math.floor(seconds) + " seconds ago";
};

const Landing = () => {
  // --- State for Dynamic Data ---
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  // --- Fetch Data from Conflict API ---
  useEffect(() => {
    const fetchNews = async () => {
      try {
        // Try env var first, fallback to your Docker port 8004
        const baseUrl = process.env.REACT_APP_API_URL || "http://localhost:8004";
        
        // Fetch 2 articles to match your grid layout
        const res = await fetch(`${baseUrl}/articles?limit=2`);
        
        if (res.ok) {
          const data = await res.json();
          setArticles(data);
        } else {
          console.error("Failed to fetch articles");
        }
      } catch (error) {
        console.error("Error connecting to backend:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, []);

  return (
    <div className="min-h-screen">
      <Navbar />
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: `url(${heroBg})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background/80 to-background" />
        
        <div className="container relative z-10 mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center animate-fade-in">
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-primary bg-clip-text text-transparent">
              Advanced Proxy Defense Intelligence
            </h1>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Real-time threat monitoring, predictive analytics, and what-if simulations
              for next-generation cyber defense operations.
            </p>
            <div className="flex gap-4 justify-center flex-wrap">
              <Link to="/auth">
                <Button variant="hero" size="lg">
                  Start Free Trial
                </Button>
              </Link>
              <Link to="/about">
                <Button variant="outline" size="lg">
                  Learn More
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Live Metrics Section */}
      <section className="py-16 bg-muted/20">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold mb-8 text-center">
            Live Defense Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="Active Threats"
              value="247"
              icon={Shield}
              trend="down"
              trendValue="-12% from last hour"
              variant="threat"
            />
            <MetricCard
              title="Protected Networks"
              value="1,429"
              icon={Globe}
              trend="up"
              trendValue="+8% growth"
              variant="safe"
            />
            <MetricCard
              title="Response Time"
              value="0.3s"
              icon={Zap}
              trend="neutral"
              trendValue="Average"
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
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">
              Military-Grade Defense Platform
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Powered by advanced AI and real-time intelligence gathering
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 rounded-lg border border-border bg-card shadow-elevation hover:shadow-glow transition-all">
              <div className="h-12 w-12 rounded-lg bg-gradient-primary flex items-center justify-center mb-4">
                <Activity className="h-6 w-6 text-primary-foreground" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Real-Time Monitoring</h3>
              <p className="text-muted-foreground">
                Track threats across the globe with millisecond precision and automated response systems.
              </p>
            </div>

            <div className="p-6 rounded-lg border border-border bg-card shadow-elevation hover:shadow-glow transition-all">
              <div className="h-12 w-12 rounded-lg bg-gradient-accent flex items-center justify-center mb-4">
                <TrendingUp className="h-6 w-6 text-white" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Predictive Analytics</h3>
              <p className="text-muted-foreground">
                ML-powered threat prediction to stay ahead of attackers with what-if scenario modeling.
              </p>
            </div>

            <div className="p-6 rounded-lg border border-border bg-card shadow-elevation hover:shadow-glow transition-all">
              <div className="h-12 w-12 rounded-lg bg-gradient-safe flex items-center justify-center mb-4">
                <Lock className="h-6 w-6 text-success-foreground" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Automated Defense</h3>
              <p className="text-muted-foreground">
                Instant threat neutralization with AI-driven countermeasures and adaptive protection.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* News Preview Section (CONNECTED TO BACKEND) */}
      <section className="py-20 bg-muted/20">
        <div className="container mx-auto px-4">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-3xl font-bold">Latest Threat Intelligence</h2>
            <Link to="/news">
              <Button variant="ghost">View All →</Button>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {loading ? (
              // Loading Skeleton (Matches your design)
              <>
                <div className="h-48 rounded-lg border border-border bg-card animate-pulse flex items-center justify-center text-muted-foreground">
                  Connecting to ProxyDefence Neural Network...
                </div>
                <div className="h-48 rounded-lg border border-border bg-card animate-pulse hidden md:block"></div>
              </>
            ) : articles.length > 0 ? (
              // Real Data from API
              articles.map((article) => (
                <NewsCard
                  key={article.id}
                  title={article.title}
                  // Truncate description gracefully
                  description={
                    article.content 
                      ? article.content.substring(0, 140) + "..." 
                      : "No intelligence data available for this feed item."
                  }
                  timestamp={getTimeAgo(article.published_at)}
                  severity={getSeverity(article.sentiment)}
                />
              ))
            ) : (
              // Fallback (Only shows if DB is empty)
              <div className="col-span-2 text-center py-10 text-muted-foreground">
                No active threats detected in the current sector.
              </div>
            )}
          </div>

          <div className="mt-8 p-6 rounded-lg border border-primary/30 bg-primary/5">
            <p className="text-center text-muted-foreground">
              <Lock className="inline h-4 w-4 mr-2" />
              Sign in to access full threat intelligence reports and real-time alerts
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center bg-gradient-to-br from-primary/10 to-accent/10 rounded-2xl p-12 border border-primary/20">
            <h2 className="text-4xl font-bold mb-4">
              Ready to Secure Your Network?
            </h2>
            <p className="text-xl text-muted-foreground mb-8">
              Join 1,400+ organizations protecting their infrastructure with ProxyDefence
            </p>
            <Link to="/auth">
              <Button variant="hero" size="lg">
                Get Started Now
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link to="/about" className="hover:text-primary transition-colors">About</Link></li>
                <li><Link to="/news" className="hover:text-primary transition-colors">News</Link></li>
                <li><Link to="/auth" className="hover:text-primary transition-colors">Pricing</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-primary transition-colors">Documentation</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">API</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Support</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-primary transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-primary transition-colors">Privacy</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Terms</a></li>
                <li><a href="#" className="hover:text-primary transition-colors">Security</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-border text-center text-sm text-muted-foreground">
            <p>© 2025 ProxyDefence. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
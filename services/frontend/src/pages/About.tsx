import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Logo from "@/components/Logo";
import { Target, Zap, Lock, Globe, BrainCircuit, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { fetchPublicPreview, type PublicPreview } from "@/lib/api";

const About = () => {
  const [preview, setPreview] = useState<PublicPreview | null>(null);

  useEffect(() => {
    fetchPublicPreview().then(setPreview).catch(() => undefined);
  }, []);

  const stats = preview?.stats;

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="pt-24 pb-20">
        <div className="container mx-auto px-4">
          {/* Hero Section */}
          <div className="max-w-4xl mx-auto text-center mb-20 animate-fade-in">
            <h1 className="text-5xl font-bold mb-6 bg-gradient-primary bg-clip-text text-transparent">
              Defending Digital Infrastructure
            </h1>
            <p className="text-xl text-muted-foreground">
              ProxyDefence fuses live news ingestion, trained ML models, and multi-source
              geopolitical data into one real-time energy and threat intelligence platform.
            </p>
          </div>

          {/* Mission Section */}
          <section className="mb-20">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl font-bold mb-4">Our Mission</h2>
                <p className="text-lg text-muted-foreground mb-6">
                  We're building real-time geopolitical and energy-supply-chain intelligence by
                  fusing streaming news with structured data — sanctions lists, vessel tracking,
                  commodity prices, and conflict-event data — and scoring it all with trained
                  machine learning models, not keyword heuristics.
                </p>
                <p className="text-lg text-muted-foreground">
                  Every number on this page reflects what's actually running in the platform
                  right now, queried live from the same database the analyst workspace uses.
                </p>
              </div>
              <div className="relative">
                <div className="aspect-square rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 p-8 flex items-center justify-center">
                  <Logo className="h-40 w-40" />
                </div>
              </div>
            </div>
          </section>

          {/* Values Section */}
          <section className="mb-20">
            <h2 className="text-3xl font-bold mb-12 text-center">Core Values</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="p-8 rounded-lg border border-border bg-card shadow-elevation">
                <Target className="h-10 w-10 text-primary mb-4" />
                <h3 className="text-xl font-semibold mb-3">Precision</h3>
                <p className="text-muted-foreground">
                  Trained classifiers, not keyword matching — every threat score, topic label,
                  and risk classification comes from a model with a measured validation metric.
                </p>
              </div>
              <div className="p-8 rounded-lg border border-border bg-card shadow-elevation">
                <Zap className="h-10 w-10 text-primary mb-4" />
                <h3 className="text-xl font-semibold mb-3">Freshness</h3>
                <p className="text-muted-foreground">
                  News ingestion runs hourly across two independent providers, so the risk
                  picture reflects what's happening now, not last week.
                </p>
              </div>
              <div className="p-8 rounded-lg border border-border bg-card shadow-elevation">
                <Lock className="h-10 w-10 text-primary mb-4" />
                <h3 className="text-xl font-semibold mb-3">Honesty</h3>
                <p className="text-muted-foreground">
                  When a data source has a real gap — a currency with no exchange-rate coverage,
                  a region with thin sensor data — we show that gap instead of papering over it.
                </p>
              </div>
            </div>
          </section>

          {/* Technology Section */}
          <section className="mb-20 bg-muted/20 rounded-2xl p-12">
            <h2 className="text-3xl font-bold mb-8 text-center">
              Powered by Real Data, Not Demos
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                  <Globe className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Multi-Source Data Fusion</h3>
                  <p className="text-sm text-muted-foreground">
                    GDELT global events, EIA energy statistics, AIS vessel tracking, OFAC/EU/UN
                    sanctions lists, and commodity prices — unified into one canonical schema.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-accent flex items-center justify-center flex-shrink-0">
                  <BrainCircuit className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Trained ML Models</h3>
                  <p className="text-sm text-muted-foreground">
                    An XGBoost disruption-risk classifier, a topic classifier beating naive
                    baselines by double digits, and dedicated price and procurement forecasters.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-safe flex items-center justify-center flex-shrink-0">
                  <Zap className="h-6 w-6 text-success-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Live Simulation Engine</h3>
                  <p className="text-sm text-muted-foreground">
                    A digital-twin network model lets analysts run what-if scenarios — chokepoint
                    closures, refinery outages — and see the projected supply gap.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                  <Users className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Built for Analysts</h3>
                  <p className="text-sm text-muted-foreground">
                    Cases, generated intelligence briefs, watchable search, and a graph explorer
                    designed around how threat analysts actually investigate a story.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Stats Section */}
          <section className="mb-20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">
                  {stats ? stats.trained_models : "—"}
                </p>
                <p className="text-sm text-muted-foreground">Trained ML Models</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">
                  {stats ? stats.datasets : "—"}
                </p>
                <p className="text-sm text-muted-foreground">Live Data Sources</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">
                  {stats ? `${Math.round(stats.avg_confidence * 100)}%` : "—"}
                </p>
                <p className="text-sm text-muted-foreground">Avg. ML Confidence</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">
                  {stats ? stats.total_articles : "—"}
                </p>
                <p className="text-sm text-muted-foreground">Articles Analyzed</p>
              </div>
            </div>
          </section>

          {/* CTA Section */}
          <section>
            <div className="max-w-3xl mx-auto text-center bg-gradient-to-br from-primary/10 to-accent/10 rounded-2xl p-12 border border-primary/20">
              <h2 className="text-3xl font-bold mb-4">
                See the Full Picture
              </h2>
              <p className="text-lg text-muted-foreground mb-8">
                Create a free analyst account to explore the live threat feed, entity graph,
                risk dashboard, and simulation engine.
              </p>
              <Link to="/auth">
                <Button variant="hero" size="lg">
                  Create Free Account
                </Button>
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default About;

import Navbar from "@/components/Navbar";
import { Shield, Target, Users, Zap, Globe, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

const About = () => {
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
              ProxyDefence is the world's most advanced proxy threat intelligence platform,
              powered by AI and trusted by enterprises globally.
            </p>
          </div>

          {/* Mission Section */}
          <section className="mb-20">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl font-bold mb-4">Our Mission</h2>
                <p className="text-lg text-muted-foreground mb-6">
                  We're building the future of cybersecurity through real-time threat intelligence,
                  predictive analytics, and automated defense systems. Our platform protects
                  critical infrastructure from sophisticated proxy-based attacks that traditional
                  security solutions miss.
                </p>
                <p className="text-lg text-muted-foreground">
                  By combining cutting-edge machine learning with global threat data, we empower
                  security teams to stay ahead of attackers and protect what matters most.
                </p>
              </div>
              <div className="relative">
                <div className="aspect-square rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 p-8 flex items-center justify-center">
                  <Shield className="h-48 w-48 text-primary opacity-50" />
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
                  We deliver accuracy at scale, minimizing false positives while catching
                  sophisticated threats that others miss.
                </p>
              </div>
              <div className="p-8 rounded-lg border border-border bg-card shadow-elevation">
                <Zap className="h-10 w-10 text-primary mb-4" />
                <h3 className="text-xl font-semibold mb-3">Speed</h3>
                <p className="text-muted-foreground">
                  Millisecond response times ensure threats are neutralized before they
                  can cause damage to your infrastructure.
                </p>
              </div>
              <div className="p-8 rounded-lg border border-border bg-card shadow-elevation">
                <Lock className="h-10 w-10 text-primary mb-4" />
                <h3 className="text-xl font-semibold mb-3">Trust</h3>
                <p className="text-muted-foreground">
                  Enterprise-grade security and privacy protections keep your data safe
                  while we protect your networks.
                </p>
              </div>
            </div>
          </section>

          {/* Technology Section */}
          <section className="mb-20 bg-muted/20 rounded-2xl p-12">
            <h2 className="text-3xl font-bold mb-8 text-center">
              Powered by Advanced Technology
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                  <Globe className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Global Threat Network</h3>
                  <p className="text-sm text-muted-foreground">
                    Real-time data collection from 150+ countries and 10,000+ honeypots
                    worldwide provides unmatched visibility.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-accent flex items-center justify-center flex-shrink-0">
                  <Target className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">AI-Powered Detection</h3>
                  <p className="text-sm text-muted-foreground">
                    Machine learning models trained on billions of data points identify
                    threats with 99.7% accuracy.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-safe flex items-center justify-center flex-shrink-0">
                  <Zap className="h-6 w-6 text-success-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Automated Response</h3>
                  <p className="text-sm text-muted-foreground">
                    Instant threat mitigation through automated countermeasures and
                    adaptive defense strategies.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="h-12 w-12 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                  <Users className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Expert Team</h3>
                  <p className="text-sm text-muted-foreground">
                    Security researchers and engineers with decades of combined experience
                    in threat intelligence.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Stats Section */}
          <section className="mb-20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">1.4K+</p>
                <p className="text-sm text-muted-foreground">Protected Networks</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">99.7%</p>
                <p className="text-sm text-muted-foreground">Detection Accuracy</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">0.3s</p>
                <p className="text-sm text-muted-foreground">Avg Response Time</p>
              </div>
              <div className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">24/7</p>
                <p className="text-sm text-muted-foreground">Global Monitoring</p>
              </div>
            </div>
          </section>

          {/* CTA Section */}
          <section>
            <div className="max-w-3xl mx-auto text-center bg-gradient-to-br from-primary/10 to-accent/10 rounded-2xl p-12 border border-primary/20">
              <h2 className="text-3xl font-bold mb-4">
                Join the Defense Revolution
              </h2>
              <p className="text-lg text-muted-foreground mb-8">
                Experience enterprise-grade protection with our 14-day free trial.
                No credit card required.
              </p>
              <Link to="/auth">
                <Button variant="hero" size="lg">
                  Start Your Free Trial
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
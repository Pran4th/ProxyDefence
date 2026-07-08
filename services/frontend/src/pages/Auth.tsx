import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Shield, LockKeyhole, UserPlus } from "lucide-react";

import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/context/AuthContext";

const Auth = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/dashboard";

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      if (isRegisterMode) {
        await register(email, username, password);
      } else {
        await login(email, password);
      }

      toast({
        title: isRegisterMode ? "Account created" : "Welcome back",
        description: "Secure access to ProxyDefence has been granted.",
      });
      navigate(redirectTo, { replace: true });
    } catch (error: any) {
      toast({
        title: "Authentication failed",
        description: error?.response?.data?.detail || error.message || "Unable to complete authentication.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="relative overflow-hidden px-4 pb-20 pt-28">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.22),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(239,68,68,0.16),transparent_28%)]" />
        <div className="relative mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-[2rem] border border-border bg-card/60 p-8 shadow-elevation backdrop-blur lg:p-10">
            <div className="mb-8">
              <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-primary">
                <Shield className="h-3.5 w-3.5" />
                Analyst Identity
              </p>
              <h1 className="text-4xl font-bold leading-tight">
                {isRegisterMode ? "Create your ProxyDefence operator account" : "Sign in to the intelligence workspace"}
              </h1>
              <p className="mt-3 max-w-xl text-muted-foreground">
                Access the live threat feed, geopolitical analytics, entity graphing, and the ML intelligence console.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {isRegisterMode && (
                <div>
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="intel-operator"
                    className="mt-2"
                    required
                  />
                </div>
              )}
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="analyst@proxydefence.io"
                  className="mt-2"
                  required
                />
              </div>
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  className="mt-2"
                  required
                />
              </div>
              <Button type="submit" variant="hero" className="w-full" disabled={loading}>
                {loading ? "Authenticating..." : isRegisterMode ? "Create account" : "Sign in"}
              </Button>
            </form>

            <div className="mt-6 flex items-center justify-between rounded-2xl border border-border bg-background/70 px-4 py-3">
              <div className="flex items-center gap-3">
                {isRegisterMode ? <UserPlus className="h-4 w-4 text-primary" /> : <LockKeyhole className="h-4 w-4 text-primary" />}
                <p className="text-sm text-muted-foreground">
                  {isRegisterMode ? "Already provisioned?" : "Need analyst access?"}
                </p>
              </div>
              <Button variant="ghost" onClick={() => setIsRegisterMode((value) => !value)}>
                {isRegisterMode ? "Sign in instead" : "Register instead"}
              </Button>
            </div>
          </section>

          <aside className="space-y-6 rounded-[2rem] border border-border bg-card/50 p-8 shadow-elevation backdrop-blur">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Security model</p>
              <h2 className="mt-3 text-2xl font-semibold">JWT-authenticated analyst workflows</h2>
            </div>
            <div className="space-y-4">
              {[
                "Protected intelligence dashboards with role-aware access.",
                "Token-based API authentication for search, analytics, and graph data.",
                "Password hashing and persistent user identities in PostgreSQL.",
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-border bg-background/60 p-4 text-sm text-muted-foreground">
                  {item}
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
};

export default Auth;

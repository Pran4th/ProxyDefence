import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LockKeyhole, UserPlus, Check, X } from "lucide-react";

import Navbar from "@/components/Navbar";
import Logo from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/context/AuthContext";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface FieldErrors {
  email?: string;
  username?: string;
  password?: string;
  confirmPassword?: string;
}

const Auth = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/dashboard";

  const passwordChecks = useMemo(
    () => ({
      length: password.length >= 8,
      letter: /[a-zA-Z]/.test(password),
      number: /[0-9]/.test(password),
    }),
    [password]
  );

  const errors: FieldErrors = useMemo(() => {
    const next: FieldErrors = {};
    if (!email) next.email = "Email is required.";
    else if (!EMAIL_PATTERN.test(email)) next.email = "Enter a valid email address.";

    if (isRegisterMode && username.trim().length < 3) {
      next.username = "Username must be at least 3 characters.";
    }

    if (!password) next.password = "Password is required.";
    else if (isRegisterMode && !(passwordChecks.length && passwordChecks.letter && passwordChecks.number)) {
      next.password = "Password doesn't meet the requirements below.";
    } else if (!isRegisterMode && password.length < 8) {
      next.password = "Password must be at least 8 characters.";
    }

    if (isRegisterMode && confirmPassword !== password) {
      next.confirmPassword = "Passwords don't match.";
    }

    return next;
  }, [email, username, password, confirmPassword, isRegisterMode, passwordChecks]);

  const isValid = Object.keys(errors).length === 0;

  const markTouched = (field: string) => setTouched((t) => ({ ...t, [field]: true }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setTouched({ email: true, username: true, password: true, confirmPassword: true });
    if (!isValid) return;

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

  const fieldError = (field: keyof FieldErrors) => (touched[field] ? errors[field] : undefined);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="relative overflow-hidden px-4 pb-20 pt-28">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.22),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(239,68,68,0.16),transparent_28%)]" />
        <div className="relative mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-[2rem] border border-border bg-card/60 p-8 shadow-elevation backdrop-blur lg:p-10">
            <div className="mb-8">
              <div className="mb-4 flex items-center gap-3">
                <Logo className="h-10 w-10" />
                <p className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-primary">
                  Analyst Identity
                </p>
              </div>
              <h1 className="text-4xl font-bold leading-tight">
                {isRegisterMode ? "Create your ProxyDefence operator account" : "Sign in to the intelligence workspace"}
              </h1>
              <p className="mt-3 max-w-xl text-muted-foreground">
                Access the live threat feed, geopolitical analytics, entity graphing, and the ML intelligence console.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
              {isRegisterMode && (
                <div>
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    onBlur={() => markTouched("username")}
                    placeholder="intel-operator"
                    className="mt-2"
                    aria-invalid={!!fieldError("username")}
                  />
                  {fieldError("username") && (
                    <p className="mt-1.5 text-xs text-destructive">{fieldError("username")}</p>
                  )}
                </div>
              )}
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  onBlur={() => markTouched("email")}
                  placeholder="analyst@proxydefence.io"
                  className="mt-2"
                  aria-invalid={!!fieldError("email")}
                />
                {fieldError("email") && <p className="mt-1.5 text-xs text-destructive">{fieldError("email")}</p>}
              </div>
              <div>
                <Label htmlFor="password">Password</Label>
                <div className="relative mt-2">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    onBlur={() => markTouched("password")}
                    placeholder="At least 8 characters"
                    className="pr-10"
                    aria-invalid={!!fieldError("password")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {fieldError("password") && <p className="mt-1.5 text-xs text-destructive">{fieldError("password")}</p>}

                {isRegisterMode && (password.length > 0 || touched.password) && (
                  <div className="mt-2 space-y-1">
                    {[
                      { ok: passwordChecks.length, label: "At least 8 characters" },
                      { ok: passwordChecks.letter, label: "Contains a letter" },
                      { ok: passwordChecks.number, label: "Contains a number" },
                    ].map((req) => (
                      <div
                        key={req.label}
                        className={`flex items-center gap-1.5 text-xs ${req.ok ? "text-success" : "text-muted-foreground"}`}
                      >
                        {req.ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                        {req.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {isRegisterMode && (
                <div>
                  <Label htmlFor="confirm-password">Confirm password</Label>
                  <Input
                    id="confirm-password"
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    onBlur={() => markTouched("confirmPassword")}
                    placeholder="Re-enter your password"
                    className="mt-2"
                    aria-invalid={!!fieldError("confirmPassword")}
                  />
                  {fieldError("confirmPassword") && (
                    <p className="mt-1.5 text-xs text-destructive">{fieldError("confirmPassword")}</p>
                  )}
                </div>
              )}

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
              <Button
                variant="ghost"
                onClick={() => {
                  setIsRegisterMode((value) => !value);
                  setTouched({});
                }}
              >
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

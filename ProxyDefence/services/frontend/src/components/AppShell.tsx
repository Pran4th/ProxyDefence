import { Link, NavLink } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Cpu,
  Globe2,
  CalendarDays,
  LogOut,
  Settings,
  Shield,
  UserCircle2,
  Bot,
  FileText,
  Bell,
  ShieldCheck,
  Search as SearchIcon
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import logo from "@/assets/logo.png";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: Activity },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/entities", label: "Entities", icon: Globe2 },
  { to: "/simulations", label: "Simulations", icon: Cpu },
  { to: "/profile", label: "Profile", icon: Settings },
  { to: "/events", label: "Events", icon: CalendarDays },
  {to: "/search",label: "Search",icon: SearchIcon},
  
  {
  to: "/copilot",
  label: "Copilot",
  icon: Bot,
},
{
  to: "/briefings",
  label: "Briefings",
  icon: FileText,
},
{
  to: "/alerts",
  label: "Alerts",
  icon: Bell,
},
{
  to: "/watchlists",
  label: "Watchlists",
  icon: ShieldCheck,
},
{
  to: "/cases",
  label: "Cases",
  icon: Shield,
},
{
  to: "/reports",
  label: "Reports",
  icon: FileText,
},
];

const AppShell = ({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) => {
  const { logout, user } = useAuth();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 border-r border-border bg-card/60 backdrop-blur xl:flex xl:flex-col">
          <div className="border-b border-border px-6 py-5">
            <Link to="/" className="flex items-center gap-3">
              <img src={logo} alt="ProxyDefence" className="h-10 w-10 rounded-xl" />
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">ProxyDefence</p>
                <p className="text-lg font-semibold">Intelligence Core</p>
              </div>
            </Link>
          </div>

          <div className="flex-1 px-4 py-6">
            <div className="mb-6 rounded-2xl border border-primary/20 bg-primary/5 p-4">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-full bg-primary/15">
                  <UserCircle2 className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{user?.username ?? "Analyst"}</p>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">{user?.role ?? "observer"}</p>
                </div>
              </div>
            </div>

            <nav className="space-y-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-3 rounded-xl px-4 py-3 text-sm transition-colors",
                        isActive
                          ? "bg-primary text-primary-foreground shadow-glow"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      ].join(" ")
                    }
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          <div className="border-t border-border px-4 py-4">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={logout}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </aside>

        <main className="flex-1">
          <header className="border-b border-border bg-background/80 backdrop-blur">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Threat Intelligence Workspace</p>
                <h1 className="text-3xl font-bold">{title}</h1>
                <p className="text-sm text-muted-foreground">{subtitle}</p>
              </div>
              <div className="hidden items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3 md:flex">
                <Shield className="h-4 w-4 text-primary" />
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Session</p>
                  <p className="text-sm font-medium">Authenticated intelligence access</p>
                </div>
              </div>
            </div>
          </header>
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</div>
        </main>
      </div>
    </div>
  );
};

export default AppShell;

import { Menu, Shield } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import logo from "@/assets/logo.png";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/about", label: "About" },
  { to: "/news", label: "Intel Feed" },
];

const navLinkClass =
  "text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:text-primary";

const Navbar = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { token, user, logout } = useAuth();

  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/80 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-3">
          <img src={logo} alt="ProxyDefence Logo" className="h-9 w-9 rounded-lg" />
          <div className="leading-tight">
            <p className="font-display text-lg tracking-tight text-foreground">ProxyDefence</p>
            <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
              Threat Intelligence
            </p>
          </div>
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <Link key={link.to} to={link.to} className={navLinkClass}>
              {link.label}
            </Link>
          ))}

          {token ? (
            <div className="flex items-center gap-3">
              <div className="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm">
                {user?.username}
              </div>
              <Link to="/dashboard">
                <Button variant="hero" size="sm">
                  Open Dashboard
                </Button>
              </Link>
              <Button variant="ghost" size="sm" onClick={logout}>
                Logout
              </Button>
              <div className="h-6 w-px bg-border" aria-hidden="true" />
              <ThemeToggle />
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link to="/auth">
                <Button variant="ghost" size="sm">Sign In</Button>
              </Link>
              <Link to="/auth">
                <Button variant="hero" size="sm">
                  <Shield className="mr-2 h-4 w-4" />
                  Analyst Access
                </Button>
              </Link>
              <div className="h-6 w-px bg-border" aria-hidden="true" />
              <ThemeToggle />
            </div>
          )}
        </div>

        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            onClick={() => setMobileMenuOpen((open) => !open)}
            aria-label="Toggle navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="border-t border-border bg-card/95 px-4 py-4 md:hidden">
          <div className="space-y-3">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className="block text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground"
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            {token ? (
              <>
                <Link
                  to="/dashboard"
                  className="block text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Dashboard
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                >
                  Logout
                </Button>
              </>
            ) : (
              <Link to="/auth" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="hero" size="sm" className="w-full">Sign In</Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;

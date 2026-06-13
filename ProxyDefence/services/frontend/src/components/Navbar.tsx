import { Menu, Shield } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import logo from "@/assets/logo.png";

const Navbar = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { token, user, logout } = useAuth();

  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/80 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-3">
          <img src={logo} alt="ProxyDefence Logo" className="h-10 w-10 rounded-xl" />
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">ProxyDefence</p>
            <p className="text-lg font-semibold">Threat Intelligence</p>
          </div>
        </Link>

        <div className="hidden items-center gap-6 md:flex">
          <Link to="/" className="text-sm font-medium hover:text-primary transition-colors">Home</Link>
          <Link to="/about" className="text-sm font-medium hover:text-primary transition-colors">About</Link>
          <Link to="/news" className="text-sm font-medium hover:text-primary transition-colors">Intel Feed</Link>
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
            </div>
          )}
        </div>

        <button className="md:hidden" onClick={() => setMobileMenuOpen((open) => !open)}>
          <Menu className="h-6 w-6" />
        </button>
      </div>

      {mobileMenuOpen && (
        <div className="border-t border-border bg-card/95 px-4 py-4 md:hidden">
          <div className="space-y-3">
            <Link to="/" className="block text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>Home</Link>
            <Link to="/about" className="block text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>About</Link>
            <Link to="/news" className="block text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>Intel Feed</Link>
            {token ? (
              <>
                <Link to="/dashboard" className="block text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>Dashboard</Link>
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

import { Link } from "react-router-dom";
import { Activity, Shield, Settings, LogOut, BarChart3, Cpu, User, Bell, Lock, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import logo from "@/assets/logo.png";

const Profile = () => {
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
            className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors"
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
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary/10 text-primary font-medium"
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
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Account Settings</h1>
            <p className="text-muted-foreground">Manage your profile and preferences</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Profile Section */}
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
                <div className="flex items-center gap-4 mb-6">
                  <User className="h-5 w-5 text-primary" />
                  <h3 className="text-lg font-semibold">Profile Information</h3>
                </div>
                
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="first-name">First Name</Label>
                      <Input id="first-name" defaultValue="John" className="mt-1" />
                    </div>
                    <div>
                      <Label htmlFor="last-name">Last Name</Label>
                      <Input id="last-name" defaultValue="Doe" className="mt-1" />
                    </div>
                  </div>
                  
                  <div>
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" defaultValue="john.doe@company.com" className="mt-1" />
                  </div>
                  
                  <div>
                    <Label htmlFor="organization">Organization</Label>
                    <Input id="organization" defaultValue="ProxyDefence Enterprise" className="mt-1" />
                  </div>
                  
                  <div>
                    <Label htmlFor="location">Location</Label>
                    <Input id="location" defaultValue="San Francisco, CA" className="mt-1" />
                  </div>

                  <Button variant="hero">Save Changes</Button>
                </div>
              </div>

              {/* Security Settings */}
              <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
                <div className="flex items-center gap-4 mb-6">
                  <Lock className="h-5 w-5 text-primary" />
                  <h3 className="text-lg font-semibold">Security</h3>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="current-password">Current Password</Label>
                    <Input id="current-password" type="password" className="mt-1" />
                  </div>
                  
                  <div>
                    <Label htmlFor="new-password">New Password</Label>
                    <Input id="new-password" type="password" className="mt-1" />
                  </div>
                  
                  <div>
                    <Label htmlFor="confirm-password">Confirm New Password</Label>
                    <Input id="confirm-password" type="password" className="mt-1" />
                  </div>

                  <Button variant="outline">Change Password</Button>
                </div>
              </div>

              {/* Notifications */}
              <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
                <div className="flex items-center gap-4 mb-6">
                  <Bell className="h-5 w-5 text-primary" />
                  <h3 className="text-lg font-semibold">Notifications</h3>
                </div>
                
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Critical Threat Alerts</p>
                      <p className="text-sm text-muted-foreground">
                        Get notified about critical threats
                      </p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Weekly Reports</p>
                      <p className="text-sm text-muted-foreground">
                        Receive weekly security summaries
                      </p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Simulation Results</p>
                      <p className="text-sm text-muted-foreground">
                        Alerts when simulations complete
                      </p>
                    </div>
                    <Switch />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">System Updates</p>
                      <p className="text-sm text-muted-foreground">
                        New features and improvements
                      </p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                </div>
              </div>
            </div>

            {/* Sidebar Stats */}
            <div className="space-y-6">
              <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
                <h4 className="font-semibold mb-4">Account Status</h4>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-muted-foreground">Plan</p>
                    <p className="text-lg font-bold">Enterprise</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Member Since</p>
                    <p className="text-lg font-bold">Jan 2024</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">API Usage</p>
                    <p className="text-lg font-bold">1.2M / 5M</p>
                  </div>
                </div>
                <Button variant="outline" className="w-full mt-4">
                  Upgrade Plan
                </Button>
              </div>

              <div className="rounded-lg border border-primary/30 bg-primary/5 p-6">
                <Globe className="h-8 w-8 text-primary mb-3" />
                <h4 className="font-semibold mb-2">Location Services</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Enable location-based threat detection for enhanced security.
                </p>
                <Button variant="outline" size="sm" className="w-full">
                  Configure
                </Button>
              </div>

              <div className="rounded-lg border border-accent/30 bg-accent/5 p-6">
                <Shield className="h-8 w-8 text-accent mb-3" />
                <h4 className="font-semibold mb-2">Two-Factor Auth</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Add an extra layer of security to your account.
                </p>
                <Button size="sm" className="w-full">
                  Enable 2FA
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Profile;
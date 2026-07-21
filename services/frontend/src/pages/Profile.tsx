import { useState } from "react";
import { Bell, Lock, Sparkles, User } from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/context/AuthContext";
import {
  updateProfile,
  updateNotificationPreferences,
  changePassword,
  toggleTierBeta,
  type NotificationPreferences,
} from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const DEFAULT_NOTIFICATIONS: NotificationPreferences = {
  critical_threat_alerts: true,
  weekly_reports: true,
  simulation_results: false,
  system_updates: true,
};

const Profile = () => {
  const { user, setUser } = useAuth();
  const { toast } = useToast();
  const [organization, setOrganization] = useState(user?.organization ?? "");
  const [location, setLocation] = useState(user?.location ?? "");
  const [saving, setSaving] = useState(false);

  const [notifications, setNotifications] = useState<NotificationPreferences>(
    user?.notification_preferences ?? DEFAULT_NOTIFICATIONS
  );
  const [savingNotifications, setSavingNotifications] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const [togglingTier, setTogglingTier] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateProfile({ organization: organization || null, location: location || null });
      setUser(updated);
      toast({ title: "Profile updated" });
    } catch (err) {
      console.error("Failed to update profile", err);
      toast({ title: "Failed to update profile", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleToggleNotification = async (key: keyof NotificationPreferences, value: boolean) => {
    const next = { ...notifications, [key]: value };
    setNotifications(next);
    setSavingNotifications(true);
    try {
      const updated = await updateNotificationPreferences(next);
      setUser(updated);
    } catch (err) {
      console.error("Failed to update notification preferences", err);
      setNotifications(notifications);
      toast({ title: "Failed to update notification preference", variant: "destructive" });
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword) {
      toast({ title: "Enter your current and new password", variant: "destructive" });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast({ title: "New password and confirmation do not match", variant: "destructive" });
      return;
    }
    if (newPassword.length < 8) {
      toast({ title: "New password must be at least 8 characters", variant: "destructive" });
      return;
    }
    setChangingPassword(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast({ title: "Password changed" });
    } catch (err: any) {
      toast({
        title: "Failed to change password",
        description: err?.response?.data?.detail ?? "Please check your current password and try again.",
        variant: "destructive",
      });
    } finally {
      setChangingPassword(false);
    }
  };

  const handleToggleTier = async () => {
    setTogglingTier(true);
    try {
      const updated = await toggleTierBeta();
      setUser(updated);
      toast({
        title: updated.tier === "premium" ? "Premium activated" : "Switched to Free tier",
      });
    } catch (err) {
      console.error("Failed to toggle tier", err);
      toast({ title: "Failed to update plan", variant: "destructive" });
    } finally {
      setTogglingTier(false);
    }
  };

  return (
    <AppShell
      title="Profile and access"
      subtitle="Manage analyst identity, alerting preferences, and operational access posture."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
            <div className="mb-6 flex items-center gap-4">
              <User className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold">Profile Information</h3>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="username">Username</Label>
                  <Input id="username" defaultValue={user?.username || "Analyst"} className="mt-1" />
                </div>
                <div>
                  <Label htmlFor="role">Role</Label>
                  <Input id="role" defaultValue={user?.role || "observer"} className="mt-1" />
                </div>
              </div>

              <div>
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" defaultValue={user?.email || "analyst@proxydefence.local"} className="mt-1" />
              </div>

              <div>
                <Label htmlFor="organization">Organization</Label>
                <Input
                  id="organization"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  placeholder="Not set"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Not set"
                  className="mt-1"
                />
              </div>

              <Button variant="hero" onClick={() => void handleSave()} disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
            <div className="mb-6 flex items-center gap-4">
              <Lock className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold">Security</h3>
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="current-password">Current Password</Label>
                <Input
                  id="current-password"
                  type="password"
                  className="mt-1"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="new-password">New Password</Label>
                <Input
                  id="new-password"
                  type="password"
                  className="mt-1"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="confirm-password">Confirm New Password</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  className="mt-1"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              <Button variant="outline" onClick={() => void handleChangePassword()} disabled={changingPassword}>
                {changingPassword ? "Changing..." : "Change Password"}
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
            <div className="mb-6 flex items-center gap-4">
              <Bell className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold">Notifications</h3>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Critical Threat Alerts</p>
                  <p className="text-sm text-muted-foreground">Get notified about critical threats</p>
                </div>
                <Switch
                  checked={notifications.critical_threat_alerts}
                  disabled={savingNotifications}
                  onCheckedChange={(v) => void handleToggleNotification("critical_threat_alerts", v)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Weekly Reports</p>
                  <p className="text-sm text-muted-foreground">Receive weekly security summaries</p>
                </div>
                <Switch
                  checked={notifications.weekly_reports}
                  disabled={savingNotifications}
                  onCheckedChange={(v) => void handleToggleNotification("weekly_reports", v)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Simulation Results</p>
                  <p className="text-sm text-muted-foreground">Alerts when simulations complete</p>
                </div>
                <Switch
                  checked={notifications.simulation_results}
                  disabled={savingNotifications}
                  onCheckedChange={(v) => void handleToggleNotification("simulation_results", v)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">System Updates</p>
                  <p className="text-sm text-muted-foreground">New features and improvements</p>
                </div>
                <Switch
                  checked={notifications.system_updates}
                  disabled={savingNotifications}
                  onCheckedChange={(v) => void handleToggleNotification("system_updates", v)}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-6 shadow-elevation">
            <h4 className="mb-4 font-semibold">Account Status</h4>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-muted-foreground">Role</p>
                <p className="text-lg font-bold capitalize">{user?.role ?? "Analyst"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Member Since</p>
                <p className="text-lg font-bold">
                  {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "Recently"}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-primary/30 bg-primary/5 p-6">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h4 className="font-semibold">Plan</h4>
            </div>
            <p className="mb-1 text-lg font-bold capitalize">{user?.tier ?? "free"}</p>
            <p className="mb-4 text-sm text-muted-foreground">
              {user?.tier === "premium"
                ? "Full access: Command Center response pipeline, custom scenario runs, SPR & procurement analysis."
                : "Free tier: live signal feed, corridor risk, article market impact, and read-only dashboards. Upgrade for the full response pipeline."}
            </p>
            <Button
              variant={user?.tier === "premium" ? "outline" : "hero"}
              size="sm"
              className="w-full"
              onClick={() => void handleToggleTier()}
              disabled={togglingTier}
            >
              {togglingTier
                ? "Updating..."
                : user?.tier === "premium"
                  ? "Downgrade to Free"
                  : "Try Premium (Beta, free during hackathon)"}
            </Button>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default Profile;

import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";

import {
  Alert,
  fetchAlerts,
} from "@/lib/api";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  Badge,
} from "@/components/ui/badge";

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAlerts();
  }, []);

  const loadAlerts = async () => {
    try {
      const data = await fetchAlerts();
      setAlerts(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell
      title="Alerts"
      subtitle="Monitor threat alerts and watchlist matches"
    >
      <div className="grid gap-4">

        {loading && (
          <Card>
            <CardContent className="p-6">
              Loading alerts...
            </CardContent>
          </Card>
        )}

        {!loading &&
          alerts.map((alert) => (
            <Card key={alert.id}>
              <CardHeader>
                <div className="flex items-center justify-between">

                  <CardTitle>
                    {alert.entity_text}
                  </CardTitle>

                  <Badge>
                    {alert.status}
                  </Badge>

                </div>
              </CardHeader>

              <CardContent>

                <div className="space-y-2">

                  <p>
                    {alert.message}
                  </p>

                  <p>
                    Risk Score:
                    {" "}
                    {alert.risk_score}
                  </p>

                  <p>
                    Alert Type:
                    {" "}
                    {alert.alert_type}
                  </p>

                  <p>
                    Event:
                    {" "}
                    {alert.event_id}
                  </p>

                </div>

              </CardContent>
            </Card>
          ))}

      </div>
    </AppShell>
  );
}
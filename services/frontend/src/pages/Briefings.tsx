import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

const Briefings = () => {
  const [events, setEvents] = useState<any[]>([]);
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBriefing();
  }, []);

  const loadBriefing = async () => {
    try {
      setLoading(true);

      const [eventsResponse, entitiesResponse] = await Promise.all([
        api.get("/events"),
        api.get("/analytics/entities"),
      ]);

      setEvents(eventsResponse.data || []);
      setEntities(entitiesResponse.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const topActor =
    entities.length > 0 ? entities[0].entity : "Unknown";

  return (
    <AppShell
      title="Intelligence Briefings"
      subtitle="Executive threat intelligence overview"
    >
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="text-lg">
            Loading intelligence briefing...
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* TOP METRICS */}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-3xl border border-border bg-card p-6">
              <p className="text-sm text-muted-foreground">
                Active Events
              </p>

              <p className="mt-2 text-4xl font-bold">
                {events.length}
              </p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <p className="text-sm text-muted-foreground">
                Tracked Entities
              </p>

              <p className="mt-2 text-4xl font-bold">
                {entities.length}
              </p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <p className="text-sm text-muted-foreground">
                Top Actor
              </p>

              <p className="mt-2 text-xl font-bold">
                {topActor}
              </p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <p className="text-sm text-muted-foreground">
                Monitoring Status
              </p>

              <p className="mt-2 text-xl font-bold text-green-400">
                ACTIVE
              </p>
            </div>
          </div>

          {/* EVENTS + ACTORS */}

          <div className="grid gap-6 xl:grid-cols-2">
            {/* EVENTS */}

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="mb-5 text-2xl font-bold">
                Active Events
              </h2>

              <div className="space-y-4">
                {events.slice(0, 5).map((event: any) => (
                  <div
                    key={event.id}
                    className="rounded-2xl border border-border bg-background p-4"
                  >
                    <div className="mb-2 font-semibold">
                      {event.title}
                    </div>

                    <div className="text-sm text-muted-foreground">
                      {event.summary
                        ? `${event.summary.slice(0, 180)}...`
                        : "No summary available"}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* THREAT ACTORS */}

            <div className="rounded-3xl border border-border bg-card p-6">
              <h2 className="mb-5 text-2xl font-bold">
                Top Threat Actors
              </h2>

              <div className="space-y-3">
                {entities.slice(0, 10).map(
                  (entity: any, index: number) => (
                    <div
                      key={entity.entity}
                      className="flex items-center justify-between rounded-2xl border border-border bg-background p-4"
                    >
                      <div>
                        <div className="font-semibold">
                          #{index + 1} {entity.entity}
                        </div>

                        <div className="text-xs text-muted-foreground">
                          {entity.type}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="font-bold">
                          {entity.mentions}
                        </div>

                        <div className="text-xs text-muted-foreground">
                          mentions
                        </div>
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>

          {/* EXECUTIVE ASSESSMENT */}

          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-5 text-2xl font-bold">
              Executive Assessment
            </h2>

            <div className="space-y-4 text-muted-foreground leading-7">
              <p>
                Intelligence monitoring currently tracks{" "}
                <strong>{events.length}</strong> active
                events and{" "}
                <strong>{entities.length}</strong> identified
                entities.
              </p>

              <p>
                The most prominent monitored actor is{" "}
                <strong>{topActor}</strong>, based on entity
                frequency across processed intelligence reports.
              </p>

              <p>
                Current reporting suggests continued geopolitical
                activity requiring analyst attention and ongoing
                monitoring of actor relationships, emerging
                events, and threat indicators.
              </p>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default Briefings;
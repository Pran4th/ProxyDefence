import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays } from "lucide-react";

import AppShell from "@/components/AppShell";
import { fetchEvents, type Event } from "@/lib/api";

const Events = () => {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  useEffect(() => {
    fetchEvents()
      .then((data) => setEvents(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell
      title="Event Explorer"
      subtitle="Investigate clustered geopolitical events and emerging intelligence signals."
    >
      {loading ? (
        <div className="rounded-2xl border border-border bg-card p-6">
          Loading events...
        </div>
      ) : (
        <div className="grid gap-4">
          {events.map((event) => (
            <button
              key={event.id}
              onClick={() => navigate(`/events/${event.id}`)}
              className="rounded-2xl border border-border bg-card p-5 text-left transition hover:border-primary"
            >
              <div className="flex items-center gap-3">
                <CalendarDays className="h-5 w-5 text-primary" />

                <div className="flex-1">
                  <h2 className="text-lg font-semibold">
                    {event.title}
                  </h2>

                  <p className="mt-2 text-sm text-muted-foreground">
                    {event.summary?.slice(0, 180)}...
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border px-3 py-1 text-xs">
                  {event.topic}
                </span>

                <span className="rounded-full border px-3 py-1 text-xs">
                  Risk: {event.risk_level}
                </span>

                <span className="rounded-full border px-3 py-1 text-xs">
                  Score: {Math.round(event.risk_score)}
                </span>

                <span className="rounded-full border px-3 py-1 text-xs">
                  Articles: {event.article_count}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </AppShell>
  );
};

export default Events;
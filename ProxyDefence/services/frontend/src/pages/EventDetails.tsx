import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import AppShell from "@/components/AppShell";

import {
  fetchEvent,
  fetchEventArticles,
  type EventDetails,
  type Article,
} from "@/lib/api";

const EventDetailsPage = () => {
  const { eventId } = useParams();

  const [event, setEvent] = useState<EventDetails | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!eventId) return;

    Promise.all([
      fetchEvent(Number(eventId)),
      fetchEventArticles(Number(eventId)),
    ])
      .then(([eventData, articleData]) => {
        setEvent(eventData);
        setArticles(articleData);
      })
      .finally(() => setLoading(false));
  }, [eventId]);

  return (
    <AppShell
      title={event?.title || "Event"}
      subtitle="Clustered intelligence event analysis."
    >
      {loading && (
        <div className="rounded-2xl border border-border bg-card p-6">
          Loading event...
        </div>
      )}

      {!loading && event && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Topic
              </p>

              <h3 className="text-xl font-semibold">
                {event.topic}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Risk Level
              </p>

              <h3 className="text-xl font-semibold">
                {event.risk_level}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Risk Score
              </p>

              <h3 className="text-xl font-semibold">
                {Math.round(event.risk_score)}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Articles
              </p>

              <h3 className="text-xl font-semibold">
                {event.article_count}
              </h3>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-3 text-xl font-semibold">
              Executive Summary
            </h2>

            <p className="text-muted-foreground">
              {event.summary}
            </p>
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-semibold">
              Top Entities
            </h2>

            <div className="flex flex-wrap gap-3">
              {event.entities?.map((entity) => (
                <div
                  key={`${entity.entity_text}-${entity.entity_type}`}
                  className="rounded-xl border border-border px-4 py-3"
                >
                  <div className="font-medium">
                    {entity.entity_text}
                  </div>

                  <div className="text-xs text-muted-foreground">
                    {entity.entity_type}
                  </div>

                  <div className="text-xs text-muted-foreground">
                    Mentions: {entity.mention_count}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-semibold">
              Related Articles
            </h2>

            <div className="space-y-3">
              {articles.map((article) => (
                <div
                  key={article.id}
                  className="rounded-xl border border-border p-4"
                >
                  <h3 className="font-medium">
                    {article.title}
                  </h3>

                  <p className="mt-2 text-sm text-muted-foreground">
                    Topic: {article.topic}
                  </p>

                  <p className="text-sm text-muted-foreground">
                    Risk: {article.risk_level}
                  </p>

                  <p className="text-sm text-muted-foreground">
                    Threat Score:{" "}
                    {Math.round(article.threat_score || 0)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
};

export default EventDetailsPage;
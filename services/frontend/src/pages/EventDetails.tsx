import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import AppShell from "@/components/AppShell";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  fetchEvent,
  type EventDetails,
  type Article,
} from "@/lib/api";

type EventArticle = Pick<Article, "id" | "title" | "topic" | "threat_score"> & {
  similarity_score?: number;
};

type EventDetailsPayload = EventDetails & {
  articles: EventArticle[];
};

const EventDetailsPage = () => {
  const { eventId } = useParams();

  const [event, setEvent] = useState<EventDetailsPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!eventId) return;

    fetchEvent(Number(eventId))
      .then((eventData) => setEvent(eventData as EventDetailsPayload))
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
              Event Summary
            </h2>

            <p className="text-muted-foreground">
              {event.summary}
            </p>
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-semibold">
              Related Entities
            </h2>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entity</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Mentions</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {event.entities?.map((entity) => (
                  <TableRow key={`${entity.entity_text}-${entity.entity_type}`}>
                    <TableCell className="font-medium">
                      {entity.entity_text}
                    </TableCell>
                    <TableCell>{entity.entity_type}</TableCell>
                    <TableCell>{entity.mention_count}</TableCell>
                    <TableCell>
                      {Math.round((entity.avg_confidence ?? 0) * 100)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-semibold">
              Related Articles
            </h2>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Topic</TableHead>
                  <TableHead>Threat Score</TableHead>
                  <TableHead>Similarity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {event.articles?.map((article) => (
                  <TableRow key={article.id}>
                    <TableCell className="font-medium">
                      {article.title}
                    </TableCell>
                    <TableCell>{article.topic}</TableCell>
                    <TableCell>
                      {Math.round(article.threat_score || 0)}
                    </TableCell>
                    <TableCell>
                      {Math.round((article.similarity_score ?? 0) * 100)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </AppShell>
  );
};

export default EventDetailsPage;

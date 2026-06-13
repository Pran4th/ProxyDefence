import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import AppShell from "@/components/AppShell";
import CytoscapeComponent from "react-cytoscapejs";
import {
  fetchEntityProfile,
  fetchEntityArticles,
  fetchEntityRelationships,
} from "@/lib/api";

const EntityDetails = () => {
  const { entityName } = useParams();

  const [profile, setProfile] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);
  const [relationships, setRelationships] = useState<any[]>([]);
  const graphElements = relationships.flatMap((r) => [
  {
    data: {
      id: r.source_entity,
      label: r.source_entity,
    },
  },
  {
    data: {
      id: r.target_entity,
      label: r.target_entity,
    },
  },
  {
    data: {
      source: r.source_entity,
      target: r.target_entity,
      label: r.relationship_type,
    },
  },
]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entityName) return;

    Promise.all([
      fetchEntityProfile(entityName),
      fetchEntityArticles(entityName),
      fetchEntityRelationships(entityName),
    ])
      .then(([profileData, articleData, relationshipData]) => {
        setProfile(profileData);
        setArticles(articleData);
        setRelationships(relationshipData);
      })
      .finally(() => setLoading(false));
  }, [entityName]);

  return (
    <AppShell
      title={entityName || "Entity"}
      subtitle="Intelligence profile and relationship analysis."
    >
      {loading && (
        <div className="rounded-2xl border border-border bg-card p-6">
          Loading...
        </div>
      )}

      {!loading && profile && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Entity Type
              </p>
              <h3 className="text-xl font-semibold">
                {profile.entity_type}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Mentions
              </p>
              <h3 className="text-xl font-semibold">
                {profile.mention_frequency}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Risk Trend
              </p>
              <h3 className="text-xl font-semibold">
                {profile.risk_trend}
              </h3>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">
                Relationships
              </p>
              <h3 className="text-xl font-semibold">
                {relationships.length}
              </h3>
            </div>
          </div>
          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
  <h2 className="mb-4 text-xl font-semibold">
    Relationship Network
  </h2>

  <div className="h-[500px]">
    <CytoscapeComponent
      elements={graphElements}
      style={{
        width: "100%",
        height: "500px",
      }}
      layout={{
        name: "cose",
      }}
      stylesheet={[
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 120,
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "curve-style": "bezier",
          },
        },
      ]}
    />
  </div>
</div>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-border bg-card p-5">
              <h2 className="text-xl font-semibold mb-4">
                Related Articles
              </h2>

              <div className="space-y-3">
                {articles.map((article) => (
                  <div
                    key={article.id}
                    className="rounded-xl border border-border p-4"
                  >
                    <p className="font-medium">
                      {article.title}
                    </p>

                    <p className="text-sm text-muted-foreground mt-2">
                      Topic: {article.topic}
                    </p>

                    <p className="text-sm text-muted-foreground">
                      Risk: {article.risk_level}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-5">
              <h2 className="text-xl font-semibold mb-4">
                Relationships
              </h2>

              <div className="space-y-3">
                {relationships.map((relationship, index) => (
                  <div
                    key={index}
                    className="rounded-xl border border-border p-4"
                  >
                    <p>
                      <strong>
                        {relationship.source_entity}
                      </strong>
                      {" → "}
                      <strong>
                        {relationship.target_entity}
                      </strong>
                    </p>

                    <p className="text-sm text-muted-foreground mt-2">
                      Type: {relationship.relationship_type}
                    </p>

                    <p className="text-sm text-muted-foreground">
                      Confidence:{" "}
                      {Math.round(
                        relationship.confidence * 100
                      )}
                      %
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
};

export default EntityDetails;
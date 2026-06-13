import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Globe2 } from "lucide-react";

import AppShell from "@/components/AppShell";
import {
  fetchEntities,
  type EntityInsight,
} from "@/lib/api";

const Entities = () => {
  const [entities, setEntities] = useState<EntityInsight[]>([]);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  useEffect(() => {
    fetchEntities()
      .then((data) => setEntities(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell
      title="Entity Explorer"
      subtitle="Explore actors, organizations, countries and intelligence entities."
    >
      <div className="grid gap-4">
        {loading && (
          <div className="rounded-2xl border border-border bg-card p-6">
            Loading entities...
          </div>
        )}

        {!loading &&
          entities.map((entity) => (
            <button
              key={`${entity.entity}-${entity.type}`}
              onClick={() =>
                navigate(`/entities/${encodeURIComponent(entity.entity)}`)
              }
              className="rounded-2xl border border-border bg-card p-5 text-left transition hover:border-primary"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Globe2 className="h-4 w-4 text-primary" />
                    <h3 className="font-semibold text-lg">
                      {entity.entity}
                    </h3>
                  </div>

                  <p className="text-sm text-muted-foreground mt-1">
                    {entity.type}
                  </p>
                </div>

                <div className="text-right">
                  <p className="font-semibold">
                    {entity.mentions}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    mentions
                  </p>
                </div>
              </div>
            </button>
          ))}
      </div>
    </AppShell>
  );
};

export default Entities;
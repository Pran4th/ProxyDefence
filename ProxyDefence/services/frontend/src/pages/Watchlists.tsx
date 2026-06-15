import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";

import {
  Watchlist,
  fetchWatchlists,
  createWatchlist,
  generateAlerts,
} from "@/lib/api";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { ShieldCheck, Plus } from "lucide-react";

export default function Watchlists() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    loadWatchlists();
  }, []);

  const loadWatchlists = async () => {
    try {
      const data = await fetchWatchlists();
      setWatchlists(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWatchlist = async () => {
    if (!name.trim()) return;

    try {
      await createWatchlist({
        name,
        description,
      });

      setName("");
      setDescription("");

      await loadWatchlists();
    } catch (error) {
      console.error(error);
    }
  };

  const handleGenerateAlerts = async () => {
    try {
      const result = await generateAlerts();

      alert(
        `Generated ${result.alerts_created} alerts`
      );
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <AppShell
      title="Watchlists"
      subtitle="Monitor entities, generate alerts and track intelligence targets"
    >
      <div className="space-y-6">

        <Card>
          <CardHeader>
            <CardTitle>
              Create Watchlist
            </CardTitle>
          </CardHeader>

          <CardContent>

            <div className="grid gap-4 md:grid-cols-3">

              <Input
                placeholder="Watchlist Name"
                value={name}
                onChange={(e) =>
                  setName(e.target.value)
                }
              />

              <Input
                placeholder="Description"
                value={description}
                onChange={(e) =>
                  setDescription(e.target.value)
                }
              />

              <Button
                onClick={handleCreateWatchlist}
              >
                <Plus className="mr-2 h-4 w-4" />
                Create
              </Button>

            </div>

            <Button
              className="mt-4"
              variant="outline"
              onClick={handleGenerateAlerts}
            >
              Generate Alerts
            </Button>

          </CardContent>
        </Card>

        {loading ? (
          <Card>
            <CardContent className="p-6">
              Loading watchlists...
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">

            {watchlists.map((watchlist) => (
              <Card key={watchlist.id}>

                <CardHeader>

                  <div className="flex items-center gap-3">

                    <ShieldCheck className="h-5 w-5 text-primary" />

                    <CardTitle>
                      {watchlist.name}
                    </CardTitle>

                  </div>

                </CardHeader>

                <CardContent>

                  <p className="text-sm text-muted-foreground">
                    {watchlist.description ||
                      "No description"}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">

                    {watchlist.entities?.length ? (
                      watchlist.entities.map(
                        (entity) => (
                          <span
                            key={entity}
                            className="rounded-full border px-3 py-1 text-sm"
                          >
                            {entity}
                          </span>
                        )
                      )
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        No entities
                      </span>
                    )}

                  </div>

                  <div className="mt-4 text-xs text-muted-foreground">
                    Created:
                    {" "}
                    {new Date(
                      watchlist.created_at
                    ).toLocaleString()}
                  </div>

                </CardContent>

              </Card>
            ))}

          </div>
        )}

      </div>
    </AppShell>
  );
}
import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";

import {
  fetchCases,
  createCase,
  generateCaseReport,
} from "@/lib/api";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  Shield,
  Plus,
  FileText,
} from "lucide-react";

export default function Cases() {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const loadCases = async () => {
    try {
      const data = await fetchCases();
      setCases(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleCreateCase = async () => {
    try {
      await createCase({
        title,
        description,
        priority: "high",
      });

      setTitle("");
      setDescription("");

      await loadCases();
    } catch (err) {
      console.error(err);
    }
  };

  const handleGenerateReport = async (
    caseId: number
  ) => {
    try {
      await generateCaseReport(caseId);

      alert("Report Generated");
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <AppShell
      title="Cases"
      subtitle="Investigation workspaces and intelligence operations"
    >
      <div className="space-y-6">

        <Card>
          <CardHeader>
            <CardTitle>
              Create Investigation
            </CardTitle>
          </CardHeader>

          <CardContent>

            <div className="grid gap-4 md:grid-cols-3">

              <Input
                placeholder="Case Title"
                value={title}
                onChange={(e) =>
                  setTitle(e.target.value)
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
                onClick={handleCreateCase}
              >
                <Plus className="mr-2 h-4 w-4" />
                Create Case
              </Button>

            </div>

          </CardContent>
        </Card>

        {loading ? (
          <Card>
            <CardContent className="p-6">
              Loading...
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">

            {cases.map((item) => (
              <Card key={item.id}>

                <CardHeader>

                  <div className="flex items-center gap-3">

                    <Shield className="h-5 w-5 text-primary" />

                    <CardTitle>
                      {item.title}
                    </CardTitle>

                  </div>

                </CardHeader>

                <CardContent>

                  <p className="text-muted-foreground">
                    {item.description}
                  </p>

                  <div className="mt-4 flex gap-2 flex-wrap">

                    <span className="rounded-full border px-3 py-1">
                      {item.status}
                    </span>

                    <span className="rounded-full border px-3 py-1">
                      {item.priority}
                    </span>

                    <span className="rounded-full border px-3 py-1">
                      Notes: {item.notes_count}
                    </span>

                    <span className="rounded-full border px-3 py-1">
                      Items: {item.item_count}
                    </span>

                  </div>

                  <Button
                    className="mt-5 w-full"
                    onClick={() =>
                      handleGenerateReport(item.id)
                    }
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    Generate Intelligence Brief
                  </Button>

                </CardContent>

              </Card>
            ))}

          </div>
        )}

      </div>
    </AppShell>
  );
}
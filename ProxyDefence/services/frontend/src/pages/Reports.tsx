import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";

import {
  fetchReports,
} from "@/lib/api";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  FileText,
} from "lucide-react";

export default function Reports() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      const data = await fetchReports();
      setReports(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell
      title="Reports"
      subtitle="Generated intelligence assessments and executive briefings"
    >
      <div className="space-y-5">

        {loading ? (
          <Card>
            <CardContent className="p-6">
              Loading reports...
            </CardContent>
          </Card>
        ) : (
          reports.map((report) => (
            <Card key={report.id}>

              <CardHeader>

                <div className="flex items-center gap-3">

                  <FileText className="h-5 w-5 text-primary" />

                  <CardTitle>
                    {report.title}
                  </CardTitle>

                </div>

              </CardHeader>

              <CardContent>

                <p className="text-sm text-muted-foreground">
                  {report.executive_summary}
                </p>

                <div className="mt-5">

                  <h4 className="font-semibold">
                    Threat Assessment
                  </h4>

                  <p className="mt-2 text-muted-foreground">
                    {report.threat_assessment}
                  </p>

                </div>

                <div className="mt-5">

                  <h4 className="font-semibold">
                    Confidence
                  </h4>

                  <p className="mt-2">
                    {report.confidence_score}
                  </p>

                </div>

                <div className="mt-5 text-xs text-muted-foreground">
                  Created:
                  {" "}
                  {new Date(
                    report.created_at
                  ).toLocaleString()}
                </div>

              </CardContent>

            </Card>
          ))
        )}

      </div>
    </AppShell>
  );
}
import { useState } from "react";
import { Link } from "react-router-dom";

import AppShell from "@/components/AppShell";
import { searchArticles } from "@/lib/api";

const Search = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);

    try {
      const response = await searchArticles(query);

      setResults(response.results);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell
      title="Intelligence Search"
      subtitle="Search geopolitical events, actors, relationships and intelligence signals."
    >
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search Iran, Russia, Ukraine..."
            className="flex-1 rounded-xl border border-border bg-background px-4 py-3"
          />

          <button
            onClick={handleSearch}
            className="rounded-xl bg-primary px-6 py-3 text-primary-foreground"
          >
            Search
          </button>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {loading && (
          <div className="rounded-xl border border-border bg-card p-5">
            Searching...
          </div>
        )}

        {results.map((article) => (
          <Link
            key={article.id}
            to={`/article/${article.id}`}
            className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
          >
            <h3 className="font-semibold text-lg">
              {article.title}
            </h3>

            <p className="mt-2 text-sm text-muted-foreground">
              {article.summary ||
                article.content?.slice(0, 250)}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full border px-3 py-1 text-xs">
                {article.topic}
              </span>

              <span className="rounded-full border px-3 py-1 text-xs">
                Risk: {article.risk_level}
              </span>

              <span className="rounded-full border px-3 py-1 text-xs">
                Threat: {Math.round(
                  article.threat_score || 0
                )}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </AppShell>
  );
};

export default Search;
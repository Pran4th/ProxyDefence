import { useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Search as SearchIcon, Loader2, X } from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { searchArticles, type Article } from "@/lib/api";
import { ThreatBadge } from "@/lib/riskFormat";

const TOPICS = ["war", "diplomacy", "economics", "cyber", "general"];
const RISK_LEVELS = ["low", "medium", "high", "critical"];

const riskBadgeClass: Record<string, string> = {
  low: "border-success/30 bg-success/10 text-success",
  medium: "border-warning/30 bg-warning/10 text-warning",
  high: "border-accent/30 bg-accent/10 text-accent",
  critical: "border-destructive/30 bg-destructive/10 text-destructive",
};

type ResultArticle = Article & { _highlight?: { title?: string[]; summary?: string[] } };

/** Renders ES highlight markup (`<mark>...</mark>`) as React nodes without dangerouslySetInnerHTML. */
function Highlighted({ text }: { text: string }) {
  const parts = text.split(/(<mark>.*?<\/mark>)/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^<mark>(.*)<\/mark>$/);
        return match ? (
          <mark key={i} className="rounded bg-primary/25 text-foreground">
            {match[1]}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </>
  );
}

const Search = () => {
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState<string>("");
  const [riskLevel, setRiskLevel] = useState<string>("");
  const [results, setResults] = useState<ResultArticle[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const response = await searchArticles(query, {
        topic: topic || undefined,
        risk_level: riskLevel || undefined,
      });
      setResults(response.results as ResultArticle[]);
      setTotalResults(response.total_results);
    } catch (err) {
      setError("Search failed. Please try again.");
      setResults([]);
      setTotalResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSearch();
  };

  const clearFilters = () => {
    setTopic("");
    setRiskLevel("");
  };

  return (
    <AppShell
      title="Intelligence Search"
      subtitle="Fast keyword lookup across articles, entities, and signals. For a synthesized answer to a broader question, try Copilot instead."
    >
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search Iran, Russia, Ukraine..."
            className="flex-1"
            autoFocus
          />
          <Button onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
            <span className="ml-2">Search</span>
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Select value={topic} onValueChange={setTopic}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Any topic" />
            </SelectTrigger>
            <SelectContent>
              {TOPICS.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={riskLevel} onValueChange={setRiskLevel}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Any risk level" />
            </SelectTrigger>
            <SelectContent>
              {RISK_LEVELS.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {(topic || riskLevel) && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X className="mr-1 h-3 w-3" /> Clear filters
            </Button>
          )}
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {loading && (
          <div className="space-y-4">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">
            {error}
          </div>
        )}

        {!loading && !error && searched && totalResults !== null && (
          <p className="text-sm text-muted-foreground">
            {totalResults} result{totalResults === 1 ? "" : "s"} for "{query}"
          </p>
        )}

        {!loading && !error && searched && results.length === 0 && (
          <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
            No articles matched your search. Try a different query or clear the filters.
          </div>
        )}

        {!loading &&
          results.map((article) => (
            <Link
              key={article.article_id}
              to={`/article/${article.article_id}`}
              className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/50"
            >
              <h3 className="font-semibold text-lg">
                {article._highlight?.title?.[0] ? (
                  <Highlighted text={article._highlight.title[0]} />
                ) : (
                  article.title
                )}
              </h3>

              <p className="mt-2 text-sm text-muted-foreground">
                {article._highlight?.summary?.[0] ? (
                  <Highlighted text={article._highlight.summary[0]} />
                ) : (
                  article.summary || article.content?.slice(0, 250)
                )}
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {article.topic && (
                  <span className="rounded-full border px-3 py-1 text-xs">{article.topic}</span>
                )}
                {article.risk_level && (
                  <span
                    className={`rounded-full border px-3 py-1 text-xs ${riskBadgeClass[article.risk_level] ?? ""}`}
                  >
                    Risk: {article.risk_level}
                  </span>
                )}
                <ThreatBadge score={article.threat_score} />
              </div>
            </Link>
          ))}
      </div>
    </AppShell>
  );
};

export default Search;

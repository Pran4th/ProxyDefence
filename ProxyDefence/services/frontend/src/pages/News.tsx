import { useEffect, useMemo, useState } from "react";
import { Search, ShieldAlert, SlidersHorizontal } from "lucide-react";

import Navbar from "@/components/Navbar";
import NewsCard from "@/components/NewsCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchArticles, searchArticles, type Article } from "@/lib/api";

const News = () => {
  const [selectedFilter, setSelectedFilter] = useState<string>("all");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [newsItems, setNewsItems] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadNews = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchArticles({ limit: 40 });
        setNewsItems(data);
      } catch (loadError) {
        console.error("Failed to fetch news:", loadError);
        setError("Unable to load the intelligence feed right now.");
      } finally {
        setLoading(false);
      }
    };

    void loadNews();
  }, []);

  const getSeverity = (article: Article): "low" | "medium" | "high" | "critical" => {
    if (article.risk_level === "critical") return "critical";
    if (article.risk_level === "high") return "high";
    if (article.sentiment?.toLowerCase() === "positive") return "low";
    return "medium";
  };

  const topics = useMemo(() => {
    const values = new Set(
      newsItems
        .map((item) => item.topic)
        .filter((topic): topic is string => Boolean(topic)),
    );
    return ["all", ...Array.from(values)];
  }, [newsItems]);

  const filteredNews = useMemo(
    () =>
      newsItems.filter((item) => {
        const severity = getSeverity(item);
        const severityMatch = selectedFilter === "all" || severity === selectedFilter;
        const topicMatch = topicFilter === "all" || item.topic === topicFilter;
        const text = `${item.title} ${item.summary || item.content} ${item.source}`.toLowerCase();
        const queryMatch = !searchTerm || text.includes(searchTerm.toLowerCase());
        return severityMatch && topicMatch && queryMatch;
      }),
    [newsItems, searchTerm, selectedFilter, topicFilter],
  );

  const handleSearch = async () => {
    if (!searchTerm.trim()) {
      const data = await fetchArticles({ limit: 40 });
      setNewsItems(data);
      return;
    }

    try {
      setSearching(true);
      setError(null);
      const response = await searchArticles(searchTerm.trim());
      setNewsItems(response.results);
    } catch (searchError) {
      console.error("Search failed:", searchError);
      setError("Search is temporarily unavailable.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="pt-24 pb-20">
        <div className="container mx-auto px-4">
          <div className="mb-12 max-w-4xl text-center animate-fade-in mx-auto">
            <h1 className="mb-4 bg-gradient-primary bg-clip-text text-5xl font-bold text-transparent">
              Threat Intelligence Feed
            </h1>
            <p className="text-xl text-muted-foreground">
              Browse live reporting enriched with summaries, topic labels, and geopolitical risk scoring
            </p>
          </div>

          <div className="mb-8 rounded-[1.5rem] border border-border bg-card p-5 shadow-elevation">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-1 items-center gap-3">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        void handleSearch();
                      }
                    }}
                    className="pl-10"
                    placeholder="Search articles, actors, or topics"
                  />
                </div>
                <Button onClick={() => void handleSearch()} disabled={searching}>
                  {searching ? "Searching..." : "Search"}
                </Button>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ShieldAlert className="h-4 w-4 text-primary" />
                {filteredNews.length} intelligence reports in view
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <SlidersHorizontal className="h-4 w-4" />
                Filters
              </div>
              <Button
                variant={selectedFilter === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("all")}
              >
                All News
              </Button>
              <Button
                variant={selectedFilter === "critical" ? "destructive" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("critical")}
              >
                Critical
              </Button>
              <Button
                variant={selectedFilter === "high" ? "secondary" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("high")}
              >
                High
              </Button>
              <Button
                variant={selectedFilter === "medium" ? "secondary" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("medium")}
              >
                Medium
              </Button>
              <Button
                variant={selectedFilter === "low" ? "secondary" : "outline"}
                size="sm"
                onClick={() => setSelectedFilter("low")}
              >
                Low
              </Button>
              {topics.map((topic) => (
                <Button
                  key={topic}
                  variant={topicFilter === topic ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => setTopicFilter(topic)}
                  className="capitalize"
                >
                  {topic}
                </Button>
              ))}
            </div>
          </div>

          <div className="mb-12 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {loading ? (
              <div className="col-span-2 py-10 text-center text-muted-foreground">
                <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
                Loading intelligence feed...
              </div>
            ) : error ? (
              <div className="col-span-2 rounded-[1.5rem] border border-destructive/30 bg-destructive/5 p-6 text-center">
                <p className="text-lg font-semibold text-destructive">Feed temporarily unavailable</p>
                <p className="mt-2 text-sm text-muted-foreground">{error}</p>
              </div>
            ) : filteredNews.length > 0 ? (
              filteredNews.map((news) => (
                <NewsCard
                  key={news.id}
                  title={news.title}
                  description={news.summary || news.content}
                  timestamp={new Date(news.published_at).toLocaleString()}
                  severity={getSeverity(news)}
                  source={`${news.source} · ${news.topic || "general"} · threat ${Math.round(news.threat_score || 0)}`}
                />
              ))
            ) : (
              <div className="col-span-2 rounded-lg border bg-muted/10 py-12 text-center">
                <h3 className="text-lg font-semibold">No Reports Found</h3>
                <p className="text-muted-foreground">Try adjusting your filters or search terms.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default News;

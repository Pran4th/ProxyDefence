from statistics import mean

from research.leaderboard.board import RankingEntry


class RankingEngine:
    async def rank(self, entries: list[RankingEntry], metric: str,
                   ascending: bool = False) -> list[RankingEntry]:
        sorted_entries = sorted(
            entries,
            key=lambda e: getattr(e, "primary_score" if metric == e.primary_metric else "secondary_score", 0.0),
            reverse=not ascending,
        )
        return sorted_entries

    async def rank_multi_metric(
        self,
        entries: list[RankingEntry],
        metrics: list[tuple[str, float, bool]],
    ) -> list[tuple[RankingEntry, float]]:
        scored: list[tuple[RankingEntry, float]] = []
        for entry in entries:
            composite = 0.0
            for metric_name, weight, ascending in metrics:
                score = getattr(entry, "primary_score" if metric_name == entry.primary_metric else "secondary_score", 0.0)
                if not ascending:
                    composite += weight * score
                else:
                    composite += weight * (1.0 / (score + 1e-10))
            scored.append((entry, composite))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def compute_ranks(self, scores: list[float]) -> list[int]:
        indexed = [(i, s) for i, s in enumerate(scores)]
        indexed.sort(key=lambda x: x[1], reverse=True)
        ranks = [0] * len(scores)
        current_rank = 1
        i = 0
        while i < len(indexed):
            tied_group = [indexed[i][0]]
            j = i + 1
            while j < len(indexed) and indexed[j][1] == indexed[i][1]:
                tied_group.append(indexed[j][0])
                j += 1
            for idx in tied_group:
                ranks[idx] = current_rank
            current_rank += len(tied_group)
            i = j
        return ranks

    async def get_percentile(self, entry: RankingEntry, entries: list[RankingEntry],
                             metric: str) -> float:
        key = "primary_score" if metric == entry.primary_metric else "secondary_score"
        entry_score = getattr(entry, key, 0.0)
        if not entries:
            return 100.0
        scores = [getattr(e, key, 0.0) for e in entries]
        count_below = sum(1 for s in scores if s < entry_score)
        return (count_below / len(scores)) * 100.0

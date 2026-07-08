import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RankingEntry:
    model_name: str
    model_version: int
    model_type: str
    experiment_name: str
    run_id: str
    primary_metric: str
    primary_score: float
    secondary_metric: str
    secondary_score: float
    training_time_seconds: float
    inference_latency_ms: float | None = None
    memory_mb: float | None = None
    model_size_kb: float | None = None
    dataset_name: str = ""
    dataset_version: int = 1
    feature_version: int = 1
    params: dict = field(default_factory=dict)
    created_at: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if isinstance(self.params, str):
            self.params = json.loads(self.params)


class LeaderboardStorage:
    def __init__(self):
        self._entries: dict[str, RankingEntry] = {}
        self._sorted_cache: dict[str, list[RankingEntry]] = {}

    @property
    def entries(self) -> dict[str, RankingEntry]:
        return self._entries

    def add(self, entry_id: str, entry: RankingEntry):
        self._entries[entry_id] = entry
        self._sorted_cache.clear()

    def get(self, entry_id: str) -> RankingEntry | None:
        return self._entries.get(entry_id)

    def remove(self, entry_id: str):
        self._entries.pop(entry_id, None)
        self._sorted_cache.clear()

    def list_all(self) -> list[RankingEntry]:
        return list(self._entries.values())


class Leaderboard:
    def __init__(self):
        self._storage = LeaderboardStorage()

    async def add_entry(self, entry: RankingEntry, pool=None) -> str:
        entry_id = f"{entry.model_name}_v{entry.model_version}_{entry.run_id}"
        self._storage.add(entry_id, entry)
        if pool is not None:
            try:
                await pool.execute(
                    "INSERT INTO ml.leaderboard (model_name, model_version, model_type, "
                    "experiment_name, run_id, primary_metric, primary_score, "
                    "secondary_metric, secondary_score, training_time_seconds, "
                    "inference_latency_ms, memory_mb, model_size_kb, "
                    "dataset_name, dataset_version, feature_version, params, tags) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
                    "$14, $15, $16, $17, $18) "
                    "ON CONFLICT (model_name, model_version, run_id) DO UPDATE SET "
                    "primary_score = EXCLUDED.primary_score, "
                    "secondary_score = EXCLUDED.secondary_score",
                    entry.model_name, entry.model_version, entry.model_type,
                    entry.experiment_name, entry.run_id,
                    entry.primary_metric, entry.primary_score,
                    entry.secondary_metric, entry.secondary_score,
                    entry.training_time_seconds,
                    entry.inference_latency_ms, entry.memory_mb, entry.model_size_kb,
                    entry.dataset_name, entry.dataset_version, entry.feature_version,
                    json.dumps(entry.params), entry.tags,
                )
            except Exception as exc:
                logger.warning("failed to persist leaderboard entry to db: %s", exc)
        logger.info("leaderboard entry added", entry_id=entry_id, model=entry.model_name, score=entry.primary_score)
        return entry_id

    async def get_rankings(self, metric: str | None = None, model_type: str | None = None,
                           limit: int = 20, offset: int = 0, pool=None) -> list[RankingEntry]:
        entries = self._storage.list_all()
        if pool is not None:
            try:
                rows = await pool.fetch(
                    "SELECT * FROM ml.leaderboard "
                    "WHERE ($1::text IS NULL OR primary_metric = $1) "
                    "AND ($2::text IS NULL OR model_type = $2) "
                    "ORDER BY primary_score DESC LIMIT $3 OFFSET $4",
                    metric, model_type, limit, offset,
                )
                db_entries = []
                for row in rows:
                    db_entries.append(RankingEntry(
                        model_name=row["model_name"],
                        model_version=row["model_version"],
                        model_type=row["model_type"],
                        experiment_name=row["experiment_name"],
                        run_id=row["run_id"],
                        primary_metric=row["primary_metric"],
                        primary_score=float(row["primary_score"]),
                        secondary_metric=row["secondary_metric"],
                        secondary_score=float(row["secondary_score"]),
                        training_time_seconds=float(row["training_time_seconds"]),
                        inference_latency_ms=float(row["inference_latency_ms"]) if row["inference_latency_ms"] else None,
                        memory_mb=float(row["memory_mb"]) if row["memory_mb"] else None,
                        model_size_kb=float(row["model_size_kb"]) if row["model_size_kb"] else None,
                        dataset_name=row["dataset_name"],
                        dataset_version=row["dataset_version"],
                        feature_version=row["feature_version"],
                        params=row["params"] if isinstance(row["params"], dict) else {},
                        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                        tags=row["tags"] or [],
                    ))
                return db_entries
            except Exception as exc:
                logger.warning("failed to fetch from db, using memory: %s", exc)
        filtered = [e for e in entries if (metric is None or e.primary_metric == metric)
                    and (model_type is None or e.model_type == model_type)]
        metric_key = metric or "primary_score"
        filtered.sort(key=lambda e: getattr(e, "primary_score" if metric_key == e.primary_metric else "secondary_score", 0.0), reverse=True)
        return filtered[offset:offset + limit] if limit > 0 else filtered[offset:]

    async def get_top_n(self, metric: str = "f1", n: int = 5,
                        model_type: str | None = None, pool=None) -> list[RankingEntry]:
        return await self.get_rankings(metric=metric, model_type=model_type, limit=n, offset=0, pool=pool)

    async def get_model_history(self, model_name: str, pool=None) -> list[RankingEntry]:
        entries = self._storage.list_all()
        if pool is not None:
            try:
                rows = await pool.fetch(
                    "SELECT * FROM ml.leaderboard WHERE model_name = $1 ORDER BY model_version DESC",
                    model_name,
                )
                if rows:
                    db_entries = []
                    for row in rows:
                        db_entries.append(RankingEntry(
                            model_name=row["model_name"],
                            model_version=row["model_version"],
                            model_type=row["model_type"],
                            experiment_name=row["experiment_name"],
                            run_id=row["run_id"],
                            primary_metric=row["primary_metric"],
                            primary_score=float(row["primary_score"]),
                            secondary_metric=row["secondary_metric"],
                            secondary_score=float(row["secondary_score"]),
                            training_time_seconds=float(row["training_time_seconds"]),
                            inference_latency_ms=float(row["inference_latency_ms"]) if row["inference_latency_ms"] else None,
                            memory_mb=float(row["memory_mb"]) if row["memory_mb"] else None,
                            model_size_kb=float(row["model_size_kb"]) if row["model_size_kb"] else None,
                            dataset_name=row["dataset_name"],
                            dataset_version=row["dataset_version"],
                            feature_version=row["feature_version"],
                            params=row["params"] if isinstance(row["params"], dict) else {},
                            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                            tags=row["tags"] or [],
                        ))
                    return db_entries
            except Exception as exc:
                logger.warning("failed to fetch model history from db: %s", exc)
        return [e for e in entries if e.model_name == model_name]

    async def compare_entries(self, entry_ids: list[str]) -> dict:
        entries = []
        for eid in entry_ids:
            entry = self._storage.get(eid)
            if entry:
                entries.append(asdict(entry))
        comparison = {
            "entry_ids": entry_ids,
            "count": len(entries),
            "entries": entries,
            "comparison": {},
        }
        if len(entries) >= 2:
            metrics_keys = ["primary_score", "secondary_score", "training_time_seconds",
                            "inference_latency_ms", "memory_mb", "model_size_kb"]
            for key in metrics_keys:
                vals = [e.get(key) for e in entries if e.get(key) is not None]
                if vals:
                    comparison["comparison"][key] = {
                        "min": min(vals),
                        "max": max(vals),
                        "mean": sum(vals) / len(vals),
                        "values": {e["run_id"]: e.get(key) for e in entries},
                    }
        return comparison

    async def refresh_from_db(self, pool=None):
        if pool is None:
            logger.warning("no pool provided, skipping refresh")
            return
        try:
            rows = await pool.fetch("SELECT * FROM ml.leaderboard ORDER BY primary_score DESC")
            self._storage = LeaderboardStorage()
            for row in rows:
                entry = RankingEntry(
                    model_name=row["model_name"],
                    model_version=row["model_version"],
                    model_type=row["model_type"],
                    experiment_name=row["experiment_name"],
                    run_id=row["run_id"],
                    primary_metric=row["primary_metric"],
                    primary_score=float(row["primary_score"]),
                    secondary_metric=row["secondary_metric"],
                    secondary_score=float(row["secondary_score"]),
                    training_time_seconds=float(row["training_time_seconds"]),
                    inference_latency_ms=float(row["inference_latency_ms"]) if row["inference_latency_ms"] else None,
                    memory_mb=float(row["memory_mb"]) if row["memory_mb"] else None,
                    model_size_kb=float(row["model_size_kb"]) if row["model_size_kb"] else None,
                    dataset_name=row["dataset_name"],
                    dataset_version=row["dataset_version"],
                    feature_version=row["feature_version"],
                    params=row["params"] if isinstance(row["params"], dict) else {},
                    created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                    tags=row["tags"] or [],
                )
                eid = f"{entry.model_name}_v{entry.model_version}_{entry.run_id}"
                self._storage.add(eid, entry)
            logger.info("leaderboard refreshed from db with %d entries", len(self._storage.list_all()))
        except Exception as exc:
            logger.error("failed to refresh leaderboard from db: %s", exc)

    async def to_dataframe(self) -> pd.DataFrame:
        entries = self._storage.list_all()
        if not entries:
            return pd.DataFrame()
        rows = [asdict(e) for e in entries]
        return pd.DataFrame(rows)

    async def to_markdown(self, n: int = 10, metric: str = "f1") -> str:
        entries = await self.get_top_n(metric=metric, n=n)
        if not entries:
            return f"# Leaderboard (top {n} by {metric})\n\n*No entries.*\n"
        lines = [f"# Leaderboard (top {n} by {metric})\n"]
        lines.append(f"| Rank | Model | Version | Primary ({metric}) | Secondary | Dataset | Latency (ms) |")
        lines.append("|------|-------|---------|-------------------|-----------|---------|--------------|")
        for i, e in enumerate(entries, 1):
            lines.append(
                f"| {i} | {e.model_name} | v{e.model_version} | {e.primary_score:.4f} | "
                f"{e.secondary_score:.4f} | {e.dataset_name} | "
                f"{e.inference_latency_ms if e.inference_latency_ms is not None else 'N/A'} |"
            )
        return "\n".join(lines)

    async def to_json(self, n: int = 10, metric: str = "f1") -> str:
        entries = await self.get_top_n(metric=metric, n=n)
        data = {
            "metric": metric,
            "count": len(entries),
            "entries": [asdict(e) for e in entries],
        }
        return json.dumps(data, indent=2, default=str)

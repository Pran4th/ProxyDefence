import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from research.leaderboard.board import Leaderboard, LeaderboardStorage, RankingEntry
from research.leaderboard.ranking import RankingEngine


class TestRankingEntry:
    def test_dataclass_fields(self):
        entry = RankingEntry(
            model_name="model_a",
            model_version=1,
            model_type="xgboost",
            experiment_name="exp1",
            run_id="run1",
            primary_metric="f1",
            primary_score=0.95,
            secondary_metric="accuracy",
            secondary_score=0.94,
            training_time_seconds=10.5,
        )
        assert entry.model_name == "model_a"
        assert entry.inference_latency_ms is None
        assert entry.memory_mb is None
        assert entry.dataset_name == ""
        assert entry.params == {}
        assert entry.tags == []

    def test_dataclass_all_fields(self):
        entry = RankingEntry(
            model_name="a", model_version=1, model_type="rf",
            experiment_name="e1", run_id="r1",
            primary_metric="f1", primary_score=0.9,
            secondary_metric="acc", secondary_score=0.88,
            training_time_seconds=5.0,
            inference_latency_ms=2.5, memory_mb=128.0, model_size_kb=50.0,
            dataset_name="data", dataset_version=2, feature_version=3,
            params={"lr": 0.01}, created_at="2024-01-01T00:00:00",
            tags=["production"],
        )
        assert entry.inference_latency_ms == 2.5
        assert entry.dataset_version == 2
        assert entry.tags == ["production"]

    def test_post_init_default_created_at(self):
        entry = RankingEntry(
            model_name="a", model_version=1, model_type="rf",
            experiment_name="e1", run_id="r1",
            primary_metric="f1", primary_score=0.9,
            secondary_metric="acc", secondary_score=0.88,
            training_time_seconds=1.0,
        )
        assert entry.created_at != ""

    def test_post_init_parses_json_params(self):
        entry = RankingEntry(
            model_name="a", model_version=1, model_type="rf",
            experiment_name="e1", run_id="r1",
            primary_metric="f1", primary_score=0.9,
            secondary_metric="acc", secondary_score=0.88,
            training_time_seconds=1.0,
            params='{"lr": 0.01}',
        )
        assert entry.params == {"lr": 0.01}


class TestLeaderboardStorage:
    def test_add_and_get(self):
        storage = LeaderboardStorage()
        entry = RankingEntry(
            model_name="a", model_version=1, model_type="rf",
            experiment_name="e1", run_id="r1",
            primary_metric="f1", primary_score=0.9,
            secondary_metric="acc", secondary_score=0.88,
            training_time_seconds=1.0,
        )
        storage.add("id1", entry)
        assert storage.get("id1") is entry
        assert storage.get("nonexistent") is None

    def test_remove(self):
        storage = LeaderboardStorage()
        entry = MagicMock(spec=RankingEntry)
        storage.add("id1", entry)
        storage.remove("id1")
        assert storage.get("id1") is None

    def test_remove_nonexistent(self):
        storage = LeaderboardStorage()
        storage.remove("nonexistent")

    def test_list_all(self):
        storage = LeaderboardStorage()
        assert storage.list_all() == []
        storage.add("id1", MagicMock(spec=RankingEntry))
        assert len(storage.list_all()) == 1

    @property
    def test_entries_property(self):
        storage = LeaderboardStorage()
        assert storage.entries == {}

    def test_add_clears_cache(self):
        storage = LeaderboardStorage()
        storage._sorted_cache["test"] = ["data"]
        storage.add("id", MagicMock(spec=RankingEntry))
        assert storage._sorted_cache == {}


class TestLeaderboard:
    @pytest.mark.asyncio
    async def test_add_entry(self):
        lb = Leaderboard()
        entry = RankingEntry(
            model_name="m1", model_version=1, model_type="rf",
            experiment_name="e1", run_id="r1",
            primary_metric="f1", primary_score=0.9,
            secondary_metric="acc", secondary_score=0.88,
            training_time_seconds=1.0,
        )
        eid = await lb.add_entry(entry)
        assert eid == "m1_v1_r1"

    @pytest.mark.asyncio
    async def test_get_rankings_empty(self):
        lb = Leaderboard()
        rankings = await lb.get_rankings()
        assert rankings == []

    @pytest.mark.asyncio
    async def test_get_rankings_with_entries(self):
        lb = Leaderboard()
        e1 = RankingEntry("a", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        e2 = RankingEntry("b", 1, "rf", "e1", "r2", "f1", 0.8, "acc", 0.7, 1.0)
        await lb.add_entry(e1)
        await lb.add_entry(e2)
        rankings = await lb.get_rankings()
        assert len(rankings) == 2

    @pytest.mark.asyncio
    async def test_get_rankings_filtered_by_metric(self):
        lb = Leaderboard()
        e1 = RankingEntry("a", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        e2 = RankingEntry("b", 1, "rf", "e1", "r2", "acc", 0.85, "f1", 0.8, 1.0)
        await lb.add_entry(e1)
        await lb.add_entry(e2)
        rankings = await lb.get_rankings(metric="f1")
        assert len(rankings) == 1

    @pytest.mark.asyncio
    async def test_get_rankings_filtered_by_model_type(self):
        lb = Leaderboard()
        e1 = RankingEntry("a", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        e2 = RankingEntry("b", 1, "xgb", "e1", "r2", "f1", 0.8, "acc", 0.7, 1.0)
        await lb.add_entry(e1)
        await lb.add_entry(e2)
        rankings = await lb.get_rankings(model_type="rf")
        assert len(rankings) == 1

    @pytest.mark.asyncio
    async def test_get_top_n(self):
        lb = Leaderboard()
        for i in range(5):
            e = RankingEntry(f"m{i}", 1, "rf", f"e{i}", f"r{i}", "f1", 0.9 - i*0.1, "acc", 0.8, 1.0)
            await lb.add_entry(e)
        top = await lb.get_top_n(metric="f1", n=3)
        assert len(top) == 3
        assert top[0].primary_score >= top[-1].primary_score

    @pytest.mark.asyncio
    async def test_get_model_history(self):
        lb = Leaderboard()
        e1 = RankingEntry("m1", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        e2 = RankingEntry("m1", 2, "rf", "e1", "r2", "f1", 0.95, "acc", 0.85, 1.0)
        await lb.add_entry(e1)
        await lb.add_entry(e2)
        history = await lb.get_model_history("m1")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_model_history_empty(self):
        lb = Leaderboard()
        history = await lb.get_model_history("nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_compare_entries(self):
        lb = Leaderboard()
        e1 = RankingEntry("a", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        e2 = RankingEntry("b", 1, "rf", "e1", "r2", "f1", 0.8, "acc", 0.7, 1.0)
        eid1 = await lb.add_entry(e1)
        eid2 = await lb.add_entry(e2)
        comp = await lb.compare_entries([eid1, eid2])
        assert comp["count"] == 2
        assert "primary_score" in comp["comparison"]

    @pytest.mark.asyncio
    async def test_compare_entries_single(self):
        lb = Leaderboard()
        e1 = RankingEntry("a", 1, "rf", "e1", "r1", "f1", 0.9, "acc", 0.8, 1.0)
        eid = await lb.add_entry(e1)
        comp = await lb.compare_entries([eid])
        assert comp["count"] == 1
        assert comp["comparison"] == {}

    @pytest.mark.asyncio
    async def test_to_markdown_empty(self):
        lb = Leaderboard()
        md = await lb.to_markdown(n=10, metric="f1")
        assert "No entries" in md

    @pytest.mark.asyncio
    async def test_to_markdown(self):
        lb = Leaderboard()
        e = RankingEntry("m1", 1, "rf", "e1", "r1", "f1", 0.95, "acc", 0.9, 5.0)
        await lb.add_entry(e)
        md = await lb.to_markdown(n=10)
        assert "Leaderboard" in md
        assert "m1" in md
        assert "0.9500" in md

    @pytest.mark.asyncio
    async def test_to_json(self):
        lb = Leaderboard()
        e = RankingEntry("m1", 1, "rf", "e1", "r1", "f1", 0.95, "acc", 0.9, 5.0)
        await lb.add_entry(e)
        js = await lb.to_json(n=10)
        data = json.loads(js)
        assert data["metric"] == "f1"
        assert len(data["entries"]) == 1

    @pytest.mark.asyncio
    async def test_to_dataframe_empty(self):
        lb = Leaderboard()
        df = await lb.to_dataframe()
        assert len(df) == 0

    @pytest.mark.asyncio
    async def test_refresh_from_db_no_pool(self):
        lb = Leaderboard()
        await lb.refresh_from_db(pool=None)


class TestRankingEngine:
    @pytest.mark.asyncio
    async def test_rank(self):
        engine = RankingEngine()
        entries = [
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.9, secondary_score=0.8),
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.95, secondary_score=0.85),
        ]
        ranked = await engine.rank(entries, "f1")
        assert ranked[0].primary_score == 0.95

    @pytest.mark.asyncio
    async def test_rank_ascending(self):
        engine = RankingEngine()
        entries = [
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.9, secondary_score=0.8),
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.8, secondary_score=0.7),
        ]
        ranked = await engine.rank(entries, "f1", ascending=True)
        assert ranked[0].primary_score == 0.8

    @pytest.mark.asyncio
    async def test_rank_multi_metric(self):
        engine = RankingEngine()
        entries = [
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.9, secondary_score=0.8),
            MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.8, secondary_score=0.7),
        ]
        scored = await engine.rank_multi_metric(entries, [("f1", 1.0, False)])
        assert len(scored) == 2

    @pytest.mark.asyncio
    async def test_compute_ranks(self):
        engine = RankingEngine()
        ranks = await engine.compute_ranks([0.9, 0.8, 0.7])
        assert ranks == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_compute_ranks_with_ties(self):
        engine = RankingEngine()
        ranks = await engine.compute_ranks([0.9, 0.9, 0.8])
        assert ranks[0] == 1
        assert ranks[1] == 1
        assert ranks[2] == 3

    @pytest.mark.asyncio
    async def test_compute_ranks_empty(self):
        engine = RankingEngine()
        ranks = await engine.compute_ranks([])
        assert ranks == []

    @pytest.mark.asyncio
    async def test_get_percentile(self):
        engine = RankingEngine()
        entry = MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.9)
        entries = [MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=s) for s in [0.8, 0.7, 0.6]]
        pct = await engine.get_percentile(entry, entries, "f1")
        assert pct == 100.0

    @pytest.mark.asyncio
    async def test_get_percentile_empty(self):
        engine = RankingEngine()
        entry = MagicMock(spec=RankingEntry, primary_metric="f1", primary_score=0.9)
        pct = await engine.get_percentile(entry, [], "f1")
        assert pct == 100.0

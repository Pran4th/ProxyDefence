from __future__ import annotations

from typing import Any


class ConfidenceFactor:
    """A single factor contributing to overall confidence."""

    def __init__(self, name: str, weight: float, score: float, rationale: str = ""):
        self.name = name
        self.weight = weight
        self.score = max(0.0, min(1.0, score))
        self.rationale = rationale


class ConfidenceResult:
    """Aggregated confidence assessment."""

    def __init__(self, overall: float, factors: list[ConfidenceFactor], reasoning_quality: float, evidence_quality: float):
        self.overall = overall
        self.factors = factors
        self.reasoning_quality = reasoning_quality
        self.evidence_quality = evidence_quality

    def to_dict(self) -> dict:
        return {
            "overall": round(self.overall, 2),
            "factors": [
                {"name": f.name, "weight": f.weight, "score": round(f.score, 2), "rationale": f.rationale}
                for f in self.factors
            ],
            "reasoning_quality": round(self.reasoning_quality, 2),
            "evidence_quality": round(self.evidence_quality, 2),
        }


class ConfidenceEngine:
    """Multi-factor confidence scoring. Replaces the naive success/total ratio."""

    def __init__(self):
        self._default_weights = {
            "tool_reliability": 0.20,
            "evidence_count": 0.15,
            "source_agreement": 0.20,
            "knowledge_graph_support": 0.10,
            "rag_score": 0.10,
            "llm_self_evaluation": 0.10,
            "contradictions": 0.15,
        }

    def compute(
        self,
        tool_results: list[dict],
        citations: list[dict],
        reflection_feedback: dict | None = None,
        rag_scores: list[float] | None = None,
        kg_support: float | None = None,
        weights: dict[str, float] | None = None,
    ) -> ConfidenceResult:
        w = weights or self._default_weights
        factors: list[ConfidenceFactor] = []

        tool_reliability = self._score_tool_reliability(tool_results)
        factors.append(ConfidenceFactor("tool_reliability", w.get("tool_reliability", 0.20), tool_reliability,
                                        f"{sum(1 for r in tool_results if r.get('success'))}/{len(tool_results)} tools succeeded" if tool_results else "no tools"))

        evidence_count = self._score_evidence_count(citations)
        factors.append(ConfidenceFactor("evidence_count", w.get("evidence_count", 0.15), evidence_count,
                                        f"{len(citations)} citations"))

        source_agreement = self._score_source_agreement(tool_results, citations)
        factors.append(ConfidenceFactor("source_agreement", w.get("source_agreement", 0.20), source_agreement,
                                        "Cross-source agreement assessment"))

        kg = kg_support if kg_support is not None else 0.5
        factors.append(ConfidenceFactor("knowledge_graph_support", w.get("knowledge_graph_support", 0.10), kg,
                                        f"KG support: {kg:.2f}"))

        rag = self._score_rag(rag_scores)
        factors.append(ConfidenceFactor("rag_score", w.get("rag_score", 0.10), rag,
                                        f"RAG scores: {rag_scores}" if rag_scores else "No RAG data"))

        llm_eval = self._score_llm_evaluation(reflection_feedback)
        factors.append(ConfidenceFactor("llm_self_evaluation", w.get("llm_self_evaluation", 0.10), llm_eval,
                                        f"LLM self-eval: {llm_eval:.2f}" if reflection_feedback else "No self-eval"))

        contradictions = self._score_contradictions(tool_results)
        factors.append(ConfidenceFactor("contradictions", w.get("contradictions", 0.15), contradictions,
                                        "Contradiction assessment"))

        overall = sum(f.score * f.weight for f in factors)
        reasoning_quality = (tool_reliability + source_agreement + (1 - contradictions)) / 3
        evidence_quality = (evidence_count + rag + kg) / 3

        return ConfidenceResult(overall=overall, factors=factors, reasoning_quality=reasoning_quality, evidence_quality=evidence_quality)

    def _score_tool_reliability(self, results: list[dict]) -> float:
        if not results:
            return 0.5
        successes = sum(1 for r in results if r.get("success"))
        return successes / len(results)

    def _score_evidence_count(self, citations: list[dict]) -> float:
        count = len(citations)
        if count >= 10:
            return 1.0
        if count >= 5:
            return 0.8
        if count >= 3:
            return 0.6
        if count >= 1:
            return 0.4
        return 0.1

    def _score_source_agreement(self, results: list[dict], citations: list[dict]) -> float:
        if len(results) <= 1 and len(citations) <= 1:
            return 0.7
        successes = [r for r in results if r.get("success")]
        unique_sources = set(c.get("source_id") for c in citations if c.get("source_id"))
        if len(unique_sources) >= 3:
            return 0.9
        if len(unique_sources) >= 2:
            return 0.7
        return 0.5

    def _score_rag(self, rag_scores: list[float] | None) -> float:
        if not rag_scores:
            return 0.5
        if not rag_scores:
            return 0.5
        avg = sum(rag_scores) / len(rag_scores)
        return min(1.0, avg)

    def _score_llm_evaluation(self, feedback: dict | None) -> float:
        if not feedback:
            return 0.5
        return feedback.get("confidence", 0.5)

    def _score_contradictions(self, results: list[dict]) -> float:
        if len(results) <= 1:
            return 1.0
        failures = sum(1 for r in results if not r.get("success"))
        if failures == 0:
            return 1.0
        ratio = failures / len(results)
        return max(0.1, 1.0 - ratio)

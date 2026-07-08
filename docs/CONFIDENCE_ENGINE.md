# Confidence Engine

## Purpose

Multi-factor confidence scoring that replaces the naive `successful_calls / total_calls` ratio.

## File: `backend/shared/orchestration/confidence.py`

### Factors and Weights

| Factor | Default Weight | Description |
|--------|---------------|-------------|
| tool_reliability | 0.20 | % of successful tool calls |
| evidence_count | 0.15 | Number of unique citations |
| source_agreement | 0.20 | Cross-source consistency |
| knowledge_graph_support | 0.10 | KG entity match score |
| rag_score | 0.10 | Average RAG relevance |
| llm_self_evaluation | 0.10 | LLM's own confidence |
| contradictions | 0.15 | Inverse of contradiction rate |

### `ConfidenceEngine.compute(...) → ConfidenceResult`

**Inputs:**
- `tool_results`: list of tool execution records
- `citations`: list of citation records
- `reflection_feedback`: optional dict with LLM self-evaluation
- `rag_scores`: optional list of RAG relevance scores
- `kg_support`: optional KG connection score (0-1)
- `weights`: optional factor weight overrides

**Output:**
```python
class ConfidenceResult:
    overall: float           # Weighted sum (0-1)
    factors: list[ConfidenceFactor]  # Individual factor scores
    reasoning_quality: float # Tool reliability + agreement
    evidence_quality: float  # Evidence count + RAG + KG
```

### Scoring Rules

- **tool_reliability**: successes / total (0.5 if no tools)
- **evidence_count**: 1.0 (10+ sources), 0.8 (5+), 0.6 (3+), 0.4 (1+), 0.1 (0)
- **source_agreement**: 0.9 (3+ unique sources), 0.7 (2+), 0.5 (≤1)
- **contradictions**: 1.0 (0 failures), max(0.1, 1 - failure_rate)
- **rag_score**: min(1.0, avg) or 0.5 if no data
- **llm_self_evaluation**: reflection confidence or 0.5 if no feedback
- **knowledge_graph_support**: provided value or 0.5 if none

### Weights are Configurable

```python
weights = {"tool_reliability": 0.30, "evidence_count": 0.25, ...}
engine = ConfidenceEngine()
result = engine.compute(tool_results, citations, weights=weights)
```

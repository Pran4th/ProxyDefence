from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    confidence: float


class GraphResponse(BaseModel):
    node_count: int
    edge_count: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]

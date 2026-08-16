"""Grafo cognitivo — motor nativo (SQLite + índice em RAM), sem networkx.
Serve ao Knowledge Graph ("o que a Aila sabe") e ao Code Graph ("como o
software funciona"), distinguidos pelo ``type`` dos nós."""

from aila.cognition.graph.graph_store import GraphStore, edge_id
from aila.cognition.graph.models import GraphEdge, GraphNode

__all__ = ["GraphStore", "GraphNode", "GraphEdge", "edge_id"]

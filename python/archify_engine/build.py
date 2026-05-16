"""Phase 3 graph assembly for Archify."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _normalize_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return cleaned.strip("_").lower()


def _normalize_path(value: str | None) -> str | None:
    if not value:
        return value
    return Path(value.replace("\\", "/")).as_posix()


def _coerce_node(node: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(node)
    if "source" in normalized and "source_file" not in normalized:
        normalized["source_file"] = normalized.pop("source")
    normalized["source_file"] = _normalize_path(str(normalized.get("source_file", ""))) or ""
    if not normalized.get("file_type"):
        normalized["file_type"] = "concept"
    return normalized


def _edge_sort_key(edge: dict[str, Any]) -> tuple[Any, ...]:
    return (
        edge["source"],
        edge["target"],
        edge.get("relation", ""),
        edge.get("confidence", ""),
        edge.get("source_file", ""),
        edge.get("source_location", {}).get("line", 0),
        edge.get("source_location", {}).get("column", 0),
    )


def _node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    return (
        node.get("id", ""),
        node.get("kind", ""),
        node.get("label", ""),
        node.get("source_file", ""),
    )


def build_graph(extraction: dict[str, Any]) -> dict[str, Any]:
    """Normalize extraction output into a stable graph payload."""
    raw_nodes = extraction.get("nodes", [])
    raw_edges = extraction.get("edges")
    if raw_edges is None:
        raw_edges = extraction.get("links", [])
    raw_hyperedges = extraction.get("hyperedges", [])

    warnings: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    for index, node in enumerate(raw_nodes):
        if not isinstance(node, dict):
            warnings.append(
                {
                    "type": "invalid_node",
                    "index": index,
                    "message": "Skipped non-object node during graph build.",
                }
            )
            continue
        if not isinstance(node.get("id"), str) or not node["id"].strip():
            warnings.append(
                {
                    "type": "invalid_node",
                    "index": index,
                    "message": "Skipped node with missing string id during graph build.",
                }
            )
            continue
        nodes.append(_coerce_node(node))

    normalized_id_map: dict[str, str] = {}
    for node in sorted(nodes, key=_node_sort_key):
        normalized_id_map.setdefault(_normalize_id(node["id"]), node["id"])

    known_node_ids = {node["id"] for node in nodes}
    edges: list[dict[str, Any]] = []
    dangling_edge_count = 0

    for index, edge in enumerate(raw_edges or []):
        if not isinstance(edge, dict):
            warnings.append(
                {
                    "type": "invalid_edge",
                    "index": index,
                    "message": "Skipped non-object edge during graph build.",
                }
            )
            continue
        source = edge.get("source", edge.get("from"))
        target = edge.get("target", edge.get("to"))
        if not isinstance(source, str) or not isinstance(target, str):
            warnings.append(
                {
                    "type": "invalid_edge",
                    "index": index,
                    "message": "Skipped edge without string source/target.",
                }
            )
            continue

        resolved_source = source if source in known_node_ids else normalized_id_map.get(_normalize_id(source))
        resolved_target = target if target in known_node_ids else normalized_id_map.get(_normalize_id(target))
        if resolved_source not in known_node_ids or resolved_target not in known_node_ids:
            dangling_edge_count += 1
            warnings.append(
                {
                    "type": "dangling_edge",
                    "index": index,
                    "message": f"Skipped unresolved edge {source!r} -> {target!r}.",
                    "source": source,
                    "target": target,
                }
            )
            continue

        normalized_edge = dict(edge)
        normalized_edge["source"] = resolved_source
        normalized_edge["target"] = resolved_target
        normalized_edge["source_file"] = _normalize_path(str(normalized_edge.get("source_file", ""))) or ""
        normalized_edge["directed"] = True
        edges.append(normalized_edge)

    hyperedges: list[dict[str, Any]] = []
    for index, hyperedge in enumerate(raw_hyperedges):
        if not isinstance(hyperedge, dict):
            warnings.append(
                {
                    "type": "invalid_hyperedge",
                    "index": index,
                    "message": "Skipped non-object hyperedge during graph build.",
                }
            )
            continue
        normalized_hyperedge = dict(hyperedge)
        if "source_file" in normalized_hyperedge:
            normalized_hyperedge["source_file"] = _normalize_path(str(normalized_hyperedge["source_file"]))
        hyperedges.append(normalized_hyperedge)

    return {
        "nodes": sorted(nodes, key=_node_sort_key),
        "edges": sorted(edges, key=_edge_sort_key),
        "hyperedges": hyperedges,
        "warnings": warnings,
        "summary": {
            "inputNodeCount": len(raw_nodes),
            "inputEdgeCount": len(raw_edges or []),
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "hyperedgeCount": len(hyperedges),
            "danglingEdgeCount": dangling_edge_count,
            "warningCount": len(warnings),
        },
    }

"""Shared extraction schema helpers for deterministic code extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_FILE_TYPES = {"code", "document", "config", "asset", "concept"}
VALID_CONFIDENCES = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
REQUIRED_NODE_FIELDS = {"id", "label", "file_type", "source_file"}
REQUIRED_EDGE_FIELDS = {"source", "target", "relation", "confidence", "source_file"}


def make_id(*parts: str) -> str:
    """Build a stable lowercase identifier from semantic parts."""
    combined = "_".join(part.strip("_. ") for part in parts if part and part.strip("_. "))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", combined)
    return cleaned.strip("_").lower()


def make_file_id(rel_path: str) -> str:
    return make_id("file", rel_path)


def make_symbol_id(rel_path: str, kind: str, qualname: str) -> str:
    return make_id("symbol", rel_path, kind, qualname)


def make_reference_id(rel_path: str, kind: str, label: str) -> str:
    return make_id("ref", rel_path, kind, label)


def build_location(line: int | None, column: int | None = None) -> dict[str, int]:
    location = {"line": max(int(line or 1), 1)}
    if column is not None:
        location["column"] = max(int(column), 0)
    return location


def validate_extraction(data: dict[str, Any]) -> list[str]:
    if not isinstance(data, dict):
        return ["Extraction must be a JSON object."]

    errors: list[str] = []
    nodes = data.get("nodes")
    edges = data.get("edges")
    hyperedges = data.get("hyperedges", [])

    if not isinstance(nodes, list):
        errors.append("'nodes' must be a list.")
        nodes = []
    if not isinstance(edges, list):
        errors.append("'edges' must be a list.")
        edges = []
    if not isinstance(hyperedges, list):
        errors.append("'hyperedges' must be a list.")

    seen_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node {index} must be an object.")
            continue
        for field_name in REQUIRED_NODE_FIELDS:
            if field_name not in node:
                errors.append(f"Node {index} missing required field '{field_name}'.")
        node_id = node.get("id")
        if node_id in seen_ids:
            errors.append(f"Duplicate node id '{node_id}'.")
        elif isinstance(node_id, str):
            seen_ids.add(node_id)
        file_type = node.get("file_type")
        if file_type is not None and file_type not in VALID_FILE_TYPES:
            errors.append(f"Node {index} has invalid file_type '{file_type}'.")

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"Edge {index} must be an object.")
            continue
        for field_name in REQUIRED_EDGE_FIELDS:
            if field_name not in edge:
                errors.append(f"Edge {index} missing required field '{field_name}'.")
        confidence = edge.get("confidence")
        if confidence is not None and confidence not in VALID_CONFIDENCES:
            errors.append(f"Edge {index} has invalid confidence '{confidence}'.")
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and source not in seen_ids:
            errors.append(f"Edge {index} source '{source}' does not match a node id.")
        if isinstance(target, str) and target not in seen_ids:
            errors.append(f"Edge {index} target '{target}' does not match a node id.")

    return errors


def assert_valid_extraction(data: dict[str, Any]) -> None:
    errors = validate_extraction(data)
    if errors:
        raise ValueError("Invalid extraction payload:\n" + "\n".join(f"- {error}" for error in errors))


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node["id"]
        if node_id not in deduped:
            deduped[node_id] = node
    return [deduped[node_id] for node_id in sorted(deduped)]


def dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for edge in edges:
        key = (
            edge["source"],
            edge["target"],
            edge["relation"],
            edge["confidence"],
            edge["source_file"],
            edge.get("source_location", {}).get("line"),
        )
        if key not in deduped:
            deduped[key] = edge
    return [deduped[key] for key in sorted(deduped)]


def merge_fragments(fragments: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    hyperedges: list[dict[str, Any]] = []

    for fragment in fragments:
        nodes.extend(fragment.get("nodes", []))
        edges.extend(fragment.get("edges", []))
        hyperedges.extend(fragment.get("hyperedges", []))

    merged = {
        "nodes": dedupe_nodes(nodes),
        "edges": dedupe_edges(edges),
        "hyperedges": hyperedges,
    }
    assert_valid_extraction(merged)
    return merged


@dataclass(frozen=True)
class ExtractionSchema:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    hyperedges: list[dict[str, Any]] = field(default_factory=list)


def normalize_rel_path(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()

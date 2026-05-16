"""Deterministic graph-level deduplication for Phase 3."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    return (
        node.get("id", ""),
        node.get("kind", ""),
        node.get("label", ""),
        node.get("source_file", ""),
    )


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


def _normalized_label(label: str) -> str:
    label = label.strip().lower()
    label = re.sub(r"\(\)$", "", label)
    label = re.sub(r"[^a-z0-9]+", " ", label)
    return re.sub(r"\s+", " ", label).strip()


def _source_suffix(node: dict[str, Any]) -> str:
    return Path(node.get("source_file", "")).suffix.lower()


def _compatible_for_label_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("kind") != right.get("kind"):
        return False
    if left.get("file_type") != right.get("file_type"):
        return False
    if left.get("kind") == "file":
        return False
    return _source_suffix(left) == _source_suffix(right)


def _merge_node_attrs(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(nodes, key=_node_sort_key)
    merged = dict(ordered[0])
    for node in ordered[1:]:
        for key, value in node.items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
    return merged


def deduplicate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    raw_nodes = list(graph.get("nodes", []))
    raw_edges = list(graph.get("edges", []))

    duplicate_id_groups: dict[str, list[dict[str, Any]]] = {}
    for node in raw_nodes:
        duplicate_id_groups.setdefault(node["id"], []).append(node)

    remap: dict[str, str] = {}
    deduped_nodes: list[dict[str, Any]] = []
    duplicate_id_count = 0

    for node_id in sorted(duplicate_id_groups):
        group = duplicate_id_groups[node_id]
        merged = _merge_node_attrs(group)
        deduped_nodes.append(merged)
        duplicate_id_count += max(len(group) - 1, 0)
        for node in group:
            remap[node["id"]] = merged["id"]

    label_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for node in deduped_nodes:
        normalized_label = _normalized_label(str(node.get("label", "")))
        if not normalized_label:
            continue
        key = (
            normalized_label,
            str(node.get("kind", "")),
            str(node.get("file_type", "")),
            _source_suffix(node),
        )
        label_groups.setdefault(key, []).append(node)

    merged_label_groups: list[dict[str, Any]] = []
    label_remap: dict[str, str] = {}
    surviving_nodes: list[dict[str, Any]] = []

    for key in sorted(label_groups):
        group = sorted(label_groups[key], key=_node_sort_key)
        survivor = group[0]
        compatible_group = [survivor]
        for candidate in group[1:]:
            if _compatible_for_label_merge(survivor, candidate):
                compatible_group.append(candidate)
            else:
                surviving_nodes.append(candidate)
        if len(compatible_group) > 1:
            merged = _merge_node_attrs(compatible_group)
            merged_label_groups.append(
                {
                    "label": key[0],
                    "survivor": merged["id"],
                    "merged": [node["id"] for node in compatible_group if node["id"] != merged["id"]],
                }
            )
            for node in compatible_group:
                label_remap[node["id"]] = merged["id"]
            surviving_nodes.append(merged)
        else:
            surviving_nodes.append(survivor)

    grouped_ids = {node["id"] for nodes in label_groups.values() for node in nodes}
    surviving_nodes.extend(node for node in deduped_nodes if node["id"] not in grouped_ids)
    unique_nodes_by_id = {node["id"]: node for node in surviving_nodes}
    final_nodes = [unique_nodes_by_id[node_id] for node_id in sorted(unique_nodes_by_id)]

    final_remap = {**remap, **label_remap}
    edge_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    duplicate_edge_count = 0
    dropped_self_loops = 0

    for edge in raw_edges:
        rewritten = dict(edge)
        rewritten["source"] = final_remap.get(rewritten["source"], rewritten["source"])
        rewritten["target"] = final_remap.get(rewritten["target"], rewritten["target"])
        if rewritten["source"] == rewritten["target"]:
            dropped_self_loops += 1
            continue
        key = _edge_sort_key(rewritten)
        if key in edge_map:
            duplicate_edge_count += 1
            continue
        edge_map[key] = rewritten

    return {
        **graph,
        "nodes": final_nodes,
        "edges": [edge_map[key] for key in sorted(edge_map)],
        "dedup": {
            "duplicateNodeCount": duplicate_id_count + sum(len(item["merged"]) for item in merged_label_groups),
            "duplicateNodeIdCount": duplicate_id_count,
            "duplicateEdgeCount": duplicate_edge_count,
            "mergedLabelGroupCount": len(merged_label_groups),
            "mergedLabelGroups": merged_label_groups,
            "droppedSelfLoopCount": dropped_self_loops,
        },
    }

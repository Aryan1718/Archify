"""Deterministic graph analysis for Phase 4."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_EXCLUDED_SURPRISE_RELATIONS = {"contains", "imports", "method"}
_CONFIDENCE_SCORE = {"AMBIGUOUS": 3, "INFERRED": 2, "EXTRACTED": 1}
_KIND_PRIORITY = {
    "class": 0,
    "function": 1,
    "method": 2,
    "sql_table": 3,
    "import_reference": 4,
    "call_reference": 5,
    "file": 6,
}


def _node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    return (
        node.get("id", ""),
        node.get("kind", ""),
        node.get("label", ""),
        node.get("source_file", ""),
    )


def _edge_sort_key(edge: dict[str, Any]) -> tuple[Any, ...]:
    return (
        edge.get("source", ""),
        edge.get("target", ""),
        edge.get("relation", ""),
        edge.get("confidence", ""),
        edge.get("source_file", ""),
        edge.get("source_location", {}).get("line", 0),
        edge.get("source_location", {}).get("column", 0),
    )


def _node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in graph.get("nodes", [])}


def _adjacency(graph: dict[str, Any]) -> dict[str, set[str]]:
    adjacency = {node["id"]: set() for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
    return adjacency


def _degree_map(adjacency: dict[str, set[str]]) -> dict[str, int]:
    return {node_id: len(neighbors) for node_id, neighbors in adjacency.items()}


def _top_level_dir(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else path


def _is_grounded_node(node: dict[str, Any]) -> bool:
    source_file = str(node.get("source_file", "")).strip()
    if not source_file:
        return False
    return bool(Path(source_file).suffix)


def _is_file_hub_node(node: dict[str, Any], degree: int) -> bool:
    kind = str(node.get("kind", ""))
    if kind == "file":
        return True
    label = str(node.get("label", ""))
    source_file = str(node.get("source_file", ""))
    if source_file and label == Path(source_file).name:
        return True
    if label.startswith(".") and label.endswith("()"):
        return True
    if label.endswith("()") and degree <= 1 and kind in {"function", "method"}:
        return True
    return False


def _community_members(graph: dict[str, Any], community_id: int) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("community") == community_id:
            members.append(node)
    return sorted(members, key=_node_sort_key)


def god_nodes(graph: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
    adjacency = _adjacency(graph)
    degrees = _degree_map(adjacency)
    ranked = sorted(
        graph.get("nodes", []),
        key=lambda node: (
            -degrees.get(node["id"], 0),
            _KIND_PRIORITY.get(str(node.get("kind", "")), 99),
            _node_sort_key(node),
        ),
    )
    results: list[dict[str, Any]] = []

    for node in ranked:
        degree = degrees.get(node["id"], 0)
        if _is_file_hub_node(node, degree):
            continue
        if not _is_grounded_node(node):
            continue
        results.append(
            {
                "id": node["id"],
                "label": node.get("label", node["id"]),
                "degree": degree,
                "community": node.get("community"),
                "sourceFile": node.get("source_file", ""),
                "kind": node.get("kind", ""),
            }
        )
        if len(results) >= top_n:
            break

    return results


def _surprise_score(
    edge: dict[str, Any],
    source_node: dict[str, Any],
    target_node: dict[str, Any],
    degrees: dict[str, int],
) -> tuple[int, list[str]]:
    score = _CONFIDENCE_SCORE.get(str(edge.get("confidence", "EXTRACTED")), 1)
    reasons: list[str] = []
    confidence = str(edge.get("confidence", "EXTRACTED"))
    if confidence in {"AMBIGUOUS", "INFERRED"}:
        reasons.append(f"{confidence.lower()} relationship")

    source_file = str(source_node.get("source_file", ""))
    target_file = str(target_node.get("source_file", ""))
    if source_file != target_file:
        score += 2
        reasons.append("cross-file link")

    if source_node.get("community") != target_node.get("community"):
        score += 2
        reasons.append("cross-community bridge")

    if _top_level_dir(source_file) != _top_level_dir(target_file):
        score += 1
        reasons.append("cross-boundary directory hop")

    source_degree = degrees.get(source_node["id"], 0)
    target_degree = degrees.get(target_node["id"], 0)
    if min(source_degree, target_degree) <= 1 and max(source_degree, target_degree) >= 3:
        score += 1
        reasons.append("peripheral-to-hub jump")

    return score, reasons


def surprising_connections(graph: dict[str, Any], top_n: int = 5) -> list[dict[str, Any]]:
    nodes = _node_index(graph)
    adjacency = _adjacency(graph)
    degrees = _degree_map(adjacency)
    candidates: list[dict[str, Any]] = []

    for edge in sorted(graph.get("edges", []), key=_edge_sort_key):
        relation = str(edge.get("relation", ""))
        if relation in _EXCLUDED_SURPRISE_RELATIONS:
            continue
        source = nodes.get(str(edge.get("source", "")))
        target = nodes.get(str(edge.get("target", "")))
        if source is None or target is None:
            continue
        if _is_file_hub_node(source, degrees.get(source["id"], 0)) or _is_file_hub_node(target, degrees.get(target["id"], 0)):
            continue
        if not _is_grounded_node(source) or not _is_grounded_node(target):
            continue
        if source["id"] == target["id"]:
            continue
        score, reasons = _surprise_score(edge, source, target, degrees)
        candidates.append(
            {
                "_score": score,
                "sourceId": source["id"],
                "targetId": target["id"],
                "source": source.get("label", source["id"]),
                "target": target.get("label", target["id"]),
                "relation": relation,
                "confidence": edge.get("confidence", "EXTRACTED"),
                "confidenceScore": edge.get("confidence_score"),
                "sourceFiles": [source.get("source_file", ""), target.get("source_file", "")],
                "communities": [source.get("community"), target.get("community")],
                "why": ", ".join(reasons) if reasons else "cross-graph structural connection",
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["_score"],
            item["sourceFiles"][0],
            item["sourceFiles"][1],
            item["relation"],
            item["source"],
            item["target"],
        )
    )
    for item in candidates:
        item.pop("_score")
    return candidates[:top_n]


def community_summary(graph: dict[str, Any], max_members: int = 8) -> dict[str, Any]:
    communities = graph.get("communities", {})
    summaries: list[dict[str, Any]] = []

    for community_id in sorted(communities, key=lambda value: int(value)):
        payload = communities[community_id]
        members = _community_members(graph, int(community_id))
        real_members = [node for node in members if node.get("kind") != "file"]
        labels = [str(node.get("label", node["id"])) for node in real_members[:max_members]]
        kind_counts = Counter(str(node.get("kind", "unknown")) for node in real_members)
        summaries.append(
            {
                "id": int(community_id),
                "size": payload.get("size", len(members)),
                "cohesion": payload.get("cohesion", 0.0),
                "sampleLabels": labels,
                "primaryKinds": [
                    {"kind": kind, "count": count}
                    for kind, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
                ],
            }
        )

    return {
        "communityCount": len(summaries),
        "thinCommunityCount": sum(1 for item in summaries if item["size"] < 3),
        "communities": summaries,
    }


def ambiguity_summary(graph: dict[str, Any], sample_size: int = 10) -> dict[str, Any]:
    nodes = _node_index(graph)
    ambiguous_edges = [
        edge
        for edge in sorted(graph.get("edges", []), key=_edge_sort_key)
        if str(edge.get("confidence", "")) == "AMBIGUOUS"
    ]
    relation_counts = Counter(str(edge.get("relation", "unknown")) for edge in ambiguous_edges)
    samples: list[dict[str, Any]] = []

    for edge in ambiguous_edges[:sample_size]:
        source = nodes.get(str(edge.get("source", "")), {})
        target = nodes.get(str(edge.get("target", "")), {})
        samples.append(
            {
                "sourceId": edge.get("source", ""),
                "targetId": edge.get("target", ""),
                "source": source.get("label", edge.get("source", "")),
                "target": target.get("label", edge.get("target", "")),
                "relation": edge.get("relation", "unknown"),
                "sourceFile": edge.get("source_file", ""),
            }
        )

    return {
        "ambiguousEdgeCount": len(ambiguous_edges),
        "byRelation": dict(sorted(relation_counts.items())),
        "samples": samples,
    }


def knowledge_gaps(graph: dict[str, Any]) -> dict[str, Any]:
    adjacency = _adjacency(graph)
    degrees = _degree_map(adjacency)
    isolated: list[dict[str, Any]] = []
    by_community: dict[int, list[str]] = defaultdict(list)

    for node in sorted(graph.get("nodes", []), key=_node_sort_key):
        degree = degrees.get(node["id"], 0)
        if _is_file_hub_node(node, degree):
            continue
        if not _is_grounded_node(node):
            continue
        if degree <= 1:
            isolated.append(
                {
                    "id": node["id"],
                    "label": node.get("label", node["id"]),
                    "community": node.get("community"),
                    "sourceFile": node.get("source_file", ""),
                }
            )
        community = node.get("community")
        if isinstance(community, int):
            by_community[community].append(node["id"])

    thin_communities = sorted(community for community, members in by_community.items() if 0 < len(members) < 3)
    return {
        "isolatedNodeCount": len(isolated),
        "isolatedNodes": isolated[:10],
        "thinCommunities": thin_communities,
    }


def suggested_questions(graph: dict[str, Any], analysis: dict[str, Any], top_n: int = 5) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    if analysis["godNodes"]:
        node = analysis["godNodes"][0]
        text = f"Why is `{node['label']}` central to the repository?"
        seen.add(text)
        questions.append(
            {
                "question": text,
                "type": "hub",
                "why": f"It has the highest grounded degree in community {node.get('community', 'unknown')}.",
            }
        )

    if analysis["surprisingConnections"]:
        surprise = analysis["surprisingConnections"][0]
        text = f"How does `{surprise['source']}` connect to `{surprise['target']}` across boundaries?"
        if text not in seen:
            seen.add(text)
            questions.append(
                {
                    "question": text,
                    "type": "surprise",
                    "why": surprise["why"],
                }
            )

    for community in analysis["communitySummary"]["communities"]:
        labels = community["sampleLabels"]
        if not labels:
            continue
        text = f"What responsibilities are grouped inside Community {community['id']}?"
        if text in seen:
            continue
        seen.add(text)
        questions.append(
            {
                "question": text,
                "type": "community",
                "why": f"Representative nodes: {', '.join(labels[:3])}.",
            }
        )
        if len(questions) >= top_n:
            break

    ambiguous = analysis["ambiguitySummary"]["samples"]
    if ambiguous and len(questions) < top_n:
        sample = ambiguous[0]
        text = f"Should the `{sample['relation']}` link from `{sample['source']}` to `{sample['target']}` be trusted?"
        if text not in seen:
            questions.append(
                {
                    "question": text,
                    "type": "ambiguity",
                    "why": f"It is currently grounded only by ambiguous evidence in {sample['sourceFile']}.",
                }
            )

    if not questions:
        return [
            {
                "question": "Which grounded components in this repository need more structural links?",
                "type": "no_signal",
                "why": "The graph is too small or too sparse to rank stronger navigation questions yet.",
            }
        ]

    return questions[:top_n]


def analyze_graph(graph: dict[str, Any]) -> dict[str, Any]:
    gods = god_nodes(graph)
    surprises = surprising_connections(graph)
    communities = community_summary(graph)
    ambiguity = ambiguity_summary(graph)
    gaps = knowledge_gaps(graph)

    analysis = {
        "godNodes": gods,
        "surprisingConnections": surprises,
        "communitySummary": communities,
        "ambiguitySummary": ambiguity,
        "knowledgeGaps": gaps,
    }
    analysis["suggestedQuestions"] = suggested_questions(graph, analysis)
    return analysis

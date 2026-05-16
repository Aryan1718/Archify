"""Deterministic architecture context synthesis for Phase 5."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_GENERIC_PREFIXES = {"src", "app", "apps", "lib", "pkg", "packages", "services"}
_GENERIC_SUBSYSTEM_NAMES = {"common", "shared", "utils", "core"}
_CONCERN_KEYWORDS = {
    "config": ("config", "settings", "env"),
    "logging": ("log", "logger", "logging"),
    "auth": ("auth", "login", "jwt", "session", "permission", "token"),
    "persistence": ("db", "database", "sql", "repo", "repository", "model", "store"),
    "caching": ("cache", "redis", "memo"),
    "errors": ("error", "exception", "failure"),
    "observability": ("metric", "trace", "span", "telemetry", "monitor"),
}
_INTERFACE_KEYWORDS = {
    "cli": ("cli", "main", "run", "serve"),
    "route": ("route", "router", "api", "handler", "controller", "endpoint"),
    "service": ("service", "client", "facade", "provider"),
    "database": ("repo", "repository", "store", "query", "sql", "table", "model"),
}
_ENTRYPOINT_BASENAMES = {
    "main.py",
    "__main__.py",
    "app.py",
    "server.py",
    "manage.py",
    "cli.py",
    "index.js",
    "main.js",
    "server.js",
    "app.js",
    "cli.js",
}
_KIND_ORDER = {
    "class": 0,
    "function": 1,
    "method": 2,
    "sql_table": 3,
    "import_reference": 4,
    "call_reference": 5,
    "file": 6,
}
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
_CONFIDENCE_LABEL_BY_EDGE = {"EXTRACTED": "high", "INFERRED": "medium", "AMBIGUOUS": "low"}


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "item"


def _node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    return (
        node.get("source_file", ""),
        _KIND_ORDER.get(str(node.get("kind", "")), 99),
        node.get("label", ""),
        node.get("id", ""),
    )


def _edge_sort_key(edge: dict[str, Any]) -> tuple[Any, ...]:
    location = edge.get("source_location", {}) or {}
    return (
        edge.get("source", ""),
        edge.get("target", ""),
        edge.get("relation", ""),
        edge.get("source_file", ""),
        location.get("line", 0),
        location.get("column", 0),
    )


def _top_level_dir(path: str) -> str:
    if "/" not in path:
        return path or "."
    return path.split("/", 1)[0]


def _path_tokens(path: str) -> list[str]:
    return [token for token in Path(path).as_posix().split("/") if token]


def _meaningful_prefix(path: str) -> str:
    tokens = _path_tokens(path)
    if not tokens:
        return "."
    if len(tokens) == 1:
        return tokens[0]
    if tokens[0] in _GENERIC_PREFIXES:
        return "/".join(tokens[:2])
    return tokens[0]


def _confidence_rank(label: str) -> int:
    return _CONFIDENCE_ORDER.get(label, 99)


def _edge_ref(edge: dict[str, Any]) -> str:
    location = edge.get("source_location", {}) or {}
    return (
        f"edge:{edge.get('source', '')}:{edge.get('relation', '')}:{edge.get('target', '')}:"
        f"{edge.get('source_file', '')}:{location.get('line', 0)}:{location.get('column', 0)}"
    )


def _node_ref(node_id: str) -> str:
    return f"node:{node_id}"


def _file_ref(path: str) -> str:
    return f"file:{path}"


def _is_doc_node(node: dict[str, Any]) -> bool:
    return str(node.get("file_type", "")) == "document" or str(node.get("kind", "")).startswith("doc_") or str(node.get("kind", "")) == "document"


def _is_symbol_node(node: dict[str, Any]) -> bool:
    return str(node.get("kind", "")) != "file"


def _node_keywords(node: dict[str, Any]) -> str:
    return f"{node.get('label', '')} {node.get('source_file', '')}".lower()


def _build_adjacency(graph: dict[str, Any]) -> dict[str, set[str]]:
    adjacency = {node["id"]: set() for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
    return adjacency


def _group_nodes_into_subsystems(
    community_id: int,
    members: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    if len(members) < 4:
        return [sorted(members, key=_node_sort_key)]

    members_by_id = {member["id"]: member for member in members}
    by_prefix: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for member in members:
        source_file = str(member.get("source_file", ""))
        if not source_file:
            return [sorted(members, key=_node_sort_key)]
        by_prefix[_meaningful_prefix(source_file)].append(member)

    groups = [sorted(group, key=_node_sort_key) for _, group in sorted(by_prefix.items()) if len(group) >= 2]
    if len(groups) < 2:
        return [sorted(members, key=_node_sort_key)]

    group_by_node: dict[str, str] = {}
    for prefix, group in sorted(by_prefix.items()):
        for member in group:
            group_by_node[member["id"]] = prefix

    inter_group_edges = 0
    internal_edges = 0
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in members_by_id or target not in members_by_id:
            continue
        source_group = group_by_node.get(str(source))
        target_group = group_by_node.get(str(target))
        if source_group is None or target_group is None:
            continue
        if source_group == target_group:
            internal_edges += 1
        else:
            inter_group_edges += 1

    if inter_group_edges > max(1, len(groups) - 1):
        return [sorted(members, key=_node_sort_key)]
    if internal_edges and inter_group_edges >= internal_edges:
        return [sorted(members, key=_node_sort_key)]

    return groups


def _subsystem_name(paths: list[str], key_symbols: list[str]) -> str:
    if paths:
        prefix_counts = Counter(_meaningful_prefix(path) for path in paths)
        prefix, _ = prefix_counts.most_common(1)[0]
        pieces = [piece for piece in prefix.split("/") if piece]
        if len(pieces) >= 2 and pieces[0] in _GENERIC_PREFIXES:
            return "/".join(pieces[:2])
        if pieces:
            return pieces[-1]
    if key_symbols:
        return key_symbols[0].replace("()", "")
    return "unclassified"


def _subsystem_kind(nodes: list[dict[str, Any]], source_paths: list[str], edges: list[dict[str, Any]]) -> str:
    text = " ".join([*(path.lower() for path in source_paths), *(_node_keywords(node) for node in nodes)])
    kinds = Counter(str(node.get("kind", "")) for node in nodes)
    relations = Counter(str(edge.get("relation", "")) for edge in edges)

    if any(keyword in text for keyword in ("ui", "component", "view", "page", "react", "frontend")):
        return "ui"
    if kinds.get("sql_table", 0) or sum(relations.get(name, 0) for name in ("queries", "writes", "updates", "deletes", "defines", "references")):
        return "data_layer"
    if any(keyword in text for keyword in ("adapter", "client", "provider", "gateway", "integration")):
        return "adapter"
    if any(keyword in text for keyword in ("config", "logging", "logger", "infra", "ops", "deploy")):
        return "infrastructure"
    if any(keyword in text for keyword in ("shared", "common", "utils")):
        return "shared_library"
    if any(keyword in text for keyword in ("service", "handler", "worker")):
        return "service"
    if kinds.get("class", 0) >= max(1, kinds.get("function", 0)):
        return "domain"
    return "module"


def _subsystem_confidence(nodes: list[dict[str, Any]], source_paths: list[str], ambiguous_edges: int) -> str:
    if not source_paths:
        return "low"
    prefix_counts = Counter(_meaningful_prefix(path) for path in source_paths)
    dominant_ratio = prefix_counts.most_common(1)[0][1] / max(1, len(source_paths))
    if dominant_ratio >= 0.75 and ambiguous_edges == 0 and len(nodes) >= 2:
        return "high"
    if dominant_ratio >= 0.5:
        return "medium"
    return "low"


def _subsystem_summary(
    name: str,
    kind: str,
    source_paths: list[str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> str:
    symbol_count = sum(1 for node in nodes if _is_symbol_node(node))
    relation_counts = Counter(str(edge.get("relation", "")) for edge in edges if edge.get("relation"))
    strongest = ", ".join(f"{relation} x{count}" for relation, count in relation_counts.most_common(2)) or "structure-only edges"
    return f"{name} is a {kind} subsystem covering {len(source_paths)} paths and {symbol_count} symbols; strongest evidence: {strongest}."


def _subsystem_responsibilities(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], interface_count: int) -> list[str]:
    kinds = Counter(str(node.get("kind", "")) for node in nodes if _is_symbol_node(node))
    relations = Counter(str(edge.get("relation", "")) for edge in edges if edge.get("relation"))
    responsibilities: list[str] = []

    if kinds:
        top_kinds = ", ".join(f"{kind} x{count}" for kind, count in kinds.most_common(2))
        responsibilities.append(f"Primary symbols: {top_kinds}.")
    if relations:
        top_relations = ", ".join(f"{relation} x{count}" for relation, count in relations.most_common(2))
        responsibilities.append(f"Internal relations: {top_relations}.")
    if interface_count:
        responsibilities.append(f"Exposes {interface_count} interface candidate{'s' if interface_count != 1 else ''}.")
    return responsibilities[:3]


def _subsystem_internal_signals(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    relation_counts = Counter(str(edge.get("relation", "")) for edge in edges if edge.get("relation"))
    labels = [str(node.get("label", node["id"])) for node in sorted(nodes, key=_node_sort_key) if _is_symbol_node(node)]
    signals = [f"{relation}:{count}" for relation, count in relation_counts.most_common(3)]
    signals.extend(labels[:2])
    return signals[:4]


def _is_interface_candidate(node: dict[str, Any], source_tags: set[str], degree: int, subsystem_kind: str) -> tuple[bool, str, str]:
    label = str(node.get("label", "")).lower()
    source_file = str(node.get("source_file", "")).lower()
    text = f"{label} {source_file}"

    if "entrypoint" in source_tags or Path(source_file).name in _ENTRYPOINT_BASENAMES:
        return True, "entrypoint", "high"
    if any(keyword in text for keyword in _INTERFACE_KEYWORDS["cli"]):
        return True, "cli", "medium" if degree < 2 else "high"
    if "route" in source_tags or any(keyword in text for keyword in _INTERFACE_KEYWORDS["route"]):
        return True, "route", "high"
    if subsystem_kind == "data_layer" or "database" in source_tags or any(keyword in text for keyword in _INTERFACE_KEYWORDS["database"]):
        return True, "database", "medium"
    if degree >= 2 and any(keyword in text for keyword in _INTERFACE_KEYWORDS["service"]):
        return True, "service", "medium"
    return False, "", "low"


def _format_confidence(label: str) -> str:
    return label.upper()


def _evidence_snippets(
    evidence: dict[str, dict[str, Any]],
    node_ids: list[str],
    edge_refs: list[str],
    limit: int = 3,
) -> list[str]:
    snippets: list[str] = []
    for node_id in node_ids:
        entry = evidence.get(_node_ref(node_id))
        if not entry:
            continue
        label = entry.get("label", node_id)
        source_file = entry.get("source_file", "")
        snippets.append(f"{source_file}:{label}" if source_file else str(label))
        if len(snippets) >= limit:
            return snippets
    for edge_ref in edge_refs:
        entry = evidence.get(edge_ref)
        if not entry:
            continue
        source_file = entry.get("source_file", "")
        relation = entry.get("relation", "")
        snippets.append(f"{source_file}:{relation}" if source_file else str(relation))
        if len(snippets) >= limit:
            return snippets
    return snippets


def _build_summary_counts(context: dict[str, Any]) -> dict[str, int]:
    return {
        "subsystemCount": len(context["subsystems"]),
        "interfaceCount": len(context["interfaces"]),
        "dataFlowCount": len(context["data_flows"]),
        "crossCuttingConcernCount": len(context["cross_cutting_concerns"]),
        "entrypointCount": len(context["key_entrypoints"]),
        "externalDependencyCount": len(context["external_dependencies"]),
        "openQuestionCount": len(context["open_questions"]),
    }


def render_architecture_context_markdown(context: dict[str, Any]) -> str:
    evidence = context["evidence"]
    lines = ["# Architecture Context", ""]

    system = context["system"]
    lines.extend(
        [
            "## System",
            "",
            f"- Project: `{system['project_name']}`",
            f"- Target Path: `{system['target_path']}`",
            f"- Dominant Directories: {', '.join(f'`{item}`' for item in system['dominant_top_level_directories']) or '`none`'}",
            f"- Dependency Shape: {system['dependency_shape']}",
            f"- Summary: {system['summary']}",
            "",
        ]
    )

    lines.extend(["## Subsystem Inventory", ""])
    for subsystem in context["subsystems"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, subsystem["evidence_node_ids"], subsystem["evidence_edge_refs"]))
        lines.append(f"### {subsystem['name']} [{_format_confidence(subsystem['confidence'])}]")
        lines.append("")
        lines.append(f"- Kind: `{subsystem['kind']}`")
        lines.append(f"- Summary: {subsystem['summary']}")
        lines.append(f"- Paths: {', '.join(f'`{path}`' for path in subsystem['source_paths']) or '`none`'}")
        lines.append(f"- Key Symbols: {', '.join(f'`{symbol}`' for symbol in subsystem['key_symbols']) or '`none`'}")
        lines.append(f"- Depends On: {', '.join(f'`{item}`' for item in subsystem['depends_on']) or '`none`'}")
        lines.append(f"- Depended On By: {', '.join(f'`{item}`' for item in subsystem['depended_on_by']) or '`none`'}")
        lines.append(f"- Responsibilities: {'; '.join(subsystem['responsibilities']) or 'none'}")
        lines.append(f"- Evidence: {evidence_refs or 'none'}")
        lines.append("")

    lines.extend(["## Interfaces", ""])
    for interface in context["interfaces"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, interface["evidence_node_ids"], interface["evidence_edge_refs"]))
        lines.append(f"- `{interface['name']}` [{_format_confidence(interface['confidence'])}] in `{interface['subsystem_id']}` as `{interface['kind']}` from `{interface['source_path']}`.")
        lines.append(f"  Evidence: {evidence_refs or 'none'}")
    lines.append("")

    lines.extend(["## Key Flows", ""])
    for flow in context["data_flows"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, [], flow["evidence_edge_refs"]))
        lines.append(
            f"- `{flow['source_subsystem_id']}` -> `{flow['target_subsystem_id']}` [{_format_confidence(flow['confidence'])}] "
            f"via `{flow['relation']}`: {flow['summary']} Evidence: {evidence_refs or 'none'}"
        )
    lines.append("")

    lines.extend(["## Cross-Cutting Concerns", ""])
    for concern in context["cross_cutting_concerns"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, concern["evidence_node_ids"], concern["evidence_edge_refs"]))
        lines.append(
            f"- `{concern['name']}` [{_format_confidence(concern['confidence'])}] touches "
            f"{', '.join(f'`{item}`' for item in concern['subsystem_ids'])}: {concern['summary']} Evidence: {evidence_refs or 'none'}"
        )
    lines.append("")

    lines.extend(["## Entrypoints", ""])
    for entrypoint in context["key_entrypoints"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, entrypoint["evidence_node_ids"], entrypoint["evidence_edge_refs"]))
        lines.append(
            f"- `{entrypoint['name']}` [{_format_confidence(entrypoint['confidence'])}] from `{entrypoint['source_path']}` "
            f"in `{entrypoint['subsystem_id']}`. {entrypoint['summary']} Evidence: {evidence_refs or 'none'}"
        )
    lines.append("")

    lines.extend(["## External Dependencies", ""])
    for dependency in context["external_dependencies"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, dependency["evidence_node_ids"], dependency["evidence_edge_refs"]))
        lines.append(
            f"- `{dependency['name']}` [{_format_confidence(dependency['confidence'])}] used by "
            f"{', '.join(f'`{item}`' for item in dependency['used_by_subsystems']) or '`none`'} from "
            f"{', '.join(f'`{path}`' for path in dependency['source_paths']) or '`none`'}. Evidence: {evidence_refs or 'none'}"
        )
    lines.append("")

    lines.extend(["## Open Questions", ""])
    for question in context["open_questions"]:
        evidence_refs = ", ".join(_evidence_snippets(evidence, question["evidence_node_ids"], question["evidence_edge_refs"]))
        lines.append(
            f"- {_format_confidence(question['confidence'])}: {question['question']} "
            f"Why: {question['why']} Evidence: {evidence_refs or 'none'}"
        )
    lines.append("")

    return "\n".join(lines)


def build_architecture_context(
    graph: dict[str, Any],
    analysis: dict[str, Any],
    detection: dict[str, Any],
    extraction_summary: dict[str, Any],
    semantic_summary: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    nodes = sorted(graph.get("nodes", []), key=_node_sort_key)
    code_nodes = [node for node in nodes if not _is_doc_node(node)]
    edges = sorted(graph.get("edges", []), key=_edge_sort_key)
    node_index = {node["id"]: node for node in nodes}
    adjacency = _build_adjacency(graph)
    degrees = {node_id: len(neighbors) for node_id, neighbors in adjacency.items()}
    file_tags = {
        item["path"]: set(item.get("architectureTags", []))
        for item in detection.get("inventory", [])
        if isinstance(item, dict) and item.get("path")
    }

    evidence: dict[str, dict[str, Any]] = {}
    for node in nodes:
        evidence[_node_ref(node["id"])] = {
            "type": "node",
            "id": node["id"],
            "label": node.get("label", node["id"]),
            "kind": node.get("kind", ""),
            "source_file": node.get("source_file", ""),
            "source_location": node.get("source_location"),
        }
        source_file = str(node.get("source_file", ""))
        if source_file and _file_ref(source_file) not in evidence:
            evidence[_file_ref(source_file)] = {"type": "file", "path": source_file}
    for edge in edges:
        edge_key = _edge_ref(edge)
        evidence[edge_key] = {
            "type": "edge",
            "source": edge.get("source", ""),
            "target": edge.get("target", ""),
            "relation": edge.get("relation", ""),
            "confidence": edge.get("confidence", ""),
            "source_file": edge.get("source_file", ""),
            "source_location": edge.get("source_location"),
        }

    subsystem_records: list[dict[str, Any]] = []
    subsystem_node_to_id: dict[str, str] = {}

    for community_key in sorted(graph.get("communities", {}), key=lambda value: int(value)):
        community_id = int(community_key)
        member_ids = graph["communities"][community_key].get("nodes", [])
        members = [node_index[node_id] for node_id in member_ids if node_id in node_index and not _is_doc_node(node_index[node_id])]
        if not members:
            continue
        groups = _group_nodes_into_subsystems(community_id, members, edges)
        for group_index, group in enumerate(groups):
            source_paths = sorted({str(node.get("source_file", "")) for node in group if node.get("source_file")})
            name = _subsystem_name(source_paths, [str(node.get("label", node["id"])) for node in group if _is_symbol_node(node)])
            subsystem_id = f"subsystem-{community_id}-{group_index}-{_slug(name)}"
            group_node_ids = {node["id"] for node in group}
            related_edges = [
                edge
                for edge in edges
                if edge.get("source") in group_node_ids or edge.get("target") in group_node_ids
            ]
            internal_edges = [
                edge for edge in related_edges if edge.get("source") in group_node_ids and edge.get("target") in group_node_ids
            ]
            ambiguous_edges = sum(1 for edge in related_edges if str(edge.get("confidence", "")) == "AMBIGUOUS")
            kind = _subsystem_kind(group, source_paths, related_edges)
            confidence = _subsystem_confidence(group, source_paths, ambiguous_edges)
            subsystem_records.append(
                {
                    "community_id": community_id,
                    "group_index": group_index,
                    "id": subsystem_id,
                    "name": name,
                    "kind": kind,
                    "nodes": sorted(group, key=_node_sort_key),
                    "source_paths": source_paths,
                    "summary": _subsystem_summary(name, kind, source_paths, group, related_edges),
                    "confidence": confidence,
                    "internal_edges": sorted(internal_edges, key=_edge_sort_key),
                    "related_edges": sorted(related_edges, key=_edge_sort_key),
                }
            )
            for node in group:
                subsystem_node_to_id[node["id"]] = subsystem_id

    subsystem_records.sort(key=lambda item: (item["community_id"], item["group_index"], item["id"]))

    dependency_edges: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    incoming_map: dict[str, set[str]] = defaultdict(set)
    outgoing_map: dict[str, set[str]] = defaultdict(set)
    interfaces: list[dict[str, Any]] = []
    entrypoints: list[dict[str, Any]] = []

    for record in subsystem_records:
        subsystem_id = record["id"]
        group_node_ids = {node["id"] for node in record["nodes"]}
        public_interface_ids: list[str] = []
        for node in record["nodes"]:
            source_path = str(node.get("source_file", ""))
            tags = file_tags.get(source_path, set())
            is_interface, interface_kind, interface_confidence = _is_interface_candidate(
                node=node,
                source_tags=tags,
                degree=degrees.get(node["id"], 0),
                subsystem_kind=record["kind"],
            )
            if not is_interface:
                continue
            interface_id = f"interface-{_slug(subsystem_id)}-{_slug(str(node.get('label', node['id'])))}-{interface_kind}"
            interface = {
                "id": interface_id,
                "name": str(node.get("label", node["id"])),
                "kind": interface_kind,
                "subsystem_id": subsystem_id,
                "source_path": source_path,
                "symbol": str(node.get("label", node["id"])),
                "summary": f"{node.get('label', node['id'])} appears to be a {interface_kind} boundary for {record['name']}.",
                "evidence_node_ids": [node["id"]],
                "evidence_edge_refs": sorted(
                    {_edge_ref(edge) for edge in record["related_edges"] if edge.get("source") == node["id"] or edge.get("target") == node["id"]}
                ),
                "confidence": interface_confidence,
            }
            interfaces.append(interface)
            public_interface_ids.append(interface_id)

            source_name = Path(source_path).name.lower()
            if interface_kind in {"entrypoint", "cli", "route"} or source_name in _ENTRYPOINT_BASENAMES:
                entrypoints.append(
                    {
                        "id": f"entrypoint-{_slug(interface_id)}",
                        "name": interface["name"],
                        "kind": interface_kind,
                        "subsystem_id": subsystem_id,
                        "source_path": source_path,
                        "summary": f"Ranked as an entrypoint because it is tagged or named like a runtime root and has degree {degrees.get(node['id'], 0)}.",
                        "evidence_node_ids": [node["id"]],
                        "evidence_edge_refs": interface["evidence_edge_refs"],
                        "confidence": "high" if interface_kind == "entrypoint" else interface_confidence,
                    }
                )

        record["public_interface_ids"] = sorted(public_interface_ids)
        record["key_symbols"] = [
            str(node.get("label", node["id"]))
            for node in sorted(
                (node for node in record["nodes"] if _is_symbol_node(node)),
                key=lambda node: (-degrees.get(node["id"], 0), _node_sort_key(node)),
            )[:5]
        ]

    for edge in edges:
        source_subsystem = subsystem_node_to_id.get(str(edge.get("source", "")))
        target_subsystem = subsystem_node_to_id.get(str(edge.get("target", "")))
        if not source_subsystem or not target_subsystem or source_subsystem == target_subsystem:
            continue
        dependency_edges[(source_subsystem, target_subsystem)].append(edge)
        outgoing_map[source_subsystem].add(target_subsystem)
        incoming_map[target_subsystem].add(source_subsystem)

    data_flows: list[dict[str, Any]] = []
    for (source_subsystem, target_subsystem), bundled_edges in sorted(dependency_edges.items()):
        relation_counts = Counter(str(edge.get("relation", "")) for edge in bundled_edges if edge.get("relation"))
        relation = sorted(relation_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if relation_counts else "depends_on"
        confidence_counts = Counter(_CONFIDENCE_LABEL_BY_EDGE.get(str(edge.get("confidence", "")), "medium") for edge in bundled_edges)
        confidence = sorted(confidence_counts.items(), key=lambda item: (_confidence_rank(item[0]), -item[1]))[0][0]
        summary = ", ".join(f"{name} x{count}" for name, count in relation_counts.most_common(2)) or "cross-subsystem structural link"
        data_flows.append(
            {
                "source_subsystem_id": source_subsystem,
                "target_subsystem_id": target_subsystem,
                "relation": relation,
                "summary": summary,
                "evidence_edge_refs": sorted(_edge_ref(edge) for edge in bundled_edges),
                "confidence": confidence,
            }
        )

    data_flows.sort(
        key=lambda item: (
            item["source_subsystem_id"],
            item["target_subsystem_id"],
            item["relation"],
        )
    )

    concerns: list[dict[str, Any]] = []
    for concern_name, keywords in sorted(_CONCERN_KEYWORDS.items()):
        matching_nodes = [node for node in nodes if any(keyword in _node_keywords(node) for keyword in keywords)]
        subsystem_ids = sorted({subsystem_node_to_id.get(node["id"], "") for node in matching_nodes if subsystem_node_to_id.get(node["id"], "")})
        if len(subsystem_ids) < 2:
            continue
        concern_edges = sorted(
            {
                _edge_ref(edge)
                for edge in edges
                if edge.get("source") in {node["id"] for node in matching_nodes} or edge.get("target") in {node["id"] for node in matching_nodes}
            }
        )
        concerns.append(
            {
                "id": f"concern-{concern_name}",
                "name": concern_name,
                "summary": f"{concern_name} signals appear across {len(subsystem_ids)} subsystems via {len(matching_nodes)} matched nodes.",
                "subsystem_ids": subsystem_ids,
                "evidence_node_ids": sorted(node["id"] for node in matching_nodes),
                "evidence_edge_refs": concern_edges,
                "confidence": "high" if len(subsystem_ids) >= 3 else "medium",
            }
        )

    external_dependencies: list[dict[str, Any]] = []
    dependency_nodes = [
        node for node in code_nodes if str(node.get("kind", "")) in {"import_reference", "call_reference"}
    ]
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in dependency_nodes:
        by_label[str(node.get("label", node["id"]))].append(node)

    for label, dependency_group in sorted(by_label.items()):
        used_by = sorted({subsystem_node_to_id.get(node["id"], "") for node in dependency_group if subsystem_node_to_id.get(node["id"], "")})
        if not used_by:
            continue
        dependency_edge_refs = sorted(
            {
                _edge_ref(edge)
                for edge in edges
                if edge.get("source") in {node["id"] for node in dependency_group} or edge.get("target") in {node["id"] for node in dependency_group}
            }
        )
        external_dependencies.append(
            {
                "id": f"external-{_slug(label)}",
                "name": label,
                "kind": dependency_group[0].get("kind", "reference"),
                "source_paths": sorted({str(node.get("source_file", "")) for node in dependency_group if node.get("source_file")}),
                "used_by_subsystems": used_by,
                "evidence_node_ids": sorted(node["id"] for node in dependency_group),
                "evidence_edge_refs": dependency_edge_refs,
                "confidence": "medium" if len(used_by) > 1 else "low",
            }
        )

    open_questions: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    for record in subsystem_records:
        prefix_counts = Counter(_meaningful_prefix(path) for path in record["source_paths"])
        if len(prefix_counts) > 1 or record["confidence"] == "low":
            question = f"Should `{record['name']}` stay grouped as one subsystem?"
            if question not in seen_questions:
                seen_questions.add(question)
                open_questions.append(
                    {
                        "id": f"question-{_slug(record['id'])}-grouping",
                        "question": question,
                        "why": "Its membership spans multiple path prefixes or relies on low-confidence evidence.",
                        "related_subsystems": [record["id"]],
                        "evidence_node_ids": [node["id"] for node in record["nodes"][:4]],
                        "evidence_edge_refs": sorted(_edge_ref(edge) for edge in record["related_edges"][:4]),
                        "confidence": "low",
                    }
                )

    for flow in data_flows:
        if flow["confidence"] != "low":
            continue
        question = (
            f"Does `{flow['source_subsystem_id']}` really depend on `{flow['target_subsystem_id']}` "
            f"through `{flow['relation']}`?"
        )
        if question in seen_questions:
            continue
        seen_questions.add(question)
        open_questions.append(
            {
                "id": f"question-{_slug(flow['source_subsystem_id'])}-{_slug(flow['target_subsystem_id'])}-flow",
                "question": question,
                "why": "The strongest cross-subsystem signal is backed by ambiguous or sparse evidence.",
                "related_subsystems": [flow["source_subsystem_id"], flow["target_subsystem_id"]],
                "evidence_node_ids": [],
                "evidence_edge_refs": flow["evidence_edge_refs"][:4],
                "confidence": "low",
            }
        )

    for suggested in analysis.get("suggestedQuestions", []):
        question = str(suggested.get("question", "")).strip()
        if not question or question in seen_questions:
            continue
        seen_questions.add(question)
        related_subsystems = sorted(
            {
                subsystem_node_to_id.get(item.get("id", ""), "")
                for item in analysis.get("godNodes", [])
                if subsystem_node_to_id.get(item.get("id", ""), "")
            }
        )
        open_questions.append(
            {
                "id": f"question-{_slug(question)}",
                "question": question,
                "why": str(suggested.get("why", "Derived from Phase 4 analysis signals.")),
                "related_subsystems": related_subsystems[:2],
                "evidence_node_ids": [
                    item["id"]
                    for item in analysis.get("godNodes", [])[:2]
                    if item.get("id") in subsystem_node_to_id
                ],
                "evidence_edge_refs": [],
                "confidence": "low",
            }
        )

    subsystems: list[dict[str, Any]] = []
    for record in subsystem_records:
        subsystem_id = record["id"]
        subsystems.append(
            {
                "id": subsystem_id,
                "name": record["name"],
                "summary": record["summary"],
                "kind": record["kind"],
                "source_paths": record["source_paths"],
                "key_symbols": record["key_symbols"],
                "responsibilities": _subsystem_responsibilities(
                    record["nodes"],
                    record["internal_edges"],
                    len(record["public_interface_ids"]),
                ),
                "depends_on": sorted(outgoing_map.get(subsystem_id, set())),
                "depended_on_by": sorted(incoming_map.get(subsystem_id, set())),
                "public_interfaces": record["public_interface_ids"],
                "internal_signals": _subsystem_internal_signals(record["nodes"], record["internal_edges"]),
                "evidence_node_ids": [node["id"] for node in record["nodes"]],
                "evidence_edge_refs": sorted(_edge_ref(edge) for edge in record["related_edges"]),
                "doc_evidence_node_ids": [],
                "doc_rationale_snippets": [],
                "confidence": record["confidence"],
            }
        )

    doc_nodes = [node for node in nodes if _is_doc_node(node)]
    doc_node_ids = {node["id"] for node in doc_nodes}
    doc_support_by_target: dict[str, set[str]] = defaultdict(set)
    doc_paths_by_target: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("relation") != "references":
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in doc_node_ids:
            continue
        doc_support_by_target[target].add(source)
        if edge.get("source_file"):
            doc_paths_by_target[target].add(str(edge.get("source_file")))

    subsystem_doc_support: dict[str, set[str]] = defaultdict(set)
    subsystem_doc_paths: dict[str, set[str]] = defaultdict(set)
    interface_doc_support: dict[str, set[str]] = defaultdict(set)
    for subsystem in subsystems:
        source_paths = set(subsystem["source_paths"])
        for node_id in subsystem["evidence_node_ids"]:
            subsystem_doc_support[subsystem["id"]].update(doc_support_by_target.get(node_id, set()))
            subsystem_doc_paths[subsystem["id"]].update(doc_paths_by_target.get(node_id, set()))
        for node in code_nodes:
            if str(node.get("source_file", "")) in source_paths:
                subsystem_doc_support[subsystem["id"]].update(doc_support_by_target.get(node["id"], set()))
                subsystem_doc_paths[subsystem["id"]].update(doc_paths_by_target.get(node["id"], set()))
        subsystem["doc_evidence_node_ids"] = sorted(subsystem_doc_support[subsystem["id"]])
        subsystem["doc_rationale_snippets"] = [
            f"{node_index[node_id].get('source_file', '')}:{node_index[node_id].get('label', node_id)}"
            for node_id in subsystem["doc_evidence_node_ids"][:4]
            if node_id in node_index
        ]

    for interface in interfaces:
        doc_nodes_for_interface = set()
        for node_id in interface["evidence_node_ids"]:
            doc_nodes_for_interface.update(doc_support_by_target.get(node_id, set()))
        interface_doc_support[interface["id"]] = doc_nodes_for_interface
        interface["doc_evidence_node_ids"] = sorted(doc_nodes_for_interface)

    dominant_dirs = [
        item
        for item, _ in Counter(
            _top_level_dir(path)
            for subsystem in subsystems
            for path in subsystem["source_paths"]
        ).most_common(5)
    ]
    cross_dependency_count = len(data_flows)
    unresolved_dependency_count = len(external_dependencies)
    project_name = Path(target_path).resolve().name
    system_summary = (
        f"{project_name} contains {len(subsystems)} subsystem{'s' if len(subsystems) != 1 else ''}, "
        f"{cross_dependency_count} cross-subsystem flow{'s' if cross_dependency_count != 1 else ''}, "
        f"{semantic_summary.get('processedDocumentCount', 0)} processed document{'s' if semantic_summary.get('processedDocumentCount', 0) != 1 else ''}, "
        f"and {unresolved_dependency_count} external dependenc{'ies' if unresolved_dependency_count != 1 else 'y'} "
        f"derived from {extraction_summary.get('nodeCount', 0)} extracted code nodes."
    )

    for flow in data_flows:
        source_doc_nodes = subsystem_doc_support.get(flow["source_subsystem_id"], set())
        target_doc_nodes = subsystem_doc_support.get(flow["target_subsystem_id"], set())
        shared_doc_nodes = sorted(source_doc_nodes & target_doc_nodes)
        flow["evidence_node_ids"] = shared_doc_nodes[:4]
        flow["doc_rationale_snippets"] = [
            f"{node_index[node_id].get('source_file', '')}:{node_index[node_id].get('label', node_id)}"
            for node_id in shared_doc_nodes[:3]
            if node_id in node_index
        ]

    for question in open_questions:
        related = question.get("related_subsystems", [])
        doc_candidates = set()
        for subsystem_id in related:
            doc_candidates.update(subsystem_doc_support.get(subsystem_id, set()))
        for node_id in sorted(doc_candidates):
            if node_id not in question["evidence_node_ids"]:
                question["evidence_node_ids"].append(node_id)
        question["evidence_node_ids"] = question["evidence_node_ids"][:6]

    context = {
        "system": {
            "project_name": project_name,
            "target_path": str(Path(target_path).resolve()),
            "dominant_top_level_directories": dominant_dirs,
            "dependency_shape": (
                f"{cross_dependency_count} subsystem links, "
                f"{analysis.get('ambiguitySummary', {}).get('ambiguousEdgeCount', 0)} ambiguous edges, "
                f"{detection.get('totals', {}).get('byArchitectureTag', {}).get('entrypoint', 0)} tagged entrypoints, "
                f"{semantic_summary.get('processedDocumentCount', 0)} enriched docs"
            ),
            "summary": system_summary,
        },
        "subsystems": subsystems,
        "interfaces": sorted(
            interfaces,
            key=lambda item: (item["subsystem_id"], _confidence_rank(item["confidence"]), item["name"], item["id"]),
        ),
        "data_flows": data_flows,
        "cross_cutting_concerns": sorted(concerns, key=lambda item: (_confidence_rank(item["confidence"]), item["name"])),
        "key_entrypoints": sorted(
            entrypoints,
            key=lambda item: (_confidence_rank(item["confidence"]), item["subsystem_id"], item["name"], item["id"]),
        ),
        "external_dependencies": sorted(
            external_dependencies,
            key=lambda item: (_confidence_rank(item["confidence"]), item["name"], item["id"]),
        ),
        "evidence": dict(sorted(evidence.items())),
        "open_questions": sorted(open_questions, key=lambda item: (item["question"], item["id"])),
    }
    context["summary"] = _build_summary_counts(context)
    context["summary"]["docEvidenceSubsystemCount"] = sum(1 for subsystem in subsystems if subsystem["doc_evidence_node_ids"])
    context["summary"]["processedDocumentCount"] = int(semantic_summary.get("processedDocumentCount", 0))
    context["markdown"] = render_architecture_context_markdown(context)
    return context

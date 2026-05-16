"""Phase 6 structured architecture artifact builders."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
_EDGE_TO_LEVEL = {"EXTRACTED": "confirmed", "INFERRED": "inferred", "AMBIGUOUS": "inferred"}
_KIND_TO_SERVICE_TYPE = {
    "service": "service",
    "adapter": "adapter",
    "infrastructure": "adapter",
    "data_layer": "data_access",
    "shared_library": "shared_library",
    "domain": "service",
    "ui": "entry_surface",
    "module": "module",
}
_ROUTE_HINTS = ("route", "router", "api", "handler", "controller", "endpoint")
_JOB_HINTS = ("worker", "job", "queue", "task", "cron", "scheduler", "consumer")
_DOC_NAMES = {"readme.md", "architecture.md", "design.md", "archify.md", "adr.md"}


def _is_readme_like_doc(path: str) -> bool:
    name = Path(path).name.lower()
    if name in {"readme.md", "readme.mdx"}:
        return True
    if Path(path).parent == Path(".") and name in {"architecture.md", "design.md", "archify.md", "adr.md"}:
        return True
    return False


def _confidence_rank(value: str) -> int:
    return _CONFIDENCE_ORDER.get(value, 99)


def _location_suffix(location: dict[str, Any] | None) -> str:
    if not location:
        return ""
    line = location.get("line")
    column = location.get("column")
    if line is None:
        return ""
    if column is None:
        return f":{line}"
    return f":{line}:{column}"


def _node_ref(node_id: str) -> str:
    return f"node:{node_id}"


def _edge_ref(edge: dict[str, Any]) -> str:
    location = edge.get("source_location", {}) or {}
    return (
        f"edge:{edge.get('source', '')}:{edge.get('relation', '')}:{edge.get('target', '')}:"
        f"{edge.get('source_file', '')}:{location.get('line', 0)}:{location.get('column', 0)}"
    )


def _sort_evidence(refs: list[str]) -> list[str]:
    return sorted({ref for ref in refs if ref})


def _artifact_base(name: str, *, target_path: str, scan_root: str) -> dict[str, Any]:
    return {
        "artifact": name,
        "status": "ready",
        "phase": "analyze",
        "targetPath": target_path,
        "scanRoot": scan_root,
    }


def _finding_id(prefix: str, parts: list[str]) -> str:
    cleaned = "_".join(
        "".join(character.lower() if character.isalnum() else "_" for character in part).strip("_")
        for part in parts
        if part
    )
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return f"{prefix}:{cleaned or 'item'}"


def _record_confidence(kind: str, confidence: str) -> str:
    if kind == "confirmed":
        return "high"
    return confidence if confidence in {"high", "medium", "low"} else "medium"


def _evidence_index(context: dict[str, Any], extra_files: list[str]) -> dict[str, dict[str, Any]]:
    evidence = dict(context.get("evidence", {}))
    for path in extra_files:
        key = f"file:{path}"
        evidence.setdefault(key, {"type": "file", "path": path})
    return dict(sorted(evidence.items()))


def _build_facts(
    *,
    detection: dict[str, Any],
    extraction_summary: dict[str, Any],
    graph: dict[str, Any],
    analysis: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    confirmed: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []

    for subsystem in context.get("subsystems", []):
        evidence_refs = _sort_evidence(
            [_node_ref(node_id) for node_id in subsystem.get("evidence_node_ids", [])]
            + subsystem.get("evidence_edge_refs", [])
        )
        record = {
            "id": _finding_id("fact", ["subsystem", subsystem["id"]]),
            "category": "subsystem",
            "statement": f"{subsystem['name']} is a detected {subsystem['kind']} subsystem.",
            "kind": "confirmed",
            "confidence": "high",
            "evidence": evidence_refs,
        }
        confirmed.append(record)

    for entrypoint in context.get("key_entrypoints", []):
        evidence_refs = _sort_evidence(
            [_node_ref(node_id) for node_id in entrypoint.get("evidence_node_ids", [])]
            + entrypoint.get("evidence_edge_refs", [])
        )
        confirmed.append(
            {
                "id": _finding_id("fact", ["entrypoint", entrypoint["id"]]),
                "category": "entrypoint",
                "statement": f"{entrypoint['name']} is a detected {entrypoint['kind']} entrypoint in {entrypoint['source_path']}.",
                "kind": "confirmed",
                "confidence": "high" if entrypoint.get("confidence") == "high" else "medium",
                "evidence": evidence_refs,
            }
        )

    for flow in context.get("data_flows", []):
        evidence_refs = _sort_evidence(flow.get("evidence_edge_refs", []))
        inferred.append(
            {
                "id": _finding_id("fact", ["flow", flow["source_subsystem_id"], flow["target_subsystem_id"], flow["relation"]]),
                "category": "data_flow",
                "statement": (
                    f"{flow['source_subsystem_id']} depends on {flow['target_subsystem_id']} via {flow['relation']}."
                ),
                "kind": "inferred",
                "confidence": _record_confidence("inferred", flow.get("confidence", "medium")),
                "evidence": evidence_refs,
            }
        )

    for question in context.get("open_questions", []):
        evidence_refs = _sort_evidence(
            [_node_ref(node_id) for node_id in question.get("evidence_node_ids", [])]
            + question.get("evidence_edge_refs", [])
        )
        inferred.append(
            {
                "id": _finding_id("fact", ["question", question["id"]]),
                "category": "open_question",
                "statement": question["question"],
                "kind": "inferred",
                "confidence": _record_confidence("inferred", question.get("confidence", "low")),
                "evidence": evidence_refs,
            }
        )

    payload = _artifact_base("facts.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "confirmedFindings": sorted(confirmed, key=lambda item: (item["category"], item["statement"], item["id"])),
            "inferredFindings": sorted(inferred, key=lambda item: (_confidence_rank(item["confidence"]), item["category"], item["statement"])),
            "totals": detection.get("totals", {}),
            "extractionCandidates": detection.get("extractionCandidates", []),
            "skipped": detection.get("skipped", {}),
            "ignorePatternCount": detection.get("ignorePatternCount", 0),
            "warning": detection.get("warning"),
            "inventory": detection.get("inventory", []),
            "extractionSummary": extraction_summary,
            "graphSummary": {
                "nodeCount": len(graph.get("nodes", [])),
                "edgeCount": len(graph.get("edges", [])),
                "hyperedgeCount": len(graph.get("hyperedges", [])),
                "communityCount": graph.get("clustering", {}).get("communityCount", 0),
                "warningCount": len(graph.get("warnings", [])),
            },
            "dedupSummary": graph.get("dedup", {}),
            "clusteringSummary": graph.get("clustering", {}),
            "analysis": analysis,
            "architectureContextSummary": context.get("summary", {}),
            "summary": {
                "confirmedCount": len(confirmed),
                "inferredCount": len(inferred),
                "subsystemCount": len(context.get("subsystems", [])),
                "entrypointCount": len(context.get("key_entrypoints", [])),
                "nodeCount": len(graph.get("nodes", [])),
                "edgeCount": len(graph.get("edges", [])),
                "ambiguousEdgeCount": analysis.get("ambiguitySummary", {}).get("ambiguousEdgeCount", 0),
                "extractedFileCount": extraction_summary.get("extractedFiles", 0),
            },
            "evidenceIndex": _evidence_index(
                context,
                [item["path"] for item in detection.get("inventory", []) if isinstance(item, dict) and item.get("path")],
            ),
        }
    )
    return payload


def _build_modules(
    *,
    detection: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    subsystems = []
    for subsystem in context.get("subsystems", []):
        subsystems.append(
            {
                "id": subsystem["id"],
                "name": subsystem["name"],
                "kind": subsystem["kind"],
                "summary": subsystem["summary"],
                "confidence": subsystem["confidence"],
                "sourcePaths": subsystem.get("source_paths", []),
                "keySymbols": subsystem.get("key_symbols", []),
                "responsibilities": subsystem.get("responsibilities", []),
                "publicInterfaces": subsystem.get("public_interfaces", []),
                "dependsOn": subsystem.get("depends_on", []),
                "dependedOnBy": subsystem.get("depended_on_by", []),
                "evidence": _sort_evidence(
                    [_node_ref(node_id) for node_id in subsystem.get("evidence_node_ids", [])]
                    + subsystem.get("evidence_edge_refs", [])
                ),
            }
        )

    dependencies = [
        {
            "sourceModuleId": flow["source_subsystem_id"],
            "targetModuleId": flow["target_subsystem_id"],
            "relation": flow["relation"],
            "summary": flow["summary"],
            "confidence": flow["confidence"],
            "evidence": _sort_evidence(flow.get("evidence_edge_refs", [])),
        }
        for flow in context.get("data_flows", [])
    ]

    payload = _artifact_base("modules.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "modules": sorted(subsystems, key=lambda item: (item["name"], item["id"])),
            "dependencies": sorted(
                dependencies,
                key=lambda item: (_confidence_rank(item["confidence"]), item["sourceModuleId"], item["targetModuleId"], item["relation"]),
            ),
        }
    )
    return payload


def _build_routes(
    *,
    detection: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    confirmed: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []
    route_seen: set[tuple[str, str, str]] = set()

    for interface in context.get("interfaces", []):
        kind = interface.get("kind", "")
        source_path = interface.get("source_path", "")
        key = (interface["name"], kind, source_path)
        if key in route_seen:
            continue
        route_seen.add(key)
        base = {
            "id": _finding_id("route", [kind, source_path, interface["name"]]),
            "name": interface["name"],
            "entryType": "http" if kind == "route" else "cli",
            "boundaryKind": kind,
            "sourcePath": source_path,
            "subsystemId": interface["subsystem_id"],
            "summary": interface["summary"],
            "evidence": _sort_evidence(
                [_node_ref(node_id) for node_id in interface.get("evidence_node_ids", [])]
                + interface.get("evidence_edge_refs", [])
            ),
        }
        if kind in {"route", "cli", "entrypoint"}:
            confirmed.append({**base, "confidence": interface.get("confidence", "medium")})
        elif any(hint in interface["name"].lower() or hint in source_path.lower() for hint in _ROUTE_HINTS):
            inferred.append({**base, "confidence": interface.get("confidence", "medium")})

    for item in detection.get("inventory", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        tags = set(item.get("architectureTags", []))
        if not path:
            continue
        if "route" not in tags and "entrypoint" not in tags:
            continue
        if any(route["sourcePath"] == path for route in confirmed + inferred):
            continue
        route_kind = "route" if "route" in tags else "entrypoint"
        target = confirmed if route_kind == "entrypoint" else inferred
        target.append(
            {
                "id": _finding_id("route", [route_kind, path]),
                "name": Path(path).stem,
                "entryType": "cli" if route_kind == "entrypoint" else "http",
                "boundaryKind": route_kind,
                "sourcePath": path,
                "subsystemId": None,
                "summary": f"{path} is tagged as a {route_kind} file during repository detection.",
                "confidence": "high" if route_kind == "entrypoint" else "medium",
                "evidence": [f"file:{path}"],
            }
        )

    payload = _artifact_base("routes.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "confirmedRoutes": sorted(confirmed, key=lambda item: (_confidence_rank(item["confidence"]), item["sourcePath"], item["name"])),
            "inferredRoutes": sorted(inferred, key=lambda item: (_confidence_rank(item["confidence"]), item["sourcePath"], item["name"])),
        }
    )
    return payload


def _build_database(
    *,
    detection: dict[str, Any],
    graph: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    node_index = {node["id"]: node for node in graph.get("nodes", [])}
    tables = []
    for node in sorted(graph.get("nodes", []), key=lambda item: (item.get("source_file", ""), item.get("label", ""), item["id"])):
        if node.get("kind") != "sql_table":
            continue
        subsystem_ids = sorted(
            {
                subsystem["id"]
                for subsystem in context.get("subsystems", [])
                if node["id"] in set(subsystem.get("evidence_node_ids", []))
            }
        )
        tables.append(
            {
                "id": node["id"],
                "name": node.get("label", node["id"]),
                "sourcePath": node.get("source_file", ""),
                "subsystemIds": subsystem_ids,
                "evidence": [_node_ref(node["id"])],
            }
        )

    migrations = []
    boundaries = []
    database_paths: set[str] = set()
    migration_paths: set[str] = set()
    for item in detection.get("inventory", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        tags = set(item.get("architectureTags", []))
        if "database" in tags:
            database_paths.add(item["path"])
        if "migration" in tags:
            migration_paths.add(item["path"])
            migrations.append(
                {
                    "path": item["path"],
                    "fileType": item.get("fileType"),
                    "evidence": [f"file:{item['path']}"],
                }
            )

    for subsystem in context.get("subsystems", []):
        source_paths = set(subsystem.get("source_paths", []))
        matched_paths = sorted(source_paths & database_paths)
        matched_tables = [table["id"] for table in tables if table["sourcePath"] in source_paths]
        if not matched_paths and not matched_tables:
            continue
        boundaries.append(
            {
                "subsystemId": subsystem["id"],
                "paths": matched_paths,
                "tableIds": matched_tables,
                "summary": f"{subsystem['name']} owns or touches database-oriented code paths.",
                "confidence": "high" if matched_paths or matched_tables else "medium",
                "evidence": _sort_evidence(
                    [f"file:{path}" for path in matched_paths] + [_node_ref(table_id) for table_id in matched_tables]
                ),
            }
        )

    query_edges = []
    for edge in sorted(graph.get("edges", []), key=lambda item: (item.get("source_file", ""), item.get("relation", ""), item.get("source", ""), item.get("target", ""))):
        relation = str(edge.get("relation", ""))
        if relation not in {"queries", "writes", "updates", "deletes", "references", "defines"}:
            continue
        source = node_index.get(str(edge.get("source", "")), {})
        target = node_index.get(str(edge.get("target", "")), {})
        if source.get("kind") != "sql_table" and target.get("kind") != "sql_table":
            continue
        query_edges.append(
            {
                "relation": relation,
                "sourceId": edge.get("source", ""),
                "targetId": edge.get("target", ""),
                "sourcePath": edge.get("source_file", ""),
                "confidence": "high" if edge.get("confidence") == "EXTRACTED" else "medium",
                "evidence": [_edge_ref(edge)],
            }
        )

    payload = _artifact_base("database.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "tables": tables,
            "migrations": migrations,
            "accessBoundaries": sorted(boundaries, key=lambda item: (item["subsystemId"], item["summary"])),
            "querySignals": query_edges,
            "summary": {
                "tableCount": len(tables),
                "migrationCount": len(migrations),
                "boundaryCount": len(boundaries),
            },
        }
    )
    return payload


def _build_services(
    *,
    detection: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    services = []
    background_jobs = []
    integrations = []

    subsystem_names = {subsystem["id"]: subsystem["name"] for subsystem in context.get("subsystems", [])}
    for subsystem in context.get("subsystems", []):
        service_type = _KIND_TO_SERVICE_TYPE.get(subsystem.get("kind", "module"), "module")
        services.append(
            {
                "id": subsystem["id"],
                "name": subsystem["name"],
                "serviceType": service_type,
                "summary": subsystem["summary"],
                "sourcePaths": subsystem.get("source_paths", []),
                "publicInterfaces": subsystem.get("public_interfaces", []),
                "responsibilities": subsystem.get("responsibilities", []),
                "confidence": subsystem.get("confidence", "medium"),
                "evidence": _sort_evidence(
                    [_node_ref(node_id) for node_id in subsystem.get("evidence_node_ids", [])]
                    + subsystem.get("evidence_edge_refs", [])
                ),
            }
        )

    for interface in context.get("interfaces", []):
        name = interface["name"].lower()
        path = interface.get("source_path", "").lower()
        if any(hint in name or hint in path for hint in _JOB_HINTS):
            background_jobs.append(
                {
                    "id": interface["id"],
                    "name": interface["name"],
                    "subsystemId": interface["subsystem_id"],
                    "summary": interface["summary"],
                    "confidence": interface.get("confidence", "medium"),
                    "evidence": _sort_evidence(
                        [_node_ref(node_id) for node_id in interface.get("evidence_node_ids", [])]
                        + interface.get("evidence_edge_refs", [])
                    ),
                }
            )

    for dependency in context.get("external_dependencies", []):
        integrations.append(
            {
                "id": dependency["id"],
                "name": dependency["name"],
                "usedBySubsystems": dependency.get("used_by_subsystems", []),
                "usedBySubsystemNames": [subsystem_names[item] for item in dependency.get("used_by_subsystems", []) if item in subsystem_names],
                "sourcePaths": dependency.get("source_paths", []),
                "confidence": dependency.get("confidence", "low"),
                "evidence": _sort_evidence(
                    [_node_ref(node_id) for node_id in dependency.get("evidence_node_ids", [])]
                    + dependency.get("evidence_edge_refs", [])
                ),
            }
        )

    payload = _artifact_base("services.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "services": sorted(services, key=lambda item: (_confidence_rank(item["confidence"]), item["name"], item["id"])),
            "backgroundJobs": sorted(background_jobs, key=lambda item: (_confidence_rank(item["confidence"]), item["name"], item["id"])),
            "integrations": sorted(integrations, key=lambda item: (_confidence_rank(item["confidence"]), item["name"], item["id"])),
        }
    )
    return payload


def _manifest_dependencies(path: str) -> list[str]:
    if path.endswith("package.json"):
        return ["npm_manifest"]
    if path.endswith("pyproject.toml") or path.endswith("requirements.txt"):
        return ["python_manifest"]
    return ["manifest"]


def _build_dependencies(
    *,
    detection: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    internal = [
        {
            "sourceModuleId": flow["source_subsystem_id"],
            "targetModuleId": flow["target_subsystem_id"],
            "relation": flow["relation"],
            "summary": flow["summary"],
            "confidence": flow["confidence"],
            "evidence": _sort_evidence(flow.get("evidence_edge_refs", [])),
        }
        for flow in context.get("data_flows", [])
    ]

    external = [
        {
            "id": dependency["id"],
            "name": dependency["name"],
            "kind": dependency.get("kind", "reference"),
            "usedBySubsystems": dependency.get("used_by_subsystems", []),
            "sourcePaths": dependency.get("source_paths", []),
            "confidence": dependency.get("confidence", "low"),
            "evidence": _sort_evidence(
                [_node_ref(node_id) for node_id in dependency.get("evidence_node_ids", [])]
                + dependency.get("evidence_edge_refs", [])
            ),
        }
        for dependency in context.get("external_dependencies", [])
    ]

    manifests = []
    for item in detection.get("inventory", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        tags = set(item.get("architectureTags", []))
        if "dependency_manifest" not in tags:
            continue
        manifests.append(
            {
                "path": item["path"],
                "manifestType": _manifest_dependencies(item["path"])[0],
                "evidence": [f"file:{item['path']}"],
            }
        )

    hotspots = []
    outbound_counts = Counter(item["sourceModuleId"] for item in internal)
    inbound_counts = Counter(item["targetModuleId"] for item in internal)
    for module_id in sorted(set(outbound_counts) | set(inbound_counts)):
        hotspots.append(
            {
                "moduleId": module_id,
                "outboundCount": outbound_counts.get(module_id, 0),
                "inboundCount": inbound_counts.get(module_id, 0),
            }
        )

    payload = _artifact_base("dependencies.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "internalDependencies": sorted(
                internal,
                key=lambda item: (_confidence_rank(item["confidence"]), item["sourceModuleId"], item["targetModuleId"], item["relation"]),
            ),
            "externalDependencies": sorted(
                external,
                key=lambda item: (_confidence_rank(item["confidence"]), item["name"], item["id"]),
            ),
            "dependencyManifests": sorted(manifests, key=lambda item: item["path"]),
            "hotspots": sorted(hotspots, key=lambda item: (-item["outboundCount"], -item["inboundCount"], item["moduleId"])),
        }
    )
    return payload


def _build_docs_summary(
    *,
    detection: dict[str, Any],
    semantic: dict[str, Any],
    graph: dict[str, Any],
    context: dict[str, Any],
    target_path: str,
) -> dict[str, Any]:
    docs = []
    for item in detection.get("inventory", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        tags = set(item.get("architectureTags", []))
        if "docs" not in tags and Path(item["path"]).name.lower() not in _DOC_NAMES:
            continue
        docs.append(
            {
                "path": item["path"],
                "fileType": item.get("fileType"),
                "detectionReason": item.get("detectionReason"),
                "evidence": [f"file:{item['path']}"],
            }
        )

    if not semantic.get("enabled"):
        payload = _artifact_base("docs-summary.json", target_path=target_path, scan_root=detection["scanRoot"])
        payload.update(
            {
                "semantic": {
                    "enabled": False,
                    "backend": "none",
                    "providerEnrichmentSkipped": True,
                    "message": "Semantic enrichment is disabled. This summary preserves document provenance for downstream synthesis.",
                },
                "detectedDocs": sorted(docs, key=lambda item: item["path"]),
                "confirmedFacts": {
                    "processedDocuments": [],
                    "skippedDocuments": [],
                    "readmeLikeDocs": [item for item in sorted(docs, key=lambda item: item["path"]) if _is_readme_like_doc(item["path"])],
                },
                "inferredAlignments": {
                    "docToSubsystem": [],
                    "architectureThemes": [],
                    "unresolvedDocuments": [],
                },
                "summary": {
                    "detectedDocumentCount": len(docs),
                    "processedDocumentCount": 0,
                    "skippedDocumentCount": 0,
                    "alignedDocumentCount": 0,
                    "themeCount": 0,
                    "unresolvedDocumentCount": 0,
                },
            }
        )
        return payload

    node_index = {node["id"]: node for node in graph.get("nodes", [])}
    subsystem_lookup = {subsystem["id"]: subsystem for subsystem in context.get("subsystems", [])}
    subsystem_ids_by_node: dict[str, set[str]] = defaultdict(set)
    subsystem_ids_by_path: dict[str, set[str]] = defaultdict(set)
    for subsystem in context.get("subsystems", []):
        for node_id in subsystem.get("evidence_node_ids", []):
            subsystem_ids_by_node[node_id].add(subsystem["id"])
        for path in subsystem.get("source_paths", []):
            subsystem_ids_by_path[path].add(subsystem["id"])

    processed_documents = []
    skipped_documents = []
    doc_alignments = []
    unresolved_documents = []
    theme_index: dict[str, dict[str, Any]] = {}

    for document in semantic.get("documents", []):
        base_record = {
            "path": document["path"],
            "title": document["title"],
            "status": document["status"],
            "fileType": document.get("fileType"),
            "evidence": [f"file:{document['path']}"],
        }
        if document["status"] != "ready":
            skipped_documents.append({**base_record, "reason": document.get("reason")})
            unresolved_documents.append(
                {
                    "path": document["path"],
                    "reason": document.get("reason"),
                    "status": document["status"],
                    "notes": "Document was not available for deterministic extraction.",
                }
            )
            continue

        processed_documents.append(
            {
                **base_record,
                "extractionStatus": document["status"],
                "sections": document.get("sections", []),
                "references": document.get("references", []),
                "referenceCount": len(document.get("references", [])),
                "themes": document.get("themes", []),
                "rationaleSnippets": document.get("rationaleSnippets", []),
            }
        )

        alignment_map: dict[str, dict[str, Any]] = {}
        for reference in document.get("references", []):
            target_id = reference.get("targetId")
            target_node = node_index.get(str(target_id), {})
            subsystem_ids = set(subsystem_ids_by_node.get(str(target_id), set()))
            source_path = str(target_node.get("source_file", ""))
            if source_path:
                subsystem_ids.update(subsystem_ids_by_path.get(source_path, set()))
            for subsystem_id in sorted(subsystem_ids):
                alignment = alignment_map.setdefault(
                    subsystem_id,
                    {
                        "documentPath": document["path"],
                        "subsystemId": subsystem_id,
                        "subsystemName": subsystem_lookup[subsystem_id]["name"],
                        "confidence": "medium",
                        "evidence": set(),
                        "matchedReferences": [],
                        "rationaleSnippets": list(document.get("rationaleSnippets", [])[:2]),
                    },
                )
                alignment["evidence"].add(f"file:{document['path']}")
                alignment["evidence"].add(_node_ref(target_id))
                alignment["matchedReferences"].append(
                    {
                        "kind": reference.get("kind"),
                        "target": reference.get("target"),
                        "targetId": target_id,
                        "confidence": reference.get("confidence"),
                    }
                )
                if reference.get("confidence") == "EXTRACTED":
                    alignment["confidence"] = "high"

        if alignment_map:
            for alignment in sorted(alignment_map.values(), key=lambda item: (_confidence_rank(item["confidence"]), item["subsystemName"], item["subsystemId"])):
                doc_alignments.append(
                    {
                        **alignment,
                        "evidence": sorted(alignment["evidence"]),
                    }
                )
        else:
            unresolved_documents.append(
                {
                    "path": document["path"],
                    "reason": "no_subsystem_alignment",
                    "status": "ready",
                    "notes": "Document was processed, but it did not reference code evidence strongly enough to map to a subsystem.",
                }
            )

        for theme in document.get("themes", []):
            theme_record = theme_index.setdefault(
                theme,
                {
                    "theme": theme,
                    "documentPaths": set(),
                    "rationaleSnippets": [],
                    "evidence": set(),
                },
            )
            theme_record["documentPaths"].add(document["path"])
            theme_record["evidence"].add(f"file:{document['path']}")
            for snippet in document.get("rationaleSnippets", []):
                if snippet not in theme_record["rationaleSnippets"]:
                    theme_record["rationaleSnippets"].append(snippet)

    architecture_themes = []
    for item in sorted(theme_index.values(), key=lambda entry: entry["theme"]):
        architecture_themes.append(
            {
                "theme": item["theme"],
                "documentPaths": sorted(item["documentPaths"]),
                "rationaleSnippets": item["rationaleSnippets"][:4],
                "confidence": "high" if len(item["documentPaths"]) > 1 else "medium",
                "evidence": sorted(item["evidence"]),
            }
        )

    payload = _artifact_base("docs-summary.json", target_path=target_path, scan_root=detection["scanRoot"])
    payload.update(
        {
            "semantic": semantic.get("summary", {}),
            "detectedDocs": sorted(docs, key=lambda item: item["path"]),
            "confirmedFacts": {
                "processedDocuments": sorted(processed_documents, key=lambda item: item["path"]),
                "skippedDocuments": sorted(skipped_documents, key=lambda item: item["path"]),
                "readmeLikeDocs": [item for item in sorted(docs, key=lambda item: item["path"]) if _is_readme_like_doc(item["path"])],
            },
            "inferredAlignments": {
                "docToSubsystem": doc_alignments,
                "architectureThemes": architecture_themes,
                "unresolvedDocuments": sorted(unresolved_documents, key=lambda item: item["path"]),
            },
            "summary": {
                "detectedDocumentCount": len(docs),
                "processedDocumentCount": len(processed_documents),
                "skippedDocumentCount": len(skipped_documents),
                "alignedDocumentCount": len({item["documentPath"] for item in doc_alignments}),
                "themeCount": len(architecture_themes),
                "unresolvedDocumentCount": len(unresolved_documents),
            },
        }
    )
    return payload


def build_phase6_artifacts(
    *,
    detection: dict[str, Any],
    extraction_summary: dict[str, Any],
    semantic: dict[str, Any],
    graph: dict[str, Any],
    analysis: dict[str, Any],
    architecture_context: dict[str, Any],
    target_path: str,
) -> dict[str, dict[str, Any]]:
    return {
        "facts.json": _build_facts(
            detection=detection,
            extraction_summary=extraction_summary,
            graph=graph,
            analysis=analysis,
            context=architecture_context,
            target_path=target_path,
        ),
        "modules.json": _build_modules(detection=detection, context=architecture_context, target_path=target_path),
        "routes.json": _build_routes(detection=detection, context=architecture_context, target_path=target_path),
        "database.json": _build_database(
            detection=detection,
            graph=graph,
            context=architecture_context,
            target_path=target_path,
        ),
        "services.json": _build_services(detection=detection, context=architecture_context, target_path=target_path),
        "dependencies.json": _build_dependencies(detection=detection, context=architecture_context, target_path=target_path),
        "docs-summary.json": _build_docs_summary(
            detection=detection,
            semantic=semantic,
            graph=graph,
            context=architecture_context,
            target_path=target_path,
        ),
    }

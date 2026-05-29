"""Archify engine orchestration."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .analyze import analyze_graph
from .architecture_context import build_architecture_context
from .artifacts import build_phase6_artifacts
from .build import build_graph
from .cluster import cluster_graph
from .config import EngineConfig
from .dedup import deduplicate_graph
from .detect import build_scan_config, diff_detection_against_manifest, run_detection
from .extract import run_extraction
from .report import render_report
from .schema import merge_fragments
from .semantic import run_semantic_extraction

RESERVED_ARTIFACTS = [
    "graph.json",
    "GRAPH_REPORT.md",
    "facts.json",
    "modules.json",
    "routes.json",
    "database.json",
    "services.json",
    "dependencies.json",
    "docs-summary.json",
    "architecture-context.json",
    "architecture-context.md",
]

PLACEHOLDER_READY_ARTIFACTS = {
    "graph.json",
    "GRAPH_REPORT.md",
    "facts.json",
    "modules.json",
    "routes.json",
    "database.json",
    "services.json",
    "dependencies.json",
    "docs-summary.json",
    "architecture-context.json",
    "architecture-context.md",
}

MANIFEST_VERSION = 2
GRAPH_ARTIFACT_VERSION = 2
LOCK_FILENAME = "analyze.lock"


def _write_placeholder(path: Path, command: str, target_path: Path) -> None:
    if path.suffix == ".json":
        payload: dict[str, Any] = {
            "artifact": path.name,
            "status": "placeholder",
            "producedBy": command,
            "targetPath": str(target_path),
            "message": "Reserved Phase 0 artifact. Real analysis data is not implemented yet.",
        }
        path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf8")
        return

    body = "\n".join(
        [
            f"# {path.name}",
            "",
            "Status: placeholder",
            f"Produced by: {command}",
            f"Target path: {target_path}",
            "",
            "Reserved Phase 0 artifact. Real analysis output is not implemented yet.",
        ]
    )
    path.write_text(f"{body}\n", encoding="utf8")


def _write_reserved_placeholders(output_dir: Path, target_path: Path) -> None:
    for artifact in RESERVED_ARTIFACTS:
        if artifact in PLACEHOLDER_READY_ARTIFACTS:
            continue
        _write_placeholder(output_dir / artifact, "analyze", target_path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(payload: Any) -> str:
    return f"{json.dumps(payload, indent=2)}\n"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, _json_dumps(payload))


def _load_json_if_valid(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _config_fingerprint(config: EngineConfig) -> str:
    payload = {
        "sourceRoot": config.raw.get("defaults", {}).get("sourceRoot", "."),
        "detect": config.raw.get("analysis", {}).get("detect", {}),
        "languageScope": config.raw.get("languageScope", {}),
        "semantic": {
            "enabled": config.semantic.enabled,
            "mode": config.semantic.mode,
            "includeFileTypes": list(config.semantic.include_file_types),
            "includeExtensions": list(config.semantic.include_extensions),
            "maxDocumentBytes": config.semantic.max_document_bytes,
            "maxChunksPerDocument": config.semantic.max_chunks_per_document,
            "maxChunkBytes": config.semantic.max_chunk_bytes,
            "backend": config.semantic.backend,
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _default_extraction_file_summary() -> dict[str, Any]:
    return {
        "language": None,
        "status": "skipped",
        "nodeCount": 0,
        "edgeCount": 0,
        "warning": None,
    }


def _default_semantic_file_summary(config: EngineConfig) -> dict[str, Any]:
    return {
        "status": "not_selected" if config.semantic.enabled else "disabled",
        "reason": None if config.semantic.enabled else "semantic_disabled",
        "backend": config.semantic.backend,
        "providerStatus": "skipped",
    }


def _filter_inventory(inventory: list[dict[str, Any]], selected_paths: set[str]) -> list[dict[str, Any]]:
    if not selected_paths:
        return []
    return [item for item in inventory if item.get("path") in selected_paths]


def _split_graph_by_source_files(graph: dict[str, Any], excluded_paths: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    preserved = {"nodes": [], "edges": [], "hyperedges": []}
    removed = {"nodes": [], "edges": [], "hyperedges": []}
    for key in ("nodes", "edges", "hyperedges"):
        for record in graph.get(key, []):
            bucket = removed if str(record.get("source_file", "")) in excluded_paths else preserved
            bucket[key].append(record)
    return preserved, removed


def _semantic_documents_from_docs_summary(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    documents: list[dict[str, Any]] = []
    for item in payload.get("confirmedFacts", {}).get("processedDocuments", []):
        if not isinstance(item, dict):
            continue
        documents.append(
            {
                "path": item.get("path"),
                "title": item.get("title"),
                "status": item.get("extractionStatus", item.get("status", "ready")),
                "reason": item.get("reason"),
                "sections": item.get("sections", []),
                "references": item.get("references", []),
                "themes": item.get("themes", []),
                "rationaleSnippets": item.get("rationaleSnippets", []),
                "fileType": item.get("fileType"),
            }
        )
    for item in payload.get("confirmedFacts", {}).get("skippedDocuments", []):
        if not isinstance(item, dict):
            continue
        documents.append(
            {
                "path": item.get("path"),
                "title": item.get("title"),
                "status": item.get("status", "skipped"),
                "reason": item.get("reason"),
                "sections": [],
                "references": [],
                "themes": [],
                "rationaleSnippets": [],
                "fileType": item.get("fileType"),
            }
        )
    return [item for item in documents if item.get("path")]


def _merge_document_records(
    previous_documents: list[dict[str, Any]],
    fresh_documents: list[dict[str, Any]],
    removed_paths: set[str],
) -> list[dict[str, Any]]:
    merged = {
        str(item["path"]): item
        for item in previous_documents
        if isinstance(item, dict) and item.get("path") and str(item["path"]) not in removed_paths
    }
    for item in fresh_documents:
        if isinstance(item, dict) and item.get("path"):
            merged[str(item["path"])] = item
    return [merged[path] for path in sorted(merged)]


def _semantic_warnings_from_documents(documents: list[dict[str, Any]], excluded_paths: set[str]) -> list[dict[str, Any]]:
    warnings = []
    for document in documents:
        path = str(document.get("path", ""))
        if not path or path in excluded_paths or document.get("status") == "ready":
            continue
        warnings.append(
            {
                "path": path,
                "stage": "semantic",
                "message": f"Document status preserved as {document.get('status')}: {document.get('reason')}",
            }
        )
    return warnings


def _selected_semantic_paths(config: EngineConfig, detection: dict[str, Any]) -> set[str]:
    include_types = set(config.semantic.include_file_types)
    include_extensions = set(config.semantic.include_extensions)
    selected = set()
    for item in detection["inventory"]:
        path = str(item.get("path", ""))
        if not path:
            continue
        if item.get("fileType") not in include_types:
            continue
        if include_extensions and Path(path).suffix.lower() not in include_extensions:
            continue
        selected.add(path)
    return selected


def _build_extraction_state(
    *,
    config: EngineConfig,
    detection: dict[str, Any],
    previous_manifest: dict[str, Any] | None,
    changed_code_paths: set[str],
    deleted_paths: set[str],
) -> dict[str, Any]:
    previous_files = previous_manifest.get("files", {}) if isinstance(previous_manifest, dict) else {}
    fresh_extraction = run_extraction(
        config.repo_root,
        _filter_inventory(detection["inventory"], changed_code_paths),
        config.raw,
    )
    file_summaries = {
        path: metadata.get("extraction", _default_extraction_file_summary())
        for path, metadata in previous_files.items()
        if isinstance(metadata, dict) and path not in deleted_paths
    }
    file_summaries.update(fresh_extraction.get("files", {}))

    warnings = []
    for path, summary in file_summaries.items():
        warning = summary.get("warning") if isinstance(summary, dict) else None
        language = summary.get("language") if isinstance(summary, dict) else None
        if warning:
            warnings.append({"path": path, "language": language, "message": warning})

    all_code_paths = {item["path"] for item in detection["inventory"] if item.get("fileType") == "code"}
    node_count = sum(int(file_summaries.get(path, {}).get("nodeCount", 0) or 0) for path in all_code_paths)
    edge_count = sum(int(file_summaries.get(path, {}).get("edgeCount", 0) or 0) for path in all_code_paths)
    return {
        "graph": fresh_extraction["graph"],
        "warnings": warnings,
        "files": file_summaries,
        "summary": {
            "extractedFiles": len(all_code_paths),
            "changedFileCount": len(changed_code_paths),
            "reusedFileCount": max(len(all_code_paths) - len(changed_code_paths), 0),
            "nodeCount": node_count,
            "edgeCount": edge_count,
            "hyperedgeCount": len(fresh_extraction["graph"].get("hyperedges", [])),
            "warningCount": len(warnings),
        },
    }


def _build_semantic_state(
    *,
    config: EngineConfig,
    detection: dict[str, Any],
    previous_manifest: dict[str, Any] | None,
    previous_docs_summary: dict[str, Any] | None,
    changed_semantic_paths: set[str],
    deleted_paths: set[str],
    code_graph: dict[str, Any],
) -> dict[str, Any]:
    if not config.semantic.enabled:
        return run_semantic_extraction(
            repo_root=config.repo_root,
            inventory=[],
            semantic_config=config.semantic,
            code_graph=code_graph,
        )

    previous_files = previous_manifest.get("files", {}) if isinstance(previous_manifest, dict) else {}
    previous_documents = _semantic_documents_from_docs_summary(previous_docs_summary)
    fresh_semantic = run_semantic_extraction(
        repo_root=config.repo_root,
        inventory=_filter_inventory(detection["inventory"], changed_semantic_paths),
        semantic_config=config.semantic,
        code_graph=code_graph,
    )
    merged_documents = _merge_document_records(previous_documents, fresh_semantic.get("documents", []), deleted_paths)
    file_summaries = {
        path: metadata.get("semantic", _default_semantic_file_summary(config))
        for path, metadata in previous_files.items()
        if isinstance(metadata, dict) and path not in deleted_paths
    }
    file_summaries.update(fresh_semantic.get("files", {}))

    warnings = [
        *_semantic_warnings_from_documents(merged_documents, changed_semantic_paths),
        *fresh_semantic.get("warnings", []),
    ]
    selected_paths = _selected_semantic_paths(config, detection)
    processed_documents = [item for item in merged_documents if item.get("status") == "ready"]
    skipped_documents = [item for item in merged_documents if item.get("status") != "ready"]
    previous_summary = previous_manifest.get("semanticSummary") if isinstance(previous_manifest, dict) else None
    if not changed_semantic_paths and isinstance(previous_summary, dict):
        summary = dict(previous_summary)
    else:
        summary = {
            "enabled": True,
            "mode": config.semantic.mode,
            "backend": config.semantic.backend,
            "providerEnrichmentSkipped": bool(fresh_semantic.get("summary", {}).get("providerEnrichmentSkipped", True)),
            "selectedDocumentCount": len(selected_paths),
            "processedDocumentCount": len(processed_documents),
            "skippedDocumentCount": len(skipped_documents),
            "nodeCount": len(fresh_semantic["graph"].get("nodes", [])),
            "edgeCount": len(fresh_semantic["graph"].get("edges", [])),
            "hyperedgeCount": len(fresh_semantic["graph"].get("hyperedges", [])),
            "warningCount": len(warnings),
        }

    return {
        "enabled": True,
        "graph": fresh_semantic["graph"],
        "warnings": warnings,
        "files": file_summaries,
        "documents": merged_documents,
        "summary": summary,
    }


def _artifact_note(config: EngineConfig) -> str:
    return (
        "Phase 7 docs-first enrichment completed alongside the code-first pipeline."
        if config.semantic.enabled
        else "Phase 6 structured architecture artifacts completed with document provenance preserved for synthesis."
    )


def _load_required_ready_artifact(config: EngineConfig, name: str) -> dict[str, Any]:
    payload = _load_json_if_valid(config.output_dir / name)
    if payload is None:
        raise RuntimeError(f"GENERATE_INPUT_MISSING: {name}")
    if payload.get("status") != "ready":
        raise RuntimeError(f"GENERATE_INPUT_NOT_READY: {name} (status={payload.get('status', 'unknown')})")
    return payload


def _dedupe_strings(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _evidence_refs(*collections: list[str]) -> list[str]:
    refs: list[str] = []
    for collection in collections:
        refs.extend(str(item) for item in collection if item)
    return _dedupe_strings(refs)


def _brief_list(items: list[str], *, limit: int = 3) -> list[str]:
    return [item for item in items if item][:limit]


def _artifact_relpath(config: EngineConfig, name: str) -> str:
    return Path(config.output_dir.name, name).as_posix()


QUESTIONNAIRE_TEMPLATE = [
    "What kind of architecture output do you want next: a high-level diagram, a deployment view, a sequence flow, or a deeper written architecture?",
    "Which user journeys, business workflows, or API flows matter most for this architecture pass?",
    "What operational constraints should shape the design, such as scale, latency, reliability, compliance, tenancy, or geographic requirements?",
    "Which external systems, third-party integrations, or data providers are in scope and which are intentionally out of scope?",
    "Are there planned changes, migrations, or target-state boundaries that differ from the current codebase structure?",
    "Which inferred components, names, or boundaries should be treated as tentative until you confirm them?",
]


def _supporting_docs(docs_summary: dict[str, Any]) -> list[str]:
    docs = docs_summary.get("confirmedFacts", {}).get("readmeLikeDocs", [])
    paths = [str(item.get("path")) for item in docs if isinstance(item, dict) and item.get("path")]
    return sorted(dict.fromkeys(paths))


def _primary_readme_path(docs_summary: dict[str, Any]) -> str | None:
    for path in _supporting_docs(docs_summary):
        parts = Path(path).parts
        if len(parts) == 1 and parts[0].lower() == "readme.md":
            return path
    return None


def _additional_supporting_docs(docs_summary: dict[str, Any], primary_readme: str | None) -> list[str]:
    return [path for path in _supporting_docs(docs_summary) if path != primary_readme]


def _build_design_packet(target_path: str, config: EngineConfig) -> dict[str, Any]:
    graph = _load_required_ready_artifact(config, "graph.json")
    facts = _load_required_ready_artifact(config, "facts.json")
    modules = _load_required_ready_artifact(config, "modules.json")
    routes = _load_required_ready_artifact(config, "routes.json")
    database = _load_required_ready_artifact(config, "database.json")
    services = _load_required_ready_artifact(config, "services.json")
    dependencies = _load_required_ready_artifact(config, "dependencies.json")
    docs_summary = _load_required_ready_artifact(config, "docs-summary.json")
    architecture_context = _load_required_ready_artifact(config, "architecture-context.json")
    architecture_context_md = config.output_dir / "architecture-context.md"
    if not architecture_context_md.exists():
        raise RuntimeError("GENERATE_INPUT_MISSING: architecture-context.md")

    subsystem_records = architecture_context.get("subsystems", [])
    service_records = services.get("services", [])
    flow_records = architecture_context.get("data_flows", [])
    entrypoint_records = architecture_context.get("key_entrypoints", [])
    open_questions = architecture_context.get("open_questions", [])
    doc_themes = docs_summary.get("inferredAlignments", {}).get("architectureThemes", [])
    primary_readme = _primary_readme_path(docs_summary)
    additional_supporting_docs = _additional_supporting_docs(docs_summary, primary_readme)

    evidence_refs = _evidence_refs(
        [f"artifact:{name}" for name in (
            "architecture-context.json",
            "architecture-context.md",
            "facts.json",
            "modules.json",
            "services.json",
            "dependencies.json",
            "routes.json",
            "database.json",
            "docs-summary.json",
        )],
        [
            *(
                ref
                for item in subsystem_records[:4]
                for ref in item.get("evidence", [])
            ),
            *(
                ref
                for item in flow_records[:4]
                for ref in item.get("evidence_edge_refs", [])
            ),
            *(
                ref
                for item in open_questions[:4]
                for ref in item.get("evidence_edge_refs", [])
            ),
        ],
    )

    confirmed_sections = [
        {
            "id": "system-overview",
            "title": "System Overview",
            "summary": architecture_context.get("system", {}).get("summary", ""),
            "evidence": _evidence_refs(
                [f"artifact:{_artifact_relpath(config, 'architecture-context.json')}"],
                [f"artifact:{_artifact_relpath(config, 'facts.json')}"],
            ),
        },
        {
            "id": "subsystems",
            "title": "Subsystems",
            "summary": f"Detected {len(subsystem_records)} subsystem(s) and {len(service_records)} service surface(s).",
            "items": [
                {
                    "name": subsystem.get("name"),
                    "kind": subsystem.get("kind"),
                    "summary": subsystem.get("summary"),
                    "sourcePaths": subsystem.get("source_paths", []),
                    "evidence": subsystem.get("evidence", []),
                }
                for subsystem in subsystem_records
            ],
            "evidence": _evidence_refs(*[item.get("evidence", []) for item in subsystem_records[:6]]),
        },
        {
            "id": "entrypoints-and-interfaces",
            "title": "Entrypoints And Interfaces",
            "summary": f"Detected {len(entrypoint_records)} entrypoint candidate(s), {len(routes.get('confirmedRoutes', []))} confirmed route(s), and {database.get('summary', {}).get('tableCount', 0)} table(s).",
            "items": [
                {
                    "name": item.get("name"),
                    "kind": item.get("kind"),
                    "subsystemId": item.get("subsystem_id"),
                    "sourcePath": item.get("source_path"),
                    "evidence": _evidence_refs(item.get("evidence_node_ids", []), item.get("evidence_edge_refs", [])),
                }
                for item in entrypoint_records
            ],
            "evidence": _evidence_refs(*[
                _evidence_refs(item.get("evidence_node_ids", []), item.get("evidence_edge_refs", []))
                for item in entrypoint_records[:6]
            ]),
        },
    ]

    inferred_sections = [
        {
            "id": "cross-subsystem-flows",
            "title": "Cross-Subsystem Flows",
            "summary": f"Detected {len(flow_records)} inferred cross-subsystem flow(s).",
            "items": [
                {
                    "sourceSubsystemId": flow.get("source_subsystem_id"),
                    "targetSubsystemId": flow.get("target_subsystem_id"),
                    "relation": flow.get("relation"),
                    "summary": flow.get("summary"),
                    "confidence": flow.get("confidence"),
                    "evidence": flow.get("evidence_edge_refs", []),
                }
                for flow in flow_records
            ],
            "evidence": _evidence_refs(*[flow.get("evidence_edge_refs", []) for flow in flow_records[:6]]),
        },
        {
            "id": "documentation-alignments",
            "title": "Documentation Alignments",
            "summary": f"Detected {len(doc_themes)} architecture theme(s) from repository docs.",
            "items": doc_themes,
            "evidence": _evidence_refs(*[item.get("evidence", []) for item in doc_themes[:6]]),
        },
    ]

    uncertainty_sections = [
        {
            "id": "open-questions",
            "title": "Open Questions",
            "items": [
                {
                    "question": item.get("question"),
                    "confidence": item.get("confidence"),
                    "relatedSubsystems": item.get("related_subsystems", []),
                    "evidence": _evidence_refs(item.get("evidence_node_ids", []), item.get("evidence_edge_refs", [])),
                }
                for item in open_questions
            ],
        },
        {
            "id": "coverage-gaps",
            "title": "Coverage Gaps",
            "items": [
                {
                    "summary": f"{docs_summary.get('summary', {}).get('unresolvedDocumentCount', 0)} document(s) remain unresolved against subsystem evidence.",
                    "evidence": [f"artifact:{_artifact_relpath(config, 'docs-summary.json')}"],
                },
                {
                    "summary": f"{facts.get('summary', {}).get('ambiguousEdgeCount', 0)} ambiguous edge(s) remain in the graph.",
                    "evidence": [f"artifact:{_artifact_relpath(config, 'facts.json')}"],
                },
            ],
        },
    ]

    return {
        "artifact": "design-packet.json",
        "status": "ready",
        "phase": "generate",
        "generatedAt": _utc_now(),
        "targetPath": str(Path(target_path).resolve()),
        "scanRoot": graph.get("scanRoot"),
        "artifacts": {
            "graph": _artifact_relpath(config, "graph.json"),
            "facts": _artifact_relpath(config, "facts.json"),
            "modules": _artifact_relpath(config, "modules.json"),
            "routes": _artifact_relpath(config, "routes.json"),
            "database": _artifact_relpath(config, "database.json"),
            "services": _artifact_relpath(config, "services.json"),
            "dependencies": _artifact_relpath(config, "dependencies.json"),
            "docsSummary": _artifact_relpath(config, "docs-summary.json"),
            "architectureContext": _artifact_relpath(config, "architecture-context.json"),
            "architectureContextMarkdown": _artifact_relpath(config, "architecture-context.md"),
        },
        "supportingDocuments": {
            "primaryReadme": primary_readme,
            "additionalDocs": additional_supporting_docs,
        },
        "summaries": {
            "system": architecture_context.get("system", {}),
            "graph": graph.get("summary", {}),
            "facts": facts.get("summary", {}),
            "docs": docs_summary.get("summary", {}),
            "database": database.get("summary", {}),
            "services": services.get("summary", {}),
            "dependencies": dependencies.get("summary", {}),
            "routes": routes.get("summary", {}),
        },
        "confirmedFromCodebase": confirmed_sections,
        "inferredArchitecture": inferred_sections,
        "openQuestionsAndUncertainty": uncertainty_sections,
        "evidenceIndex": {
            "primary": evidence_refs,
            "architectureContextEvidence": architecture_context.get("evidence", {}),
        },
        "generationRules": {
            "readOrder": [
                _artifact_relpath(config, "design-packet.json"),
                _artifact_relpath(config, "architecture-context.json"),
                _artifact_relpath(config, "facts.json"),
                _artifact_relpath(config, "modules.json"),
                _artifact_relpath(config, "services.json"),
                _artifact_relpath(config, "dependencies.json"),
                _artifact_relpath(config, "routes.json"),
                _artifact_relpath(config, "database.json"),
                _artifact_relpath(config, "docs-summary.json"),
                *([primary_readme] if primary_readme else []),
                *additional_supporting_docs,
            ],
            "finalOutputFile": "archify.md",
            "mustSeparate": [
                "Confirmed From Codebase",
                "Inferred Architecture",
                "Open Questions / Uncertainty",
            ],
            "documentShape": "upload_ready_architecture_prompt_pack",
            "mustNotDo": [
                "Do not inspect the whole repository before reading the design packet and referenced artifacts.",
                "Do not present inferred behavior as confirmed fact.",
                "Do not use README or other supporting docs as a replacement for the .archify artifacts.",
                "Do not treat README-only claims as confirmed codebase facts unless grounded evidence corroborates them.",
                "Do not cite raw repository files unless the packet evidence is insufficient.",
                "Do not treat archify_design.md, architecture.md, design.md, or root diagram-prompt.md as the primary product output.",
            ],
            "requiredSections": [
                "System Prompt",
                "User Prompt",
                "Grounded Repository Context",
                "Confirmed From Codebase",
                "Inferred Architecture",
                "Questions Before Architecture Generation",
                "Diagram / Image Generation Instructions",
                "Open Questions / Uncertainty",
            ],
            "promptBehavior": {
                "firstResponseMustAskArtifactType": True,
                "artifactTypeOptions": [
                    "high-level architecture",
                    "low-level architecture",
                    "component breakdown",
                    "user flow diagram",
                    "sequence / interaction view",
                    "custom request",
                ],
                "firstResponseMustAskVisualStyle": True,
                "visualStyleOptions": [
                    "clean architecture diagram",
                    "swimlane flow",
                    "sequence view",
                    "annotated component map",
                    "presentation-ready infographic",
                    "custom style",
                ],
                "mustAllowCustomAnswers": True,
                "mustWaitForAnswersBeforeFinalOutput": True,
                "mustSeparateConfirmedFactsFromInference": True,
            },
            "diagramCapabilityPolicy": {
                "mustAskForPreferredVisualStyleBeforeGeneratingVisuals": True,
                "generateImageWhenAppSupportsIt": True,
                "fallbackToRenderReadyDiagramSpecWhenImageGenerationUnavailable": True,
                "mustNotAssumeSpecificAppFeatureSet": True,
            },
            "questionnairePolicy": {
                "mustAskBeforeFinalArchitecture": True,
                "mayAdjustFromAnswers": [
                    "boundaries",
                    "flows",
                    "naming",
                    "assumptions",
                    "deliverable_type",
                    "diagram_style",
                ],
                "mustNotPresentInferredAsConfirmed": True,
                "readmeMayEnrichWithoutOverridingGroundedEvidence": True,
            },
        },
        "questionnaireTemplate": {
            "sectionTitle": "Questions Before Architecture Generation",
            "instructions": [
                "Ask every question in this section before generating or revising the final architecture.",
                "Use the answers to adjust boundaries, flows, naming, assumptions, and diagram scope.",
                "Keep inferred items explicitly marked as inferred until the answers confirm them.",
            ],
            "questions": QUESTIONNAIRE_TEMPLATE,
        },
    }


def _build_archify_guide(packet: dict[str, Any], config: EngineConfig) -> dict[str, Any]:
    artifacts = packet.get("artifacts", {})
    supporting_documents = packet.get("supportingDocuments", {})
    generation_rules = packet.get("generationRules", {})
    questionnaire = packet.get("questionnaireTemplate", {})
    prompt_behavior = generation_rules.get("promptBehavior", {})
    diagram_policy = generation_rules.get("diagramCapabilityPolicy", {})

    read_order = [
        _artifact_relpath(config, "design-packet.json"),
        _artifact_relpath(config, "archify.guide.json"),
        *[
            item
            for item in generation_rules.get("readOrder", [])
            if item != _artifact_relpath(config, "design-packet.json")
        ],
    ]

    section_plan = [
        {
            "section": "System Prompt",
            "required": True,
            "sourceArtifacts": [_artifact_relpath(config, "design-packet.json")],
            "sourceFields": ["generationRules.requiredSections", "generationRules.documentShape"],
            "factPolicy": "instruction_only",
            "draftingInstructions": [
                "Define the assistant role, grounding expectations, and factuality constraints.",
                "State that `.archify` artifacts are the primary source of truth.",
            ],
            "missingEvidenceBehavior": "Do not invent repository facts in this section. Keep it as instruction-only content.",
            "validationChecks": [
                "Keep this section instructional, not descriptive of unverified repository details.",
                "Mention grounded `.archify` evidence as the primary source of confirmed facts.",
            ],
        },
        {
            "section": "User Prompt",
            "required": True,
            "sourceArtifacts": [_artifact_relpath(config, "design-packet.json")],
            "sourceFields": ["questionnaireTemplate", "generationRules.promptBehavior"],
            "factPolicy": "instruction_only",
            "draftingInstructions": [
                "Tell the downstream AI what to produce using the grounded repository context.",
                "Preserve the guided interaction requirements from the packet.",
            ],
            "missingEvidenceBehavior": "Do not add repository-specific claims unless they are already grounded elsewhere in the packet.",
            "validationChecks": [
                "Preserve the requirement to ask which architecture artifact the user wants.",
                "Preserve the requirement to ask for visual style before visual generation.",
            ],
        },
        {
            "section": "Grounded Repository Context",
            "required": True,
            "sourceArtifacts": [
                artifacts.get("architectureContext"),
                artifacts.get("architectureContextMarkdown"),
                artifacts.get("facts"),
                artifacts.get("modules"),
                artifacts.get("services"),
                artifacts.get("routes"),
                artifacts.get("database"),
                artifacts.get("dependencies"),
            ],
            "sourceFields": ["confirmedFromCodebase", "groundedRepositoryContext"],
            "factPolicy": "confirmed_first",
            "draftingInstructions": [
                "Summarize the system, subsystems, interfaces, dependencies, routes, and data concerns from the listed artifacts.",
                "Prefer compact factual statements over exhaustive dumps.",
            ],
            "missingEvidenceBehavior": "If a subsystem or concern is not supported by the listed artifacts, omit it or explicitly mark evidence as insufficient.",
            "validationChecks": [
                "Every major claim should map back to at least one listed artifact.",
                "Do not blend inferred architecture into this section without labeling it.",
            ],
        },
        {
            "section": "Confirmed From Codebase",
            "required": True,
            "sourceArtifacts": [
                artifacts.get("architectureContext"),
                artifacts.get("facts"),
                artifacts.get("modules"),
                artifacts.get("services"),
                artifacts.get("routes"),
                artifacts.get("database"),
                artifacts.get("dependencies"),
            ],
            "sourceFields": ["confirmedFromCodebase"],
            "factPolicy": "confirmed_only",
            "draftingInstructions": [
                "Use only packet entries already categorized as confirmed.",
                "Preserve evidence-backed distinctions such as subsystem inventory, interfaces, services, routes, and data stores.",
            ],
            "missingEvidenceBehavior": "If there are few confirmed items for a topic, state that the codebase evidence is limited instead of filling gaps.",
            "validationChecks": [
                "Every bullet or paragraph in this section must come from confirmed packet content.",
                "Do not introduce README-only or inferred claims here.",
            ],
        },
        {
            "section": "Inferred Architecture",
            "required": True,
            "sourceArtifacts": [
                artifacts.get("architectureContext"),
                artifacts.get("architectureContextMarkdown"),
            ],
            "sourceFields": ["inferredArchitecture"],
            "factPolicy": "inferred_must_be_labeled",
            "draftingInstructions": [
                "Summarize architectural implications synthesized from grounded relationships.",
                "Use explicit labels such as `Inferred` when describing boundaries, flows, or responsibilities not directly declared.",
            ],
            "missingEvidenceBehavior": "If the packet has no meaningful inferred items, say that no strong additional architectural inference was derived.",
            "validationChecks": [
                "Every statement in this section should be explicitly framed as inference.",
                "Do not move inferred content into confirmed sections.",
            ],
        },
        {
            "section": "Open Questions / Uncertainty",
            "required": True,
            "sourceArtifacts": [
                artifacts.get("architectureContext"),
                artifacts.get("docsSummary"),
            ],
            "sourceFields": ["openQuestionsAndUncertainty"],
            "factPolicy": "uncertainty_only",
            "draftingInstructions": [
                "List unresolved architecture questions, ambiguous boundaries, and missing evidence areas.",
                "Keep uncertainty actionable and specific.",
            ],
            "missingEvidenceBehavior": "If the packet has no open questions, state that no major unresolved questions were extracted from the grounded artifacts.",
            "validationChecks": [
                "Do not convert uncertainty into factual statements.",
                "Keep this section focused on ambiguity, missing evidence, or decisions needing user input.",
            ],
        },
        {
            "section": "Questions Before Architecture Generation",
            "required": True,
            "sourceArtifacts": [_artifact_relpath(config, "design-packet.json")],
            "sourceFields": ["questionnaireTemplate.sectionTitle", "questionnaireTemplate.questions"],
            "factPolicy": "instruction_only",
            "draftingInstructions": [
                "Preserve the packet questionnaire as a pre-generation gating step.",
                "Keep the questions focused on user intent, flows, constraints, and scope.",
            ],
            "missingEvidenceBehavior": "Do not replace the questionnaire with assumptions.",
            "validationChecks": [
                "Keep the section title from the packet.",
                "Preserve the requirement to ask these questions before final architecture output.",
            ],
        },
        {
            "section": "Diagram / Image Generation Instructions",
            "required": True,
            "sourceArtifacts": [_artifact_relpath(config, "design-packet.json")],
            "sourceFields": ["generationRules.diagramCapabilityPolicy", "generationRules.promptBehavior"],
            "factPolicy": "instruction_only",
            "draftingInstructions": [
                "Tell capable apps to generate visuals directly and other apps to return render-ready diagram specifications.",
                "Preserve the visual-style question and wait-for-answer requirement.",
            ],
            "missingEvidenceBehavior": "Do not invent diagram content beyond what the grounded context supports.",
            "validationChecks": [
                "State the direct image-generation behavior when supported.",
                "State the fallback render-ready specification behavior when image generation is unavailable.",
            ],
        },
    ]

    fallback_repo_reads = []
    primary_readme = supporting_documents.get("primaryReadme")
    if primary_readme:
        fallback_repo_reads.append(
            {
                "path": primary_readme,
                "reason": "Supporting product and usage context referenced by the design packet.",
            }
        )
    for path in supporting_documents.get("additionalDocs", []):
        fallback_repo_reads.append(
            {
                "path": path,
                "reason": "Optional supporting context referenced by the design packet.",
            }
        )

    return {
        "artifact": "archify.guide.json",
        "status": "ready",
        "phase": "generate",
        "docType": "archify",
        "outputFile": "archify.md",
        "targetPath": packet.get("targetPath"),
        "goal": "Guide the agent to write `archify.md` from grounded `.archify` artifacts with minimal extra repository reads.",
        "primaryArtifacts": [
            _artifact_relpath(config, "design-packet.json"),
            artifacts.get("architectureContext"),
            artifacts.get("architectureContextMarkdown"),
            artifacts.get("facts"),
            artifacts.get("modules"),
            artifacts.get("services"),
            artifacts.get("routes"),
            artifacts.get("database"),
            artifacts.get("dependencies"),
            artifacts.get("docsSummary"),
        ],
        "readOrder": [item for item in read_order if item],
        "sectionPlan": [
            {
                **item,
                "sourceArtifacts": [artifact for artifact in item.get("sourceArtifacts", []) if artifact],
            }
            for item in section_plan
        ],
        "factPolicy": {
            "confirmed": "Only state items as confirmed when they are directly supported by the listed `.archify` artifacts.",
            "inferred": "Use inferred statements only when synthesized from artifact relationships and label them explicitly as inferred.",
            "missingEvidence": "If the artifacts do not support a claim, state that repository evidence is insufficient instead of guessing.",
            "supportingDocs": "Treat README and optional supporting docs as secondary context that cannot override grounded `.archify` evidence.",
        },
        "draftingWorkflow": [
            "Read `.archify/design-packet.json`.",
            "Read `.archify/archify.guide.json`.",
            "Read only the artifacts listed in `readOrder`.",
            "Draft `archify.md` section by section using `sectionPlan`.",
            "Run section-level validation using each section's `validationChecks`.",
            "Run final document validation using `validationChecks` before finalizing output.",
        ],
        "fallbackRepoReads": fallback_repo_reads,
        "forbiddenBehaviors": [
            "Do not inspect the whole repository before reading the guide and the referenced `.archify` artifacts.",
            "Do not present README-only or supporting-doc-only claims as confirmed codebase facts.",
            "Do not invent rationale, deployment boundaries, or undocumented architecture decisions.",
            "Do not write any primary output file other than `archify.md`.",
        ],
        "promptBehavior": {
            "firstResponseMustAskArtifactType": prompt_behavior.get("firstResponseMustAskArtifactType", False),
            "artifactTypeOptions": prompt_behavior.get("artifactTypeOptions", []),
            "firstResponseMustAskVisualStyle": prompt_behavior.get("firstResponseMustAskVisualStyle", False),
            "mustAllowCustomAnswers": prompt_behavior.get("mustAllowCustomAnswers", False),
            "mustWaitForAnswersBeforeFinalOutput": prompt_behavior.get("mustWaitForAnswersBeforeFinalOutput", False),
        },
        "questionnaire": questionnaire,
        "diagramCapabilityPolicy": diagram_policy,
        "validationChecks": [
            "Read `.archify/design-packet.json` before any other synthesis artifact.",
            "Read `.archify/archify.guide.json` before reading repository files outside `.archify`.",
            "Draft and validate `archify.md` section by section using `sectionPlan`.",
            "Ensure every major section is traceable to the listed source artifacts.",
            "Ensure inferred statements are labeled and kept separate from confirmed facts.",
            "Ensure unsupported claims are replaced with explicit uncertainty or missing-evidence language.",
            "Ensure the final document includes `System Prompt`, `User Prompt`, `Grounded Repository Context`, `Questions Before Architecture Generation`, and `Diagram / Image Generation Instructions`.",
        ],
    }


def _render_design_brief(packet: dict[str, Any]) -> str:
    system_summary = packet.get("summaries", {}).get("system", {}).get("summary", "")
    subsystem_items = packet.get("confirmedFromCodebase", [])[1].get("items", []) if len(packet.get("confirmedFromCodebase", [])) > 1 else []
    flow_items = packet.get("inferredArchitecture", [])[0].get("items", []) if packet.get("inferredArchitecture") else []
    question_items = packet.get("openQuestionsAndUncertainty", [])[0].get("items", []) if packet.get("openQuestionsAndUncertainty") else []
    subsystem_names = [item.get("name", "") for item in subsystem_items]
    flow_summaries = [item.get("summary", "") for item in flow_items]
    question_summaries = [item.get("question", "") for item in question_items]

    lines = [
        "# Design Brief",
        "",
        f"Target: `{packet.get('targetPath', '')}`",
        "",
        "This brief is internal grounding for the Archify skill. The skill should use it to write root-level `archify.md` as an upload-ready multi-role architecture prompt document.",
        "",
        "## Grounded Summary",
        system_summary or "No system summary was available.",
        "",
        "## Confirmed Priorities",
    ]
    if subsystem_names:
        lines.extend(f"- Subsystem: `{name}`" for name in _brief_list(subsystem_names, limit=5))
    else:
        lines.append("- No subsystem records were available.")
    lines.extend([
        "",
        "## Inferred Priorities",
    ])
    if flow_summaries:
        lines.extend(f"- {summary}" for summary in _brief_list(flow_summaries, limit=5))
    else:
        lines.append("- No inferred cross-subsystem flows were available.")
    lines.extend([
        "",
        "## Open Questions",
    ])
    if question_summaries:
        lines.extend(f"- {summary}" for summary in _brief_list(question_summaries, limit=5))
    else:
        lines.append("- No open questions were recorded.")
    lines.extend([
        "",
        "## Writing Rules",
        "- Start from `.archify/design-packet.json` and only read the referenced artifacts.",
        "- Use the `.archify` artifacts as the primary grounded source of confirmed facts.",
        "- Read the root README listed as `supportingDocuments.primaryReadme` after the `.archify` artifacts when it is present.",
        "- Skip the README step cleanly when `supportingDocuments.primaryReadme` is null.",
        "- Treat `supportingDocuments.additionalDocs` as optional extra context after the README step.",
        "- Write one final file: `archify.md`.",
        "- Base the final `archify.md` on `.archify` knowledge plus README understanding when a README is present.",
        "- Make the final file an upload-ready architecture prompt pack for AI apps such as ChatGPT or Claude.",
        "- Include explicit `System Prompt` and `User Prompt` sections at the top level.",
        "- Include a `Grounded Repository Context` section that carries the repository evidence without replacing the prompt sections.",
        "- Keep confirmed facts separate from inferred architecture.",
        "- Include a `Questions Before Architecture Generation` section and ask those questions before finalizing the architecture.",
        "- The first guided interaction must ask which architecture artifact the user wants, offer multiple options, and allow a custom answer.",
        "- The second guided interaction must ask how the architecture should look visually, offer diagram or image style options, and allow a custom answer.",
        "- Wait for the user's guided answers before generating the final architecture output or visual.",
        "- Include `Diagram / Image Generation Instructions` that tell capable apps to generate the image directly and tell non-image-capable apps to return a render-ready diagram prompt or specification instead.",
        "- Support multiple deliverable types including high-level architecture, low-level architecture, component breakdowns, user flows, sequence or interaction views, and custom requests.",
        "- Do not let README-only claims override grounded `.archify` evidence without marking them as inferred or uncertain.",
        "- Cite evidence references from the packet in each major section.",
        "- Do not create `archify_design.md`, `architecture.md`, `design.md`, or root `diagram-prompt.md` as the main output.",
    ])
    return "\n".join(lines) + "\n"


def _render_archify_guide_brief(guide: dict[str, Any]) -> str:
    lines = [
        "# Archify Guide Brief",
        "",
        f"Doc type: `{guide.get('docType', '')}`",
        f"Output file: `{guide.get('outputFile', '')}`",
        "",
        guide.get("goal", ""),
        "",
        "## Read Order",
    ]
    lines.extend(f"- `{item}`" for item in guide.get("readOrder", []))
    lines.extend([
        "",
        "## Drafting Workflow",
    ])
    lines.extend(f"- {item}" for item in guide.get("draftingWorkflow", []))
    lines.extend([
        "",
        "## Fact Rules",
        f"- Confirmed: {guide.get('factPolicy', {}).get('confirmed', '')}",
        f"- Inferred: {guide.get('factPolicy', {}).get('inferred', '')}",
        f"- Missing evidence: {guide.get('factPolicy', {}).get('missingEvidence', '')}",
        f"- Supporting docs: {guide.get('factPolicy', {}).get('supportingDocs', '')}",
        "",
        "## Required Sections",
    ])
    for item in guide.get("sectionPlan", []):
        if not item.get("section"):
            continue
        artifacts = ", ".join(f"`{artifact}`" for artifact in item.get("sourceArtifacts", []))
        lines.append(f"- `{item.get('section', '')}` from {artifacts}")
        for field in item.get("sourceFields", []):
            lines.append(f"  Field: `{field}`")
        for instruction in item.get("draftingInstructions", []):
            lines.append(f"  Drafting: {instruction}")
        lines.append(f"  Missing evidence: {item.get('missingEvidenceBehavior', '')}")
    lines.extend([
        "",
        "## Validation Checks",
    ])
    lines.extend(f"- {item}" for item in guide.get("validationChecks", []))
    lines.extend([
        "",
        "## Forbidden Behaviors",
    ])
    lines.extend(f"- {item}" for item in guide.get("forbiddenBehaviors", []))
    return "\n".join(lines) + "\n"


def _is_live_pid(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def _analysis_lock(output_dir: Path, target: Path):
    lock_path = output_dir / LOCK_FILENAME
    stale_lock = None
    if lock_path.exists():
        existing = _load_json_if_valid(lock_path)
        pid = existing.get("pid") if isinstance(existing, dict) else None
        if isinstance(pid, int) and _is_live_pid(pid):
            raise RuntimeError(f"ANALYZE_IN_PROGRESS: {lock_path}")
        stale_lock = existing or {"message": "Removed stale or corrupt analyze lock."}
    _atomic_write_json(lock_path, {"pid": os.getpid(), "startedAt": _utc_now(), "targetPath": str(target)})
    try:
        yield stale_lock
    finally:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass


def _resolve_scan_root(target_path: str, config: EngineConfig) -> tuple[Path, Path]:
    target = Path(target_path).resolve()
    source_root = config.raw.get("defaults", {}).get("sourceRoot", ".")
    configured_root = (config.repo_root / source_root).resolve()
    scan_root = target

    try:
        scan_root.relative_to(config.repo_root)
    except ValueError as exc:
        raise ValueError(f"Target path must stay within repo root: {target}") from exc

    if configured_root.exists() and target == config.repo_root:
        scan_root = configured_root
    return target, scan_root


def _prepare_detection(config: EngineConfig, scan_root: Path) -> dict[str, Any]:
    scan_config = build_scan_config(
        config=config.raw,
        repo_root=config.repo_root,
        scan_root=scan_root,
        output_dir=config.output_dir,
    )
    return run_detection(scan_config)


def _load_incremental_state(config: EngineConfig) -> dict[str, Any]:
    return {
        "manifest": _load_json_if_valid(config.output_dir / "manifest.json"),
        "graph": _load_json_if_valid(config.output_dir / "graph.json"),
        "docs_summary": _load_json_if_valid(config.output_dir / "docs-summary.json"),
    }


def _incremental_eligibility(
    *,
    config: EngineConfig,
    target: Path,
    detection: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str | None]:
    manifest = state["manifest"]
    graph = state["graph"]
    if manifest is None or graph is None:
        return False, "missing_prior_state"
    if manifest.get("status") != "ready" or graph.get("status") != "ready":
        return False, "prior_state_not_ready"
    if manifest.get("targetPath") != str(target):
        return False, "target_path_changed"
    if manifest.get("scanRoot") != detection["scanRoot"]:
        return False, "scan_root_changed"
    if manifest.get("manifestVersion") != MANIFEST_VERSION:
        return False, "manifest_version_changed"
    if manifest.get("graphArtifactVersion") != GRAPH_ARTIFACT_VERSION:
        return False, "graph_artifact_version_changed"
    if manifest.get("semanticEnabled") != config.semantic.enabled:
        return False, "semantic_enabled_changed"
    if manifest.get("semanticConfigFingerprint") != _config_fingerprint(config):
        return False, "config_fingerprint_changed"
    return True, None


def _compose_manifest(
    *,
    config: EngineConfig,
    target: Path,
    detection: dict[str, Any],
    graph_summary: dict[str, Any],
    clustered_graph: dict[str, Any],
    analysis: dict[str, Any],
    semantic_summary: dict[str, Any],
    architecture_context_summary: dict[str, Any],
    extraction_files: dict[str, Any],
    semantic_files: dict[str, Any],
    mode: str,
    incremental: dict[str, Any],
    stale_lock: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "artifact": "manifest.json",
        "status": "ready",
        "phase": "analyze",
        "manifestVersion": MANIFEST_VERSION,
        "graphArtifactVersion": GRAPH_ARTIFACT_VERSION,
        "generatedAt": _utc_now(),
        "targetPath": str(target),
        "scanRoot": detection["scanRoot"],
        "semanticEnabled": config.semantic.enabled,
        "semanticConfigFingerprint": _config_fingerprint(config),
        "mode": mode,
        "incremental": incremental,
        "staleLockRecovered": stale_lock,
        "graphSummary": graph_summary,
        "dedupSummary": clustered_graph["dedup"],
        "clusteringSummary": clustered_graph["clustering"],
        "analysisSummary": {
            "godNodeCount": len(analysis["godNodes"]),
            "surprisingConnectionCount": len(analysis["surprisingConnections"]),
            "suggestedQuestionCount": len(analysis["suggestedQuestions"]),
            "ambiguousEdgeCount": analysis["ambiguitySummary"]["ambiguousEdgeCount"],
        },
        "semanticSummary": semantic_summary,
        "architectureContextSummary": architecture_context_summary,
        "files": {
            path: {
                **metadata,
                "extraction": extraction_files.get(path, _default_extraction_file_summary()),
                "semantic": semantic_files.get(path, _default_semantic_file_summary(config)),
            }
            for path, metadata in detection["manifest"].items()
        },
    }


def _write_analysis_outputs(
    *,
    config: EngineConfig,
    target: Path,
    detection: dict[str, Any],
    extraction: dict[str, Any],
    semantic: dict[str, Any],
    clustered_graph: dict[str, Any],
    analysis: dict[str, Any],
    architecture_context: dict[str, Any],
    report: str,
    mode: str,
    incremental: dict[str, Any],
    stale_lock: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    architecture_context_summary = architecture_context["summary"]
    combined_warnings = [*extraction["warnings"], *semantic["warnings"], *clustered_graph["warnings"]]
    graph_summary = {
        "nodeCount": len(clustered_graph["nodes"]),
        "edgeCount": len(clustered_graph["edges"]),
        "hyperedgeCount": len(clustered_graph["hyperedges"]),
        "communityCount": clustered_graph["clustering"]["communityCount"],
        "warningCount": len(combined_warnings),
    }

    phase6_artifacts = build_phase6_artifacts(
        detection=detection,
        extraction_summary=extraction["summary"],
        semantic=semantic,
        graph=clustered_graph,
        analysis=analysis,
        architecture_context=architecture_context,
        target_path=str(target),
    )
    for artifact_name, payload in phase6_artifacts.items():
        _atomic_write_json(config.output_dir / artifact_name, payload)

    graph_payload = {
        "artifact": "graph.json",
        "status": "ready",
        "phase": "analyze",
        "graphArtifactVersion": GRAPH_ARTIFACT_VERSION,
        "mode": mode,
        "incremental": incremental,
        "targetPath": str(target),
        "scanRoot": detection["scanRoot"],
        "summary": graph_summary,
        "dedup": clustered_graph["dedup"],
        "clustering": clustered_graph["clustering"],
        "analysis": analysis,
        "semantic": semantic["summary"],
        "warnings": combined_warnings,
        "nodes": clustered_graph["nodes"],
        "edges": clustered_graph["edges"],
        "hyperedges": clustered_graph["hyperedges"],
        "communities": clustered_graph["communities"],
    }
    _atomic_write_json(config.output_dir / "graph.json", graph_payload)

    architecture_context_payload = {
        "artifact": "architecture-context.json",
        "status": "ready",
        "phase": "analyze",
        "targetPath": str(target),
        "scanRoot": detection["scanRoot"],
        **{
            key: architecture_context[key]
            for key in (
                "system",
                "subsystems",
                "interfaces",
                "data_flows",
                "cross_cutting_concerns",
                "key_entrypoints",
                "external_dependencies",
                "evidence",
                "open_questions",
                "summary",
            )
        },
    }
    _atomic_write_json(config.output_dir / "architecture-context.json", architecture_context_payload)
    _atomic_write_text(config.output_dir / "architecture-context.md", architecture_context["markdown"])
    _atomic_write_text(config.output_dir / "GRAPH_REPORT.md", report)

    manifest_payload = _compose_manifest(
        config=config,
        target=target,
        detection=detection,
        graph_summary=graph_summary,
        clustered_graph=clustered_graph,
        analysis=analysis,
        semantic_summary=semantic["summary"],
        architecture_context_summary=architecture_context_summary,
        extraction_files=extraction["files"],
        semantic_files=semantic["files"],
        mode=mode,
        incremental=incremental,
        stale_lock=stale_lock,
    )
    _atomic_write_json(config.output_dir / "manifest.json", manifest_payload)
    _write_reserved_placeholders(config.output_dir, target)
    return graph_summary, architecture_context_summary


def analyze(target_path: str, config: EngineConfig) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    target, scan_root = _resolve_scan_root(target_path, config)

    with _analysis_lock(config.output_dir, target) as stale_lock:
        detection = _prepare_detection(config, scan_root)
        state = _load_incremental_state(config)
        incremental_allowed, fallback_reason = _incremental_eligibility(
            config=config,
            target=target,
            detection=detection,
            state=state,
        )

        previous_manifest = state["manifest"] if incremental_allowed else None
        previous_graph = state["graph"] if incremental_allowed else None
        previous_docs_summary = state["docs_summary"] if incremental_allowed else None
        incremental = diff_detection_against_manifest(detection, previous_manifest)
        mode = "incremental" if incremental_allowed else "full"

        changed_code_paths = (
            set(incremental["changed_code_files"])
            if incremental_allowed
            else {item["path"] for item in detection["inventory"] if item.get("fileType") == "code"}
        )
        changed_semantic_paths = (
            set(incremental["changed_semantic_files"])
            if incremental_allowed
            else (_selected_semantic_paths(config, detection) if config.semantic.enabled else set())
        )
        deleted_paths = set(incremental["deleted_files"])
        incremental.update(
            {
                "incrementalEligible": incremental_allowed,
                "fallbackReason": fallback_reason,
                "semanticSkipped": config.semantic.enabled and not bool(changed_semantic_paths),
            }
        )

        preserved_graph = {"nodes": [], "edges": [], "hyperedges": []}
        if previous_graph is not None:
            preserved_graph, _ = _split_graph_by_source_files(
                previous_graph,
                changed_code_paths | changed_semantic_paths | deleted_paths,
            )

        extraction = _build_extraction_state(
            config=config,
            detection=detection,
            previous_manifest=previous_manifest,
            changed_code_paths=changed_code_paths,
            deleted_paths=deleted_paths,
        )
        code_graph_for_semantic = merge_fragments([preserved_graph, extraction["graph"]])
        semantic = _build_semantic_state(
            config=config,
            detection=detection,
            previous_manifest=previous_manifest,
            previous_docs_summary=previous_docs_summary,
            changed_semantic_paths=changed_semantic_paths,
            deleted_paths=deleted_paths,
            code_graph=code_graph_for_semantic,
        )
        merged_extraction = merge_fragments([preserved_graph, extraction["graph"], semantic["graph"]])
        built_graph = build_graph(merged_extraction)
        deduplicated_graph = deduplicate_graph(built_graph)
        clustered_graph = cluster_graph(deduplicated_graph)
        analysis = analyze_graph(clustered_graph)
        architecture_context = build_architecture_context(
            graph=clustered_graph,
            analysis=analysis,
            detection=detection,
            extraction_summary=extraction["summary"],
            semantic_summary=semantic["summary"],
            target_path=str(target),
        )
        report = render_report(
            graph=clustered_graph,
            analysis=analysis,
            detection=detection,
            extraction_summary=extraction["summary"],
            target_path=str(target),
        )
        graph_summary, architecture_context_summary = _write_analysis_outputs(
            config=config,
            target=target,
            detection=detection,
            extraction=extraction,
            semantic=semantic,
            clustered_graph=clustered_graph,
            analysis=analysis,
            architecture_context=architecture_context,
            report=report,
            mode=mode,
            incremental=incremental,
            stale_lock=stale_lock,
        )

    return {
        "status": "ok",
        "phase": "analyze",
        "mode": mode,
        "targetPath": str(target),
        "scanRoot": detection["scanRoot"],
        "outputDir": str(config.output_dir),
        "artifactCount": len(RESERVED_ARTIFACTS) + 1,
        "totals": detection["totals"],
        "extractionCandidateCount": len(detection["extractionCandidates"]),
        "extractedFileCount": extraction["summary"]["extractedFiles"],
        "changedFileCount": incremental["changedFileCount"],
        "deletedFileCount": incremental["deletedFileCount"],
        "reusedFileCount": incremental["reusedFileCount"],
        "semanticSkipped": incremental["semanticSkipped"],
        "fallbackReason": fallback_reason,
        "nodeCount": graph_summary["nodeCount"],
        "edgeCount": graph_summary["edgeCount"],
        "hyperedgeCount": graph_summary["hyperedgeCount"],
        "communityCount": clustered_graph["clustering"]["communityCount"],
        "semanticDocumentCount": semantic["summary"]["processedDocumentCount"],
        "semanticNodeCount": semantic["summary"]["nodeCount"],
        "deduplicatedNodeCount": clustered_graph["dedup"]["duplicateNodeCount"],
        "deduplicatedEdgeCount": clustered_graph["dedup"]["duplicateEdgeCount"],
        "validationWarningCount": graph_summary["warningCount"],
        "godNodeCount": len(analysis["godNodes"]),
        "surprisingConnectionCount": len(analysis["surprisingConnections"]),
        "suggestedQuestionCount": len(analysis["suggestedQuestions"]),
        "ambiguousEdgeCount": analysis["ambiguitySummary"]["ambiguousEdgeCount"],
        "semanticSummary": semantic["summary"],
        "architectureContextSummary": architecture_context_summary,
        "warning": detection["warning"],
        "note": _artifact_note(config),
    }


def generate(target_path: str, config: EngineConfig) -> dict[str, Any]:
    packet = _build_design_packet(target_path, config)
    guide = _build_archify_guide(packet, config)
    packet_path = config.output_dir / "design-packet.json"
    brief_path = config.output_dir / "design-brief.md"
    guide_path = config.output_dir / "archify.guide.json"
    guide_brief_path = config.output_dir / "archify.guide.md"

    _atomic_write_json(packet_path, packet)
    _atomic_write_text(brief_path, _render_design_brief(packet))
    _atomic_write_json(guide_path, guide)
    _atomic_write_text(guide_brief_path, _render_archify_guide_brief(guide))

    return {
        "status": "ok",
        "phase": "generate",
        "targetPath": str(Path(target_path).resolve()),
        "outputs": [str(packet_path), str(brief_path), str(guide_path), str(guide_brief_path)],
        "note": "Phase 9 design packet and archify guide generated from grounded `.archify/` artifacts for upload-ready `archify.md` prompt-pack authoring.",
    }

"""Phase 7 docs-first semantic extraction and reporting."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import SemanticConfig
from .schema import build_location, make_file_id, make_id, merge_fragments


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_RST_UNDERLINE_CHARS = set("=-~^\"`:#*+")
_FENCED_CODE_RE = re.compile(r"^(```|~~~)\s*([A-Za-z0-9_+-]*)\s*$")
_PATH_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+)(?![A-Za-z0-9_./-])")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_ARCHITECTURE_KEYWORDS = {
    "architecture": ("architecture", "system", "component", "service", "subsystem"),
    "interfaces": ("interface", "api", "route", "handler", "endpoint", "cli"),
    "data": ("database", "schema", "table", "query", "storage", "migration"),
    "operations": ("deploy", "infra", "worker", "queue", "job", "cron"),
}


class _NoOpSemanticProvider:
    backend = "none"

    def enrich(self, _: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "graph": {"nodes": [], "edges": [], "hyperedges": []},
            "summary": {
                "backend": self.backend,
                "chunkCount": 0,
                "nodeCount": 0,
                "edgeCount": 0,
                "hyperedgeCount": 0,
                "providerEnrichmentSkipped": True,
                "message": "Semantic provider backend is disabled for this phase.",
            },
            "warnings": [],
        }


def _slug(value: str) -> str:
    return make_id(value) or "item"


def _make_doc_node(
    node_id: str,
    label: str,
    source_file: str,
    kind: str,
    *,
    language: str,
    source_location: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "id": node_id,
        "label": label,
        "source_file": source_file,
        "file_type": "document",
        "kind": kind,
        "language": language,
    }
    if source_location is not None:
        node["source_location"] = source_location
    if extra:
        node.update(extra)
    return node


def _make_edge(
    source: str,
    target: str,
    relation: str,
    confidence: str,
    source_file: str,
    *,
    source_location: dict[str, int] | None = None,
) -> dict[str, Any]:
    edge = {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": confidence,
        "source_file": source_file,
    }
    if source_location is not None:
        edge["source_location"] = source_location
    return edge


def _doc_language_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".mdx":
        return "mdx"
    if suffix == ".md":
        return "markdown"
    if suffix == ".rst":
        return "rst"
    return "text"


def _reference_language_for_path(path: str) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".sql": "sql",
    }.get(Path(path).suffix.lower(), "unknown")


def _eligible_documents(inventory: list[dict[str, Any]], semantic_config: SemanticConfig) -> list[dict[str, Any]]:
    include_types = set(semantic_config.include_file_types)
    include_extensions = set(semantic_config.include_extensions)
    selected = []
    for item in inventory:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if not path:
            continue
        suffix = Path(path).suffix.lower()
        if str(item.get("fileType", "")).lower() not in include_types:
            continue
        if include_extensions and suffix not in include_extensions:
            continue
        selected.append(item)
    return sorted(selected, key=lambda entry: entry["path"])


def _parse_rst_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    headings: list[tuple[int, int, str]] = []
    for index in range(len(lines) - 1):
        title = lines[index].strip()
        underline = lines[index + 1].strip()
        if not title or len(underline) < len(title):
            continue
        if len(set(underline)) != 1 or underline[0] not in _RST_UNDERLINE_CHARS:
            continue
        level = {"=": 1, "-": 2, "~": 3, "^": 4}.get(underline[0], 5)
        headings.append((index + 1, level, title))
    return headings


def _split_sections(path: str, content: str) -> tuple[str, list[dict[str, Any]]]:
    lines = content.splitlines()
    suffix = Path(path).suffix.lower()
    heading_markers: list[tuple[int, int, str]] = []
    if suffix in {".md", ".mdx"}:
        for line_number, line in enumerate(lines, start=1):
            match = _HEADING_RE.match(line)
            if match:
                heading_markers.append((line_number, len(match.group(1)), match.group(2).strip()))
    elif suffix == ".rst":
        heading_markers = _parse_rst_headings(lines)

    title = Path(path).stem
    if heading_markers:
        title = heading_markers[0][2]
    else:
        for line in lines:
            stripped = line.strip()
            if stripped:
                title = stripped[:120]
                break

    sections: list[dict[str, Any]] = []
    if not heading_markers:
        sections.append(
            {
                "ordinal": 0,
                "id_suffix": "root",
                "title": title,
                "level": 1,
                "start_line": 1,
                "end_line": max(1, len(lines)),
                "content_lines": lines,
            }
        )
        return title, sections

    first_heading_line = heading_markers[0][0]
    if first_heading_line > 1:
        sections.append(
            {
                "ordinal": 0,
                "id_suffix": "intro",
                "title": f"{title} Intro",
                "level": 1,
                "start_line": 1,
                "end_line": first_heading_line - 1,
                "content_lines": lines[: first_heading_line - 1],
            }
        )

    section_offset = len(sections)
    for marker_index, (line_number, level, heading_title) in enumerate(heading_markers):
        ordinal = section_offset + marker_index
        next_line = heading_markers[marker_index + 1][0] if marker_index + 1 < len(heading_markers) else len(lines) + 1
        sections.append(
            {
                "ordinal": ordinal,
                "id_suffix": f"section-{line_number}-{_slug(heading_title)}",
                "title": heading_title,
                "level": level,
                "start_line": line_number,
                "end_line": next_line - 1,
                "content_lines": lines[line_number - 1 : next_line - 1],
            }
        )
    return title, sections


def _extract_code_blocks(path: str, lines: list[str], section_line_ranges: list[tuple[int, int, str]]) -> list[dict[str, Any]]:
    code_blocks: list[dict[str, Any]] = []
    if Path(path).suffix.lower() not in {".md", ".mdx", ".rst"}:
        return code_blocks

    start_line = None
    fence = ""
    language = ""
    for line_number, line in enumerate(lines, start=1):
        match = _FENCED_CODE_RE.match(line)
        if match and start_line is None:
            start_line = line_number
            fence = match.group(1)
            language = match.group(2) or ""
            continue
        if start_line is not None and line.startswith(fence):
            parent_section_id = section_line_ranges[0][2] if section_line_ranges else ""
            for section_start, section_end, section_id in section_line_ranges:
                if section_start <= start_line <= section_end:
                    parent_section_id = section_id
                    break
            code_blocks.append(
                {
                    "ordinal": len(code_blocks),
                    "start_line": start_line,
                    "end_line": line_number,
                    "language_hint": language or None,
                    "parent_section_id": parent_section_id,
                }
            )
            start_line = None
            fence = ""
            language = ""
    return code_blocks


def _tokenize_symbol_candidates(content: str) -> set[str]:
    candidates = {match.group(1).strip() for match in _BACKTICK_RE.finditer(content)}
    for candidate in list(candidates):
        if candidate.endswith("()"):
            candidates.add(candidate[:-2])
    return {item for item in candidates if item}


def _symbol_index(code_graph: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    file_paths: dict[str, str] = {}
    for node in code_graph.get("nodes", []):
        source_file = str(node.get("source_file", ""))
        label = str(node.get("label", ""))
        if source_file and str(node.get("kind", "")) == "file":
            file_paths[source_file] = node["id"]
        if str(node.get("file_type", "")) == "code" and str(node.get("kind", "")) != "file":
            normalized = label.lower()
            by_label[normalized].append(node)
            if label.endswith("()"):
                by_label[label[:-2].lower()].append(node)
    return by_label, file_paths


def _match_references(
    *,
    path: str,
    content: str,
    source_id: str,
    source_line: int,
    inventory_paths: set[str],
    symbol_nodes: dict[str, list[dict[str, Any]]],
    code_file_nodes: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    references: list[dict[str, Any]] = []
    summary_items: list[dict[str, Any]] = []
    target_nodes: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for match in _PATH_TOKEN_RE.finditer(content):
        token = match.group(1).strip("./")
        if token not in inventory_paths:
            continue
        target_id = code_file_nodes.get(token, make_file_id(token))
        key = (token, target_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        target_nodes.append(
            {
                "id": target_id,
                "label": token,
                "source_file": token,
                "file_type": "code",
                "kind": "file",
                "language": _reference_language_for_path(token),
                "source_location": build_location(1, 0),
            }
        )
        references.append(
            _make_edge(
                source_id,
                target_id,
                "references",
                "EXTRACTED",
                path,
                source_location=build_location(source_line),
            )
        )
        summary_items.append({"kind": "path", "target": token, "targetId": target_id, "confidence": "EXTRACTED"})

    for candidate in sorted(_tokenize_symbol_candidates(content)):
        matches = symbol_nodes.get(candidate.lower(), [])
        if len(matches) != 1:
            continue
        target = matches[0]
        key = (candidate, target["id"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        target_nodes.append(dict(target))
        references.append(
            _make_edge(
                source_id,
                target["id"],
                "references",
                "INFERRED",
                path,
                source_location=build_location(source_line),
            )
        )
        summary_items.append(
            {
                "kind": "symbol",
                "target": candidate,
                "targetId": target["id"],
                "confidence": "INFERRED",
            }
        )

    return target_nodes, references, summary_items


def _document_chunks(content: str, semantic_config: SemanticConfig) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in content.splitlines(keepends=True):
        if len(current.encode("utf8")) + len(line.encode("utf8")) > semantic_config.max_chunk_bytes and current:
            chunks.append(current)
            current = ""
            if len(chunks) >= semantic_config.max_chunks_per_document:
                break
        current += line
    if current and len(chunks) < semantic_config.max_chunks_per_document:
        chunks.append(current)
    return chunks


def _theme_matches(section_title: str, content: str) -> list[str]:
    lowered = f"{section_title}\n{content}".lower()
    return [theme for theme, keywords in _ARCHITECTURE_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]


def _rationale_snippet(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("~~~"):
            continue
        return stripped[:240]
    return None


def run_semantic_extraction(
    *,
    repo_root: Path,
    inventory: list[dict[str, Any]],
    semantic_config: SemanticConfig,
    code_graph: dict[str, Any],
) -> dict[str, Any]:
    if not semantic_config.enabled:
        return {
            "enabled": False,
            "graph": {"nodes": [], "edges": [], "hyperedges": []},
            "warnings": [],
            "files": {},
            "documents": [],
            "summary": {
                "enabled": False,
                "mode": semantic_config.mode,
                "backend": semantic_config.backend,
                "providerEnrichmentSkipped": True,
                "selectedDocumentCount": 0,
                "processedDocumentCount": 0,
                "skippedDocumentCount": 0,
                "nodeCount": 0,
                "edgeCount": 0,
                "hyperedgeCount": 0,
                "warningCount": 0,
            },
        }

    selected_docs = _eligible_documents(inventory, semantic_config)
    inventory_paths = {str(item.get("path", "")) for item in inventory if isinstance(item, dict) and item.get("path")}
    symbol_nodes, code_file_nodes = _symbol_index(code_graph)
    deterministic_fragments: list[dict[str, Any]] = []
    file_summaries: dict[str, dict[str, Any]] = {}
    document_records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    provider_chunks: list[dict[str, Any]] = []

    for item in selected_docs:
        path = item["path"]
        abs_path = repo_root / path
        size_bytes = int(item.get("sizeBytes", 0) or 0)
        if size_bytes > semantic_config.max_document_bytes:
            file_summaries[path] = {
                "status": "skipped",
                "reason": "max_document_bytes_exceeded",
                "title": Path(path).stem,
                "sectionCount": 0,
                "codeBlockCount": 0,
                "referenceCount": 0,
                "backend": semantic_config.backend,
                "providerStatus": "skipped",
            }
            document_records.append(
                {
                    "path": path,
                    "title": Path(path).stem,
                    "status": "skipped",
                    "reason": "max_document_bytes_exceeded",
                    "sections": [],
                    "references": [],
                    "themes": [],
                    "rationaleSnippets": [],
                    "fileType": item.get("fileType"),
                }
            )
            warnings.append({"path": path, "stage": "semantic", "message": "Skipped oversized document for semantic extraction."})
            continue

        try:
            content = abs_path.read_text(encoding="utf8")
        except UnicodeDecodeError:
            file_summaries[path] = {
                "status": "skipped",
                "reason": "decode_error",
                "title": Path(path).stem,
                "sectionCount": 0,
                "codeBlockCount": 0,
                "referenceCount": 0,
                "backend": semantic_config.backend,
                "providerStatus": "skipped",
            }
            document_records.append(
                {
                    "path": path,
                    "title": Path(path).stem,
                    "status": "skipped",
                    "reason": "decode_error",
                    "sections": [],
                    "references": [],
                    "themes": [],
                    "rationaleSnippets": [],
                    "fileType": item.get("fileType"),
                }
            )
            warnings.append({"path": path, "stage": "semantic", "message": "Skipped document due to UTF-8 decode error."})
            continue

        language = _doc_language_for_path(path)
        title, sections = _split_sections(path, content)
        lines = content.splitlines()
        file_id = make_file_id(path)
        nodes = [
            _make_doc_node(
                file_id,
                path,
                path,
                "document",
                language=language,
                source_location=build_location(1, 0),
                extra={"title": title, "semantic_role": "document"},
            )
        ]
        edges: list[dict[str, Any]] = []
        section_ranges: list[tuple[int, int, str]] = []
        section_summaries: list[dict[str, Any]] = []
        doc_references: list[dict[str, Any]] = []
        rationale_snippets: list[str] = []
        theme_counts: Counter[str] = Counter()

        for section in sections:
            section_id = make_id("doc", path, section["id_suffix"])
            section_ranges.append((section["start_line"], section["end_line"], section_id))
            snippet = _rationale_snippet(section["content_lines"])
            if snippet:
                rationale_snippets.append(snippet)
            content_text = "\n".join(section["content_lines"]).strip()
            nodes.append(
                _make_doc_node(
                    section_id,
                    section["title"],
                    path,
                    "doc_section",
                    language=language,
                    source_location=build_location(section["start_line"]),
                    extra={
                        "section_level": section["level"],
                        "semantic_role": "section",
                        "title": section["title"],
                    },
                )
            )
            edges.append(
                _make_edge(
                    file_id,
                    section_id,
                    "contains",
                    "EXTRACTED",
                    path,
                    source_location=build_location(section["start_line"]),
                )
            )
            referenced_nodes, references, summary_items = _match_references(
                path=path,
                content=content_text,
                source_id=section_id,
                source_line=section["start_line"],
                inventory_paths=inventory_paths,
                symbol_nodes=symbol_nodes,
                code_file_nodes=code_file_nodes,
            )
            nodes.extend(referenced_nodes)
            edges.extend(references)
            doc_references.extend(summary_items)
            matched_themes = _theme_matches(section["title"], content_text)
            theme_counts.update(matched_themes)
            section_summaries.append(
                {
                    "id": section_id,
                    "title": section["title"],
                    "level": section["level"],
                    "startLine": section["start_line"],
                    "endLine": section["end_line"],
                    "referenceCount": len(summary_items),
                    "themes": matched_themes,
                }
            )

        code_blocks = _extract_code_blocks(path, lines, section_ranges)
        for block in code_blocks:
            code_block_id = make_id("doc", path, "code", str(block["start_line"]), str(block["ordinal"]))
            nodes.append(
                _make_doc_node(
                    code_block_id,
                    f"code:{block['language_hint'] or 'plain'}",
                    path,
                    "doc_code_block",
                    language=language,
                    source_location=build_location(block["start_line"]),
                    extra={
                        "semantic_role": "code_block",
                        "language_hint": block["language_hint"],
                    },
                )
            )
            edges.append(
                _make_edge(
                    block["parent_section_id"] or file_id,
                    code_block_id,
                    "contains",
                    "EXTRACTED",
                    path,
                    source_location=build_location(block["start_line"]),
                )
            )

        deterministic_fragment = merge_fragments([{"nodes": nodes, "edges": edges, "hyperedges": []}])
        deterministic_fragments.append(deterministic_fragment)

        chunks = _document_chunks(content, semantic_config)
        for index, chunk in enumerate(chunks):
            provider_chunks.append(
                {
                    "path": path,
                    "chunkIndex": index,
                    "text": chunk,
                    "title": title,
                }
            )

        file_summaries[path] = {
            "status": "ready",
            "reason": None,
            "title": title,
            "sectionCount": len(sections),
            "codeBlockCount": len(code_blocks),
            "referenceCount": len(doc_references),
            "backend": semantic_config.backend,
            "providerStatus": "skipped",
            "nodeCount": len(deterministic_fragment["nodes"]),
            "edgeCount": len(deterministic_fragment["edges"]),
            "themes": sorted(theme_counts),
        }
        document_records.append(
            {
                "path": path,
                "title": title,
                "status": "ready",
                "reason": None,
                "sections": section_summaries,
                "references": sorted(doc_references, key=lambda item: (item["kind"], item["target"], item["targetId"])),
                "themes": sorted(theme_counts),
                "rationaleSnippets": rationale_snippets[:5],
                "fileType": item.get("fileType"),
            }
        )

    provider = _NoOpSemanticProvider()
    provider_result = provider.enrich(provider_chunks)
    deterministic_graph = merge_fragments(deterministic_fragments or [{"nodes": [], "edges": [], "hyperedges": []}])
    merged_graph = merge_fragments([deterministic_graph, provider_result["graph"]])

    return {
        "enabled": True,
        "graph": merged_graph,
        "warnings": warnings + provider_result["warnings"],
        "files": file_summaries,
        "documents": document_records,
        "summary": {
            "enabled": True,
            "mode": semantic_config.mode,
            "backend": provider.backend,
            "providerEnrichmentSkipped": bool(provider_result["summary"].get("providerEnrichmentSkipped", True)),
            "selectedDocumentCount": len(selected_docs),
            "processedDocumentCount": sum(1 for item in document_records if item["status"] == "ready"),
            "skippedDocumentCount": sum(1 for item in document_records if item["status"] != "ready"),
            "nodeCount": len(merged_graph["nodes"]),
            "edgeCount": len(merged_graph["edges"]),
            "hyperedgeCount": len(merged_graph["hyperedges"]),
            "warningCount": len(warnings) + len(provider_result["warnings"]),
            "deterministicNodeCount": len(deterministic_graph["nodes"]),
            "deterministicEdgeCount": len(deterministic_graph["edges"]),
            "providerNodeCount": int(provider_result["summary"].get("nodeCount", 0)),
            "providerEdgeCount": int(provider_result["summary"].get("edgeCount", 0)),
            "chunkCount": len(provider_chunks),
        },
    }

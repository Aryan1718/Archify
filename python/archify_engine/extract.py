"""Phase 2 deterministic extraction for Python, JS/TS, and SQL."""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import (
    assert_valid_extraction,
    build_location,
    make_file_id,
    make_reference_id,
    make_symbol_id,
    merge_fragments,
)


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".sql": "sql",
}

JS_RESERVED_WORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "typeof",
    "new",
    "function",
    "class",
    "import",
    "export",
    "await",
    "else",
    "do",
    "const",
    "let",
    "var",
}


@dataclass
class ExtractionWarning:
    path: str
    language: str
    message: str


def _language_for_path(path: str) -> str:
    return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower(), "unknown")


def _make_node(
    node_id: str,
    label: str,
    source_file: str,
    file_type: str = "code",
    *,
    kind: str,
    language: str,
    source_location: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "id": node_id,
        "label": label,
        "source_file": source_file,
        "file_type": file_type,
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
    confidence_score: float | None = None,
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
    if confidence_score is not None:
        edge["confidence_score"] = confidence_score
    return edge


def _make_file_stub_node(path: str) -> dict[str, Any]:
    return _make_node(
        make_file_id(path),
        path,
        path,
        kind="file",
        language=_language_for_path(path),
        source_location=build_location(1, 0),
    )


def _finalize_fragment(payload: dict[str, Any]) -> dict[str, Any]:
    deduped = merge_fragments([payload])
    assert_valid_extraction(deduped)
    return deduped


def _is_language_enabled(language: str, config: dict[str, Any]) -> bool:
    scope = config.get("languageScope", {})
    include = {str(item).lower() for item in scope.get("include", []) if str(item).strip()}
    exclude = {str(item).lower() for item in scope.get("exclude", []) if str(item).strip()}
    if include and language.lower() not in include:
        return False
    return language.lower() not in exclude


def _resolve_python_import(module_name: str, rel_path: str, inventory_paths: set[str]) -> tuple[str | None, str]:
    if not module_name:
        return None, "AMBIGUOUS"

    pieces = module_name.split(".")
    candidates = [
        "/".join(pieces) + ".py",
        "/".join(pieces) + "/__init__.py",
    ]
    for candidate in candidates:
        if candidate in inventory_paths:
            return candidate, "INFERRED"

    base_parts = rel_path.split("/")[:-1]
    for depth in range(len(base_parts), -1, -1):
        prefix = "/".join(base_parts[:depth])
        for candidate in candidates:
            joined = f"{prefix}/{candidate}" if prefix else candidate
            if joined in inventory_paths:
                return joined, "INFERRED"

    return None, "AMBIGUOUS"


def _resolve_relative_module_path(specifier: str, rel_path: str, inventory_paths: set[str]) -> tuple[str | None, str]:
    if not specifier.startswith("."):
        return None, "EXTRACTED"

    base_dir = posixpath.dirname(rel_path)
    normalized_specifier = posixpath.normpath(posixpath.join(base_dir, specifier))
    normalized = Path(normalized_specifier)
    suffixes = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

    for suffix in suffixes:
        file_candidate = normalized if suffix == "" else Path(f"{normalized.as_posix()}{suffix}")
        if suffix == "" and file_candidate.suffix:
            if file_candidate.as_posix() in inventory_paths:
                return file_candidate.as_posix(), "INFERRED"
        elif file_candidate.as_posix() in inventory_paths:
            return file_candidate.as_posix(), "INFERRED"
    for index_name in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        dir_candidate = normalized / index_name
        if dir_candidate.as_posix() in inventory_paths:
            return dir_candidate.as_posix(), "INFERRED"

    return None, "AMBIGUOUS"


class _PythonExtractor(ast.NodeVisitor):
    def __init__(self, source_file: str, file_id: str, language: str, inventory_paths: set[str]):
        self.source_file = source_file
        self.file_id = file_id
        self.language = language
        self.inventory_paths = inventory_paths
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.known_symbols: dict[str, str] = {}
        self.class_stack: list[str] = []
        self.scope_stack: list[str] = [file_id]
        self.pending_calls: list[tuple[str, str, int]] = []

    def current_scope(self) -> str:
        return self.scope_stack[-1]

    def register_symbol(self, kind: str, name: str, line: int, qualname: str | None = None) -> str:
        resolved_qualname = qualname or name
        node_id = make_symbol_id(self.source_file, kind, resolved_qualname)
        label = f"{resolved_qualname}()" if kind in {"function", "method"} else resolved_qualname
        self.nodes.append(
            _make_node(
                node_id,
                label,
                self.source_file,
                kind=kind,
                language=self.language,
                source_location=build_location(line),
            )
        )
        self.edges.append(
            _make_edge(
                self.current_scope(),
                node_id,
                "contains",
                "EXTRACTED",
                self.source_file,
                source_location=build_location(line),
            )
        )
        self.known_symbols[name] = node_id
        if "." in resolved_qualname:
            self.known_symbols[resolved_qualname] = node_id
        return node_id

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            target_path, confidence = _resolve_python_import(alias.name, self.source_file, self.inventory_paths)
            if target_path is not None:
                target_id = make_file_id(target_path)
                self.nodes.append(_make_file_stub_node(target_path))
            else:
                target_id = make_reference_id(self.source_file, "import", alias.name)
                self.nodes.append(
                    _make_node(
                        target_id,
                        alias.name,
                        self.source_file,
                        file_type="concept",
                        kind="import_reference",
                        language=self.language,
                        source_location=build_location(node.lineno),
                    )
                )
            self.edges.append(
                _make_edge(
                    self.file_id,
                    target_id,
                    "imports",
                    confidence if target_path is not None else "EXTRACTED",
                    self.source_file,
                    source_location=build_location(node.lineno),
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = "." * node.level + (node.module or "")
        target_path, confidence = _resolve_python_import(module_name.lstrip("."), self.source_file, self.inventory_paths)
        if target_path is not None and node.level == 0:
            target_id = make_file_id(target_path)
            confidence_value = confidence
            self.nodes.append(_make_file_stub_node(target_path))
        else:
            target_id = make_reference_id(self.source_file, "import", module_name or ".")
            confidence_value = "AMBIGUOUS" if node.level > 0 else "EXTRACTED"
            self.nodes.append(
                _make_node(
                    target_id,
                    module_name or ".",
                    self.source_file,
                    file_type="concept",
                    kind="import_reference",
                    language=self.language,
                    source_location=build_location(node.lineno),
                )
            )
        self.edges.append(
            _make_edge(
                self.file_id,
                target_id,
                "imports",
                confidence_value,
                self.source_file,
                source_location=build_location(node.lineno),
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join([*self.class_stack, node.name]) if self.class_stack else node.name
        node_id = self.register_symbol("class", node.name, node.lineno, qualname)
        self.class_stack.append(node.name)
        self.scope_stack.append(node_id)
        self.generic_visit(node)
        self.scope_stack.pop()
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self.class_stack:
            qualname = ".".join([*self.class_stack, node.name])
            kind = "method"
        else:
            qualname = node.name
            kind = "function"
        node_id = self.register_symbol(kind, node.name, node.lineno, qualname)
        self.scope_stack.append(node_id)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callee_name = _python_callee_name(node.func)
        if callee_name:
            self.pending_calls.append((self.current_scope(), callee_name, node.lineno))
        self.generic_visit(node)

    def finalize(self) -> dict[str, Any]:
        for caller_id, callee_name, line in self.pending_calls:
            target_id = self.known_symbols.get(callee_name)
            if target_id is not None:
                confidence = "INFERRED"
            else:
                target_id = make_reference_id(self.source_file, "call", callee_name)
                self.nodes.append(
                    _make_node(
                        target_id,
                        callee_name,
                        self.source_file,
                        file_type="concept",
                        kind="call_reference",
                        language=self.language,
                        source_location=build_location(line),
                    )
                )
                confidence = "AMBIGUOUS"
            self.edges.append(
                _make_edge(
                    caller_id,
                    target_id,
                    "calls",
                    confidence,
                    self.source_file,
                    source_location=build_location(line),
                )
            )
        payload = {"nodes": self.nodes, "edges": self.edges, "hyperedges": []}
        return _finalize_fragment(payload)


def _python_callee_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return node.attr
    return None


def extract_python_file(path: Path, source_file: str, inventory_paths: set[str], language: str) -> dict[str, Any]:
    file_id = make_file_id(source_file)
    source = path.read_text(encoding="utf8")
    tree = ast.parse(source, filename=source_file)

    extractor = _PythonExtractor(source_file, file_id, language, inventory_paths)
    file_node = _make_node(
        file_id,
        source_file,
        source_file,
        kind="file",
        language=language,
        source_location=build_location(1, 0),
    )
    extractor.nodes.append(file_node)
    extractor.visit(tree)
    return extractor.finalize()


def extract_js_file(path: Path, source_file: str, inventory_paths: set[str], language: str) -> dict[str, Any]:
    file_id = make_file_id(source_file)
    source = path.read_text(encoding="utf8")
    lines = source.splitlines()
    nodes = [
        _make_node(
            file_id,
            source_file,
            source_file,
            kind="file",
            language=language,
            source_location=build_location(1, 0),
        )
    ]
    edges: list[dict[str, Any]] = []
    known_symbols: dict[str, str] = {}
    class_stack: list[tuple[str, int]] = []
    scope_stack: list[tuple[str, int]] = [(file_id, -1)]
    pending_calls: list[tuple[str, str, int]] = []
    brace_depth = 0

    import_pattern = re.compile(r"""(?:import|export)\s+.*?\s+from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)""")
    class_pattern = re.compile(r"^\s*export\s+class\s+([A-Za-z_$][\w$]*)|^\s*class\s+([A-Za-z_$][\w$]*)")
    function_pattern = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
    arrow_pattern = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")
    method_pattern = re.compile(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(")
    call_pattern = re.compile(r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(")

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        opening_braces = line.count("{")
        closing_braces = line.count("}")

        class_match = class_pattern.match(line)
        if class_match:
            class_name = class_match.group(1) or class_match.group(2)
            class_id = make_symbol_id(source_file, "class", class_name)
            nodes.append(
                _make_node(
                    class_id,
                    class_name,
                    source_file,
                    kind="class",
                    language=language,
                    source_location=build_location(line_number),
                )
            )
            edges.append(_make_edge(scope_stack[-1][0], class_id, "contains", "EXTRACTED", source_file, source_location=build_location(line_number)))
            known_symbols[class_name] = class_id
            if opening_braces > 0:
                class_stack.append((class_name, brace_depth + opening_braces))
                scope_stack.append((class_id, brace_depth + opening_braces))

        function_match = function_pattern.match(line) or arrow_pattern.match(line)
        if function_match:
            function_name = function_match.group(1)
            function_id = make_symbol_id(source_file, "function", function_name)
            nodes.append(
                _make_node(
                    function_id,
                    f"{function_name}()",
                    source_file,
                    kind="function",
                    language=language,
                    source_location=build_location(line_number),
                )
            )
            edges.append(_make_edge(scope_stack[-1][0], function_id, "contains", "EXTRACTED", source_file, source_location=build_location(line_number)))
            known_symbols[function_name] = function_id
            if opening_braces > 0:
                scope_stack.append((function_id, brace_depth + opening_braces))

        if class_stack and method_pattern.match(line) and not stripped.startswith(("if ", "for ", "while ", "switch ", "catch ")):
            method_name = method_pattern.match(line).group(1)
            if method_name != "constructor":
                class_name = class_stack[-1][0]
                qualname = f"{class_name}.{method_name}"
                method_id = make_symbol_id(source_file, "method", qualname)
                nodes.append(
                    _make_node(
                        method_id,
                        f"{qualname}()",
                        source_file,
                        kind="method",
                        language=language,
                        source_location=build_location(line_number),
                    )
                )
                edges.append(_make_edge(scope_stack[-1][0], method_id, "contains", "EXTRACTED", source_file, source_location=build_location(line_number)))
                known_symbols[method_name] = method_id
                known_symbols[qualname] = method_id
                if opening_braces > 0:
                    scope_stack.append((method_id, brace_depth + opening_braces))

        import_match = import_pattern.search(line)
        if import_match:
            specifier = import_match.group(1) or import_match.group(2)
            target_path, confidence = _resolve_relative_module_path(specifier, source_file, inventory_paths)
            if target_path is not None:
                target_id = make_file_id(target_path)
                nodes.append(_make_file_stub_node(target_path))
            else:
                target_id = make_reference_id(source_file, "import", specifier)
                nodes.append(
                    _make_node(
                        target_id,
                        specifier,
                        source_file,
                        file_type="concept",
                        kind="import_reference",
                        language=language,
                        source_location=build_location(line_number),
                    )
                )
            edges.append(
                _make_edge(
                    file_id,
                    target_id,
                    "imports",
                    confidence if target_path is not None else ("EXTRACTED" if not specifier.startswith(".") else "AMBIGUOUS"),
                    source_file,
                    source_location=build_location(line_number),
                )
            )

        for match in call_pattern.finditer(line):
            callee = match.group(1)
            root_name = callee.split(".", 1)[-1] if "." in callee else callee
            if root_name in JS_RESERVED_WORDS:
                continue
            if stripped.startswith(("function ", "class ", "import ", "export function", "export class")):
                continue
            pending_calls.append((scope_stack[-1][0], callee, line_number))

        brace_depth += opening_braces
        brace_depth -= closing_braces

        while len(scope_stack) > 1 and brace_depth < scope_stack[-1][1]:
            scope_stack.pop()
        while class_stack and brace_depth < class_stack[-1][1]:
            class_stack.pop()

    for caller_id, callee, line_number in pending_calls:
        lookup_name = callee.split(".", 1)[-1] if "." in callee else callee
        target_id = known_symbols.get(callee) or known_symbols.get(lookup_name)
        confidence = "INFERRED" if target_id is not None else "AMBIGUOUS"
        if target_id is None:
            target_id = make_reference_id(source_file, "call", callee)
            nodes.append(
                _make_node(
                    target_id,
                    callee,
                    source_file,
                    file_type="concept",
                    kind="call_reference",
                    language=language,
                    source_location=build_location(line_number),
                )
            )
        edges.append(_make_edge(caller_id, target_id, "calls", confidence, source_file, source_location=build_location(line_number)))

    payload = {"nodes": nodes, "edges": edges, "hyperedges": []}
    return _finalize_fragment(payload)


def extract_sql_file(path: Path, source_file: str, _: set[str], language: str) -> dict[str, Any]:
    file_id = make_file_id(source_file)
    source = path.read_text(encoding="utf8")
    nodes = [
        _make_node(
            file_id,
            source_file,
            source_file,
            kind="file",
            language=language,
            source_location=build_location(1, 0),
        )
    ]
    edges: list[dict[str, Any]] = []

    patterns = [
        ("table", "defines", re.compile(r"\bcreate\s+table\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "alters", re.compile(r"\balter\s+table\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "queries", re.compile(r"\bfrom\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "joins", re.compile(r"\bjoin\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "writes", re.compile(r"\binsert\s+into\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "updates", re.compile(r"\bupdate\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "deletes", re.compile(r"\bdelete\s+from\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
        ("table", "references", re.compile(r"\breferences\s+([A-Za-z_][\w.]*)", re.IGNORECASE)),
    ]

    for line_number, line in enumerate(source.splitlines(), start=1):
        for kind, relation, pattern in patterns:
            for match in pattern.finditer(line):
                label = match.group(1)
                node_id = make_reference_id(source_file, kind, label)
                nodes.append(
                    _make_node(
                        node_id,
                        label,
                        source_file,
                        file_type="concept",
                        kind=f"sql_{kind}",
                        language=language,
                        source_location=build_location(line_number),
                    )
                )
                edges.append(
                    _make_edge(
                        file_id,
                        node_id,
                        relation,
                        "EXTRACTED",
                        source_file,
                        source_location=build_location(line_number),
                    )
                )

    payload = {"nodes": nodes, "edges": edges, "hyperedges": []}
    return _finalize_fragment(payload)


def extract_file(path: Path, source_file: str, inventory_paths: set[str], config: dict[str, Any]) -> tuple[dict[str, Any], ExtractionWarning | None]:
    language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if language is None or not _is_language_enabled(language, config):
        return {"nodes": [], "edges": [], "hyperedges": []}, None

    try:
        if language == "python":
            return extract_python_file(path, source_file, inventory_paths, language), None
        if language in {"javascript", "typescript"}:
            return extract_js_file(path, source_file, inventory_paths, language), None
        if language == "sql":
            return extract_sql_file(path, source_file, inventory_paths, language), None
    except SyntaxError as error:
        return (
            {"nodes": [], "edges": [], "hyperedges": []},
            ExtractionWarning(source_file, language, f"Syntax error: {error.msg} at line {error.lineno}"),
        )
    except Exception as error:  # pragma: no cover - defensive boundary
        return (
            {"nodes": [], "edges": [], "hyperedges": []},
            ExtractionWarning(source_file, language, f"{type(error).__name__}: {error}"),
        )

    return {"nodes": [], "edges": [], "hyperedges": []}, None


def run_extraction(repo_root: Path, inventory: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    code_files = [item for item in inventory if item.get("fileType") == "code"]
    inventory_paths = {item["path"] for item in code_files}
    fragments: list[dict[str, Any]] = []
    warnings: list[ExtractionWarning] = []
    file_summaries: dict[str, dict[str, Any]] = {}

    for item in code_files:
        source_file = item["path"]
        path = repo_root / source_file
        language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")
        fragment, warning = extract_file(path, source_file, inventory_paths, config)
        fragments.append(fragment)
        if warning is not None:
            warnings.append(warning)
        file_summaries[source_file] = {
            "language": language,
            "status": "warning" if warning is not None else "ready",
            "nodeCount": len(fragment.get("nodes", [])),
            "edgeCount": len(fragment.get("edges", [])),
            "warning": warning.message if warning is not None else None,
        }

    merged = merge_fragments(fragments)
    return {
        "graph": merged,
        "warnings": [
            {
                "path": warning.path,
                "language": warning.language,
                "message": warning.message,
            }
            for warning in warnings
        ],
        "files": file_summaries,
        "summary": {
            "extractedFiles": len(code_files),
            "nodeCount": len(merged["nodes"]),
            "edgeCount": len(merged["edges"]),
            "hyperedgeCount": len(merged["hyperedges"]),
            "warningCount": len(warnings),
        },
    }

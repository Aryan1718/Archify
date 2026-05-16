"""Phase 1 repository scan and classification."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FILE_TYPES = ("code", "document", "config", "asset", "unknown")
ARCHITECTURE_TAGS = (
    "entrypoint",
    "route",
    "migration",
    "database",
    "infra",
    "dependency_manifest",
    "test",
    "docs",
    "generated",
)

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".tsx",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
}
DOCUMENT_EXTENSIONS = {
    ".md",
    ".mdx",
    ".txt",
    ".rst",
}
CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
}
ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
}

CONFIG_BASENAMES = {
    "dockerfile",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "tsconfig.base.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    ".env.example",
}

ENTRYPOINT_BASENAMES = {
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

DEPENDENCY_MANIFEST_BASENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
}

SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".archify",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    "target",
    "out",
}

SKIP_FILES = {
    ".archifyignore",
    "archify.config.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

SENSITIVE_PATTERNS = [
    re.compile(r"(^|[\\/])\.(env|envrc)(\.|$)", re.IGNORECASE),
    re.compile(r"\.(pem|key|p12|pfx|cert|crt|der|p8)$", re.IGNORECASE),
    re.compile(r"\b(credential|secret|passwd|password|token|private_key)s?\b", re.IGNORECASE),
    re.compile(r"(id_rsa|id_dsa|id_ecdsa|id_ed25519)(\.pub)?$", re.IGNORECASE),
    re.compile(r"(\.netrc|\.pgpass|\.htpasswd)$", re.IGNORECASE),
]

GENERATED_PATH_PATTERNS = [
    re.compile(r"(^|/)(dist|build|coverage|generated|gen|vendor)(/|$)", re.IGNORECASE),
]
ROUTE_PATH_PATTERNS = [
    re.compile(r"(^|/)(routes?|router|controllers?|api|handlers?)(/|$)", re.IGNORECASE),
]
MIGRATION_PATH_PATTERNS = [
    re.compile(r"(^|/)(migrations?|db/migrate)(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)\d{6,}[_-].+\.(sql|py|js|ts)$", re.IGNORECASE),
]
DATABASE_PATH_PATTERNS = [
    re.compile(r"(^|/)(db|database|schema|prisma|models?)(/|$)", re.IGNORECASE),
]
INFRA_PATH_PATTERNS = [
    re.compile(r"(^|/)(infra|infrastructure|deploy|deployment|ops|helm|k8s|kubernetes|terraform|\.github|\.gitlab)(/|$)", re.IGNORECASE),
]
DOCS_PATH_PATTERNS = [
    re.compile(r"(^|/)(docs?|adr|rfcs?)(/|$)", re.IGNORECASE),
]
TEST_PATH_PATTERNS = [
    re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)", re.IGNORECASE),
    re.compile(r"(^|/).+\.(test|spec)\.(js|jsx|ts|tsx|py)$", re.IGNORECASE),
]

SHEBANG_CODE_INTERPRETERS = {
    "python",
    "python3",
    "node",
    "nodejs",
    "bash",
    "sh",
    "zsh",
}


@dataclass(frozen=True)
class ScanConfig:
    repo_root: Path
    scan_root: Path
    output_dir: Path
    follow_symlinks: bool
    include_hidden: bool
    max_file_size_bytes: int
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]


def build_scan_config(config: dict[str, Any], repo_root: Path, scan_root: Path, output_dir: Path) -> ScanConfig:
    detect_config = config.get("analysis", {}).get("detect", {})
    return ScanConfig(
        repo_root=repo_root,
        scan_root=scan_root,
        output_dir=output_dir,
        follow_symlinks=bool(detect_config.get("followSymlinks", False)),
        include_hidden=bool(detect_config.get("includeHidden", False)),
        max_file_size_bytes=max(int(detect_config.get("maxFileSizeBytes", 1024 * 1024)), 1),
        include_globs=tuple(str(item) for item in detect_config.get("includeGlobs", []) if str(item).strip()),
        exclude_globs=tuple(str(item) for item in detect_config.get("excludeGlobs", []) if str(item).strip()),
    )


def parse_ignore_file(ignore_path: Path) -> list[str]:
    if not ignore_path.exists():
        return []

    patterns: list[str] = []
    for raw_line in ignore_path.read_text(encoding="utf8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_sensitive(path: Path) -> bool:
    return any(pattern.search(path.name) for pattern in SENSITIVE_PATTERNS)


def _shebang_is_code(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            first = handle.read(128)
    except OSError:
        return False

    if not first.startswith(b"#!"):
        return False

    line = first.split(b"\n", 1)[0].decode(errors="ignore")
    parts = line[2:].strip().split()
    if not parts:
        return False

    interpreter = parts[0].split("/")[-1]
    if interpreter == "env" and len(parts) > 1:
        interpreter = parts[1].split("/")[-1]
    return interpreter in SHEBANG_CODE_INTERPRETERS


def classify_file(path: Path) -> tuple[str, str]:
    basename = path.name
    lowered = basename.lower()
    suffix = path.suffix.lower()

    if lowered in CONFIG_BASENAMES:
        return "config", f"basename:{basename}"
    if lowered.startswith("docker-compose") and suffix in {".yml", ".yaml"}:
        return "config", "docker-compose"
    if suffix in CODE_EXTENSIONS:
        return "code", f"extension:{suffix}"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document", f"extension:{suffix}"
    if suffix in CONFIG_EXTENSIONS:
        return "config", f"extension:{suffix}"
    if suffix in ASSET_EXTENSIONS:
        return "asset", f"extension:{suffix}"
    if not suffix and _shebang_is_code(path):
        return "code", "shebang"
    return "unknown", "unsupported"


def classify_tags(path: Path, file_type: str) -> list[str]:
    rel = path.as_posix().lower()
    basename = path.name.lower()
    stem = path.stem.lower()
    tags: set[str] = set()

    if basename in ENTRYPOINT_BASENAMES or path.parent.name in {"bin", "scripts"}:
        tags.add("entrypoint")
    if stem in {"main", "app", "server", "cli"} and file_type == "code":
        tags.add("entrypoint")
    if any(pattern.search(rel) for pattern in ROUTE_PATH_PATTERNS):
        tags.add("route")
    if any(pattern.search(rel) for pattern in MIGRATION_PATH_PATTERNS):
        tags.add("migration")
    if any(pattern.search(rel) for pattern in DATABASE_PATH_PATTERNS) or path.suffix.lower() == ".sql":
        tags.add("database")
    if any(pattern.search(rel) for pattern in INFRA_PATH_PATTERNS) or basename == "dockerfile":
        tags.add("infra")
    if basename in DEPENDENCY_MANIFEST_BASENAMES:
        tags.add("dependency_manifest")
    if any(pattern.search(rel) for pattern in TEST_PATH_PATTERNS):
        tags.add("test")
    if file_type == "document" or any(pattern.search(rel) for pattern in DOCS_PATH_PATTERNS):
        tags.add("docs")
    if any(pattern.search(rel) for pattern in GENERATED_PATH_PATTERNS) or basename.endswith(".min.js"):
        tags.add("generated")

    return [tag for tag in ARCHITECTURE_TAGS if tag in tags]


def _matches_pattern(rel_path: str, pattern: str) -> bool:
    normalized = pattern.replace(os.sep, "/")
    if normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")
        return rel_path == normalized or rel_path.startswith(f"{normalized}/")
    return fnmatch.fnmatch(rel_path, normalized) or fnmatch.fnmatch(Path(rel_path).name, normalized)


def _is_ignored(rel_path: str, ignore_patterns: list[str], exclude_globs: tuple[str, ...], include_globs: tuple[str, ...]) -> bool:
    ignored = False
    for pattern in ignore_patterns:
        negated = pattern.startswith("!")
        raw = pattern[1:] if negated else pattern
        if _matches_pattern(rel_path, raw):
            ignored = not negated

    if any(_matches_pattern(rel_path, pattern) for pattern in exclude_globs):
        ignored = True

    if ignored and any(_matches_pattern(rel_path, pattern) for pattern in include_globs):
        ignored = False

    return ignored


def _should_skip_dir(dir_name: str, include_hidden: bool) -> bool:
    if dir_name in SKIP_DIRS:
        return True
    if not include_hidden and dir_name.startswith("."):
        return True
    return False


def _should_skip_hidden_file(name: str, include_hidden: bool) -> bool:
    return not include_hidden and name.startswith(".")


def _readable_size_warning(total_files: int) -> str | None:
    if total_files == 0:
        return "No supported repository files were discovered under the requested target."
    if total_files < 5:
        return "Very small scan result. Verify the target path and ignore rules if this repository should contain more source files."
    if total_files > 1000:
        return "Large scan result. Phase 2 extraction should likely start with narrowed scope or incremental support."
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_detection(scan_config: ScanConfig) -> dict[str, Any]:
    ignore_patterns = parse_ignore_file(scan_config.repo_root / ".archifyignore")
    inventory: list[dict[str, Any]] = []
    manifest: dict[str, dict[str, Any]] = {}
    counts_by_type = {file_type: 0 for file_type in FILE_TYPES}
    counts_by_tag = {tag: 0 for tag in ARCHITECTURE_TAGS}
    skipped = {
        "ignored": 0,
        "sensitive": 0,
        "hidden": 0,
        "unsupported": 0,
        "oversized": 0,
    }
    extraction_candidates: list[str] = []

    for dirpath, dirnames, filenames in os.walk(scan_config.scan_root, followlinks=scan_config.follow_symlinks):
        dir_path = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not _should_skip_dir(name, scan_config.include_hidden)
        ]

        for filename in sorted(filenames):
            if filename in SKIP_FILES:
                continue
            if _should_skip_hidden_file(filename, scan_config.include_hidden):
                skipped["hidden"] += 1
                continue

            path = dir_path / filename
            rel_path = path.relative_to(scan_config.repo_root).as_posix()

            if _is_ignored(rel_path, ignore_patterns, scan_config.exclude_globs, scan_config.include_globs):
                skipped["ignored"] += 1
                continue
            if _is_sensitive(path):
                skipped["sensitive"] += 1
                continue
            if not scan_config.follow_symlinks and path.is_symlink():
                skipped["ignored"] += 1
                continue

            file_type, detection_reason = classify_file(path)
            if file_type == "unknown":
                skipped["unsupported"] += 1
                continue

            try:
                stat = path.stat()
            except OSError:
                skipped["ignored"] += 1
                continue

            if stat.st_size > scan_config.max_file_size_bytes and file_type in {"document", "config"}:
                skipped["oversized"] += 1
                continue

            tags = classify_tags(Path(rel_path), file_type)
            counts_by_type[file_type] += 1
            for tag in tags:
                counts_by_tag[tag] += 1

            inventory_record = {
                "path": rel_path,
                "fileType": file_type,
                "architectureTags": tags,
                "sizeBytes": stat.st_size,
                "mtime": stat.st_mtime,
                "detectionReason": detection_reason,
            }
            inventory.append(inventory_record)

            if file_type == "code":
                extraction_candidates.append(rel_path)

            manifest[rel_path] = {
                "mtime": stat.st_mtime,
                "sizeBytes": stat.st_size,
                "hash": _sha256_file(path),
                "fileType": file_type,
                "architectureTags": tags,
            }

    inventory.sort(key=lambda item: item["path"])
    extraction_candidates.sort()

    return {
        "scanRoot": scan_config.scan_root.relative_to(scan_config.repo_root).as_posix() or ".",
        "inventory": inventory,
        "manifest": manifest,
        "totals": {
            "files": len(inventory),
            "byFileType": counts_by_type,
            "byArchitectureTag": counts_by_tag,
        },
        "extractionCandidates": extraction_candidates,
        "skipped": skipped,
        "warning": _readable_size_warning(len(inventory)),
        "ignorePatternCount": len(ignore_patterns),
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf8")


def diff_detection_against_manifest(
    detection: dict[str, Any],
    previous_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_files = {}
    if isinstance(previous_manifest, dict):
        raw_files = previous_manifest.get("files", {})
        if isinstance(raw_files, dict):
            previous_files = {
                str(path): metadata
                for path, metadata in raw_files.items()
                if isinstance(path, str) and isinstance(metadata, dict)
            }

    current_files = detection.get("manifest", {})
    unchanged_files: list[str] = []
    new_or_changed_files: list[str] = []

    for path, metadata in current_files.items():
        previous = previous_files.get(path)
        if not isinstance(previous, dict):
            new_or_changed_files.append(path)
            continue
        if (
            previous.get("hash") == metadata.get("hash")
            and previous.get("fileType") == metadata.get("fileType")
            and previous.get("architectureTags") == metadata.get("architectureTags")
        ):
            unchanged_files.append(path)
            continue
        new_or_changed_files.append(path)

    deleted_files = sorted(path for path in previous_files if path not in current_files)
    changed_code_files = sorted(
        path for path in new_or_changed_files if current_files.get(path, {}).get("fileType") == "code"
    )
    changed_semantic_files = sorted(
        path for path in new_or_changed_files if current_files.get(path, {}).get("fileType") == "document"
    )
    reused_semantic_files = sorted(
        path for path in unchanged_files if current_files.get(path, {}).get("fileType") == "document"
    )
    reused_code_files = sorted(
        path for path in unchanged_files if current_files.get(path, {}).get("fileType") == "code"
    )

    return {
        "incrementalEligible": bool(previous_files),
        "new_or_changed_files": sorted(new_or_changed_files),
        "unchanged_files": sorted(unchanged_files),
        "deleted_files": deleted_files,
        "changed_code_files": changed_code_files,
        "changed_semantic_files": changed_semantic_files,
        "reused_code_files": reused_code_files,
        "reused_semantic_files": reused_semantic_files,
        "changedFileCount": len(new_or_changed_files),
        "deletedFileCount": len(deleted_files),
        "reusedFileCount": len(unchanged_files),
    }

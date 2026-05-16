"""Config normalization for the Python engine boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SemanticConfig:
    enabled: bool
    mode: str
    include_file_types: tuple[str, ...]
    include_extensions: tuple[str, ...]
    max_document_bytes: int
    max_chunks_per_document: int
    max_chunk_bytes: int
    backend: str


@dataclass(frozen=True)
class EngineConfig:
    repo_root: Path
    target_path: Path
    output_dir: Path
    semantic: SemanticConfig
    raw: dict[str, Any]


def normalize_config(repo_root: str, target_path: str, config: dict[str, Any]) -> EngineConfig:
    repo_root_path = Path(repo_root).resolve()
    output_dir_name = config.get("defaults", {}).get("outputDir", ".archify")
    semantic_config = config.get("analysis", {}).get("semantic", {})
    return EngineConfig(
        repo_root=repo_root_path,
        target_path=Path(target_path).resolve(),
        output_dir=repo_root_path / output_dir_name,
        semantic=SemanticConfig(
            enabled=bool(semantic_config.get("enabled", False)),
            mode=str(semantic_config.get("mode", "docs_first") or "docs_first"),
            include_file_types=tuple(
                str(item).strip().lower()
                for item in semantic_config.get("includeFileTypes", ["document"])
                if str(item).strip()
            )
            or ("document",),
            include_extensions=tuple(
                str(item).strip().lower()
                for item in semantic_config.get("includeExtensions", [".md", ".mdx", ".txt", ".rst"])
                if str(item).strip()
            )
            or (".md", ".mdx", ".txt", ".rst"),
            max_document_bytes=max(int(semantic_config.get("maxDocumentBytes", 262144)), 1),
            max_chunks_per_document=max(int(semantic_config.get("maxChunksPerDocument", 32)), 1),
            max_chunk_bytes=max(int(semantic_config.get("maxChunkBytes", 8192)), 1),
            backend=str(semantic_config.get("backend", "none") or "none").strip().lower(),
        ),
        raw=config,
    )

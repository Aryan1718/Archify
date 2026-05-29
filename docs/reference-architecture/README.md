# Graphify Reference Notes

This folder documents how `graphify` builds a repository-wide knowledge graph so the same base system can be studied and adapted for Archify without guessing at the architecture.

The reference implementation in this repo splits into a deterministic local pipeline for code and an optional semantic pipeline for non-code content. The safest implementation order is:

1. Build the code-first local graph pipeline.
2. Add incremental update behavior.
3. Add reports and graph exports.
4. Add semantic extraction for docs and media.
5. Add wiki/global graph features only if needed.

Use these notes with the source modules:

- `graphify/detect.py`
- `graphify/extract.py`
- `graphify/build.py`
- `graphify/cluster.py`
- `graphify/analyze.py`
- `graphify/report.py`
- `graphify/export.py`
- `graphify/wiki.py`
- `graphify/watch.py`
- `graphify/__main__.py`

Recommended reading order in this folder:

1. [pipeline-overview.md](./pipeline-overview.md)
2. [code-extraction.md](./code-extraction.md)
3. [semantic-extraction.md](./semantic-extraction.md)
4. [graph-assembly-and-analysis.md](./graph-assembly-and-analysis.md)
5. [architecture-context-layer.md](./architecture-context-layer.md)
6. [incremental-update-and-outputs.md](./incremental-update-and-outputs.md)
7. [customization-points.md](./customization-points.md)

Behavioral reference tests:

- `tests/test_pipeline.py`
- `tests/test_incremental.py`
- `tests/test_watch.py`
- `tests/test_wiki.py`

Minimum baseline the reference implementation should preserve:

- Repository scanning and file classification.
- Deterministic AST extraction for code.
- A shared graph schema for all extractors.
- Graph assembly plus community detection.
- Human-readable summary output and machine-readable `graph.json`.
- Incremental code-only updates that avoid re-running semantic extraction.

Extension note:

- [architecture-context-layer.md](./architecture-context-layer.md) describes the proposed intermediate layer that sits on top of `graph.json` and moves the system closer to software-architecture generation without changing the upstream Graphify outputs.

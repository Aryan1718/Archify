# Pipeline Overview

`graphify` is organized as a linear pipeline:

```text
detect -> extract -> build -> cluster -> analyze -> report -> export
```

That structure is stated in [ARCHITECTURE.md](/Users/csuftitan/Desktop/graphify/ARCHITECTURE.md) and is reflected in the code layout.

## Entry Points

Primary orchestration lives in [graphify/__main__.py](/Users/csuftitan/Desktop/graphify/graphify/__main__.py).

Important commands:

- `graphify extract <path>`: full extraction, including semantic/non-code stages.
- `graphify update <path>`: code-only rebuild path with no LLM dependency.
- `graphify cluster-only <path>`: rerun community detection and regenerate outputs from an existing graph.
- `graphify export callflow-html`: render an architecture page from `graph.json` and `GRAPH_REPORT.md`.

## Stage Responsibilities

### 1. Detect

[`graphify/detect.py`](/Users/csuftitan/Desktop/graphify/graphify/detect.py) scans the target tree, filters ignored or sensitive files, classifies content into `code`, `document`, `paper`, `image`, and `video`, and computes corpus-size metadata.

Outputs to preserve:

- A categorized file list.
- Corpus statistics such as total files and approximate word count.
- A manifest of extracted files for incremental behavior.

### 2. Extract

[`graphify/extract.py`](/Users/csuftitan/Desktop/graphify/graphify/extract.py) performs deterministic local extraction for code and markdown-like AST-supported files. The full product also adds semantic extraction for non-code content through the CLI pipeline.

Outputs to preserve:

- `nodes`
- `edges`
- optional `hyperedges`
- token accounting for semantic passes

### 3. Build

[`graphify/build.py`](/Users/csuftitan/Desktop/graphify/graphify/build.py) merges extraction fragments into one NetworkX graph, normalizes IDs, preserves direction on edges, tolerates legacy schema variants, and runs deduplication.

### 4. Cluster

[`graphify/cluster.py`](/Users/csuftitan/Desktop/graphify/graphify/cluster.py) groups nodes into communities using Leiden when available, otherwise Louvain, with follow-up splitting for oversized or low-cohesion clusters.

### 5. Analyze

[`graphify/analyze.py`](/Users/csuftitan/Desktop/graphify/graphify/analyze.py) derives graph-level insights:

- god nodes
- surprising connections
- suggested questions

### 6. Report

[`graphify/report.py`](/Users/csuftitan/Desktop/graphify/graphify/report.py) turns the graph and analysis results into `GRAPH_REPORT.md`.

### 7. Export

[`graphify/export.py`](/Users/csuftitan/Desktop/graphify/graphify/export.py) writes the durable products:

- `graph.json`
- `graph.html`
- Obsidian-style markdown outputs
- auxiliary graph formats

[`graphify/wiki.py`](/Users/csuftitan/Desktop/graphify/graphify/wiki.py) adds a wiki-style markdown layer when requested.

## Two Operating Modes To Mirror

### Full Extract Mode

Use this when building the graph from scratch or when non-code inputs changed. This mode may invoke semantic extraction and token-costing behavior.

### Incremental Update Mode

Use this when only code changed. [`graphify/watch.py`](/Users/csuftitan/Desktop/graphify/graphify/watch.py) is the practical reference: re-extract changed code files, preserve semantic nodes from the previous graph, recluster, and regenerate outputs.

## Implementation Order For A Clone

1. Reproduce `detect`, local `extract`, `build`, `cluster`, `analyze`, `report`, and `graph.json`.
2. Add `update` semantics based on `watch.py`.
3. Add HTML/wiki/report polish.
4. Add semantic and media extraction behind the same graph schema.

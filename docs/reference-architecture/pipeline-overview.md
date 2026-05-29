# Pipeline Overview

The reference implementation is organized as a linear pipeline:

```text
detect -> extract -> build -> cluster -> analyze -> report -> export
```

That structure is reflected in the reference implementation and its architecture docs.

## Entry Points

Primary orchestration lives in the CLI entrypoint layer.

Important commands:

- `extract <path>`: full extraction, including semantic/non-code stages.
- `update <path>`: code-only rebuild path with no LLM dependency.
- `cluster-only <path>`: rerun community detection and regenerate outputs from an existing graph.
- `export callflow-html`: render an architecture page from `graph.json` and `GRAPH_REPORT.md`.

## Stage Responsibilities

### 1. Detect

The detect stage scans the target tree, filters ignored or sensitive files, classifies content into `code`, `document`, `paper`, `image`, and `video`, and computes corpus-size metadata.

Outputs to preserve:

- A categorized file list.
- Corpus statistics such as total files and approximate word count.
- A manifest of extracted files for incremental behavior.

### 2. Extract

The extract stage performs deterministic local extraction for code and markdown-like AST-supported files. The full product also adds semantic extraction for non-code content through the CLI pipeline.

Outputs to preserve:

- `nodes`
- `edges`
- optional `hyperedges`
- token accounting for semantic passes

### 3. Build

The build stage merges extraction fragments into one graph, normalizes IDs, preserves direction on edges, tolerates legacy schema variants, and runs deduplication.

### 4. Cluster

The cluster stage groups nodes into communities using Leiden when available, otherwise Louvain, with follow-up splitting for oversized or low-cohesion clusters.

### 5. Analyze

The analyze stage derives graph-level insights:

- god nodes
- surprising connections
- suggested questions

### 6. Report

The report stage turns the graph and analysis results into `GRAPH_REPORT.md`.

### 7. Export

The export stage writes the durable products:

- `graph.json`
- `graph.html`
- Obsidian-style markdown outputs
- auxiliary graph formats

An optional wiki stage adds a wiki-style markdown layer when requested.

## Two Operating Modes To Mirror

### Full Extract Mode

Use this when building the graph from scratch or when non-code inputs changed. This mode may invoke semantic extraction and token-costing behavior.

### Incremental Update Mode

Use this when only code changed. The incremental update path should re-extract changed code files, preserve semantic nodes from the previous graph, recluster, and regenerate outputs.

## Implementation Order For Archify

1. Reproduce `detect`, local `extract`, `build`, `cluster`, `analyze`, `report`, and `graph.json`.
2. Add update semantics based on the incremental rebuild path.
3. Add HTML/wiki/report polish.
4. Add semantic and media extraction behind the same graph schema.

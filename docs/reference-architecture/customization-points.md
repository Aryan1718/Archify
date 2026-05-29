# Customization Points

This file is the boundary between "follow graphify closely" and "change behavior for our use case."

## Keep These Stable

These parts should stay close to graphify unless there is a strong reason not to:

- pipeline shape: `detect -> extract -> build -> cluster -> analyze -> report -> export`
- shared extraction schema
- graph-level confidence tagging
- incremental code-only update path
- durable `graph.json` plus human-readable report

Changing these early will make the adaptation harder to reason about and harder to validate against Graphify behavior.

## Best Places To Customize

### 1. File Intake Policy

Adjust:

- supported file extensions
- ignore patterns
- sensitive-file rules
- binary-to-text conversion coverage

Reference module:

- [`graphify/detect.py`](/Users/csuftitan/Desktop/graphify/graphify/detect.py)

### 2. Graph Ontology

Adjust:

- node categories
- relation vocabulary
- whether concept nodes are allowed
- hyperedge usage

Reference modules:

- [`graphify/extract.py`](/Users/csuftitan/Desktop/graphify/graphify/extract.py)
- [`graphify/build.py`](/Users/csuftitan/Desktop/graphify/graphify/build.py)

### 3. Confidence Policy

Adjust:

- when to emit `INFERRED`
- what qualifies as `AMBIGUOUS`
- whether low-confidence edges are filtered before export

Keep the tags themselves stable if downstream tools or reports depend on them.

### 4. Community And Ranking Logic

Adjust:

- community naming
- god-node ranking filters
- surprise scoring
- question suggestion heuristics

Reference modules:

- [`graphify/cluster.py`](/Users/csuftitan/Desktop/graphify/graphify/cluster.py)
- [`graphify/analyze.py`](/Users/csuftitan/Desktop/graphify/graphify/analyze.py)

### 5. Output Products

Adjust:

- report sections
- HTML/visualization style
- wiki generation
- cross-project global graph behavior

Reference modules:

- [`graphify/report.py`](/Users/csuftitan/Desktop/graphify/graphify/report.py)
- [`graphify/export.py`](/Users/csuftitan/Desktop/graphify/graphify/export.py)
- [`graphify/wiki.py`](/Users/csuftitan/Desktop/graphify/graphify/wiki.py)

## Recommended Clone Strategy

Phase 1:

- Implement code scanning, AST extraction, graph build, clustering, analysis, report, and `graph.json`.

Phase 2:

- Implement incremental update based on `watch.py`.

Phase 3:

- Add semantic extraction for selected non-code inputs.

Phase 4:

- Add optional products such as wiki, global graph, and callflow export.

## What To Decide Before Coding The Clone

- Which file types are in scope for v1.
- Whether non-code semantic extraction is part of v1 or v2.
- The exact node and relation vocabulary for your domain.
- Whether Archify must remain compatible with Graphify-style `graph.json`.
- Whether report consumers are humans only, agents only, or both.

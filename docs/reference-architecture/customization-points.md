# Customization Points

This file is the boundary between "follow the reference implementation closely" and "change behavior for the Archify use case."

## Keep These Stable

These parts should stay close to the reference implementation unless there is a strong reason not to:

- pipeline shape: `detect -> extract -> build -> cluster -> analyze -> report -> export`
- shared extraction schema
- graph-level confidence tagging
- incremental code-only update path
- durable `graph.json` plus human-readable report

Changing these early will make the adaptation harder to reason about and harder to validate against reference behavior.

## Best Places To Customize

### 1. File Intake Policy

Adjust:

- supported file extensions
- ignore patterns
- sensitive-file rules
- binary-to-text conversion coverage

Reference area:

- the detect stage

### 2. Graph Ontology

Adjust:

- node categories
- relation vocabulary
- whether concept nodes are allowed
- hyperedge usage

Reference areas:

- the extract stage
- the build stage

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

Reference areas:

- the cluster stage
- the analyze stage

### 5. Output Products

Adjust:

- report sections
- HTML/visualization style
- wiki generation
- cross-project global graph behavior

Reference areas:

- the report stage
- the export stage
- the optional wiki layer

## Recommended Adaptation Strategy

Phase 1:

- Implement code scanning, AST extraction, graph build, clustering, analysis, report, and `graph.json`.

Phase 2:

- Implement incremental update based on the update path.

Phase 3:

- Add semantic extraction for selected non-code inputs.

Phase 4:

- Add optional products such as wiki, global graph, and callflow export.

## What To Decide Before Coding The Adaptation

- Which file types are in scope for v1.
- Whether non-code semantic extraction is part of v1 or v2.
- The exact node and relation vocabulary for your domain.
- Whether Archify must remain compatible with the reference `graph.json` contract.
- Whether report consumers are humans only, agents only, or both.

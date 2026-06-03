# Incremental Update And Outputs

This is the operational part that makes the reference pipeline practical for ongoing development instead of one-shot analysis.

## Incremental Update Model

The best behavioral reference is the incremental update path, because it contains the code-only rebuild logic used by the reference implementation.

Key behaviors to preserve:

- Re-extract only changed code files when the caller provides a change set.
- Preserve existing semantic nodes and edges from the last `graph.json`.
- Evict nodes belonging to deleted or replaced source files.
- Re-run build, cluster, analyze, report, and export after the partial rebuild.
- Avoid LLM work for code-only changes.

This separation is one of the core reference-design wins. Archify should keep it unless the use case truly cannot distinguish code-only from semantic changes.

## Locking And Safety

The incremental rebuild path also includes practical protections:

- per-repo rebuild lock
- safe handling for corrupt prior `graph.json`
- optional force behavior when legitimate refactors reduce node count

These are worth copying into a real implementation, even if the first version is simpler.

## Output Set

The base reference outputs are:

- `reference-out/graph.json`
- `reference-out/GRAPH_REPORT.md`
- `reference-out/graph.html`

Optional outputs:

- wiki markdown under `reference-out/wiki/`
- callflow HTML derived from `graph.json` plus report metadata
- Obsidian vault export

These names describe the reference output contract. Archify maps the same concepts into `.archify/`.

## `graph.json` Requirements

The Archify adaptation should preserve these properties of the exported graph:

- node-link JSON shape
- per-node community annotation
- edge metadata with relation and confidence
- support for `hyperedges`
- compatibility with downstream query/export tools

## Wiki Layer

The optional wiki layer generates:

- `index.md`
- one article per community
- one article per god node

This should remain optional in Archify. It is a consumer of the graph, not a prerequisite for building it.

## Behavioral Tests To Mirror

The Archify adaptation should reproduce the intent of:

- pipeline tests
- incremental update tests
- update-path tests
- wiki-layer tests

Minimum acceptance checks:

- repeated runs on unchanged input are stable
- code-only updates do not require semantic extraction
- stale files are removed correctly
- reports and graph exports regenerate after updates

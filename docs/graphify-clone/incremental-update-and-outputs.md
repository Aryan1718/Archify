# Incremental Update And Outputs

This is the operational part that makes graphify practical for ongoing development instead of one-shot analysis.

## Incremental Update Model

The best reference is [`graphify/watch.py`](/Users/csuftitan/Desktop/graphify/graphify/watch.py), because it contains the code-only rebuild logic used by `graphify update`.

Key behaviors to preserve:

- Re-extract only changed code files when the caller provides a change set.
- Preserve existing semantic nodes and edges from the last `graph.json`.
- Evict nodes belonging to deleted or replaced source files.
- Re-run build, cluster, analyze, report, and export after the partial rebuild.
- Avoid LLM work for code-only changes.

This separation is one of the core graphify design wins. Your clone should keep it unless your use case truly cannot distinguish code-only from semantic changes.

## Locking And Safety

`watch.py` also includes practical protections:

- per-repo rebuild lock
- safe handling for corrupt prior `graph.json`
- optional force behavior when legitimate refactors reduce node count

These are worth copying into a real implementation, even if the first version is simpler.

## Output Set

The base graphify outputs are:

- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/graph.html`

Optional outputs:

- wiki markdown under `graphify-out/wiki/`
- callflow HTML derived from `graph.json` plus report metadata
- Obsidian vault export

## `graph.json` Requirements

The clone should preserve these properties of the exported graph:

- node-link JSON shape
- per-node community annotation
- edge metadata with relation and confidence
- support for `hyperedges`
- compatibility with downstream query/export tools

## Wiki Layer

[`graphify/wiki.py`](/Users/csuftitan/Desktop/graphify/graphify/wiki.py) generates:

- `index.md`
- one article per community
- one article per god node

This should remain optional in the clone. It is a consumer of the graph, not a prerequisite for building it.

## Behavioral Tests To Mirror

The clone should reproduce the intent of:

- [tests/test_pipeline.py](/Users/csuftitan/Desktop/graphify/tests/test_pipeline.py)
- [tests/test_incremental.py](/Users/csuftitan/Desktop/graphify/tests/test_incremental.py)
- [tests/test_watch.py](/Users/csuftitan/Desktop/graphify/tests/test_watch.py)
- [tests/test_wiki.py](/Users/csuftitan/Desktop/graphify/tests/test_wiki.py)

Minimum acceptance checks:

- repeated runs on unchanged input are stable
- code-only updates do not require semantic extraction
- stale files are removed correctly
- reports and graph exports regenerate after updates

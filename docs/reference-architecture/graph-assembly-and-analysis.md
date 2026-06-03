# Graph Assembly And Analysis

This layer is what turns independent extraction fragments into a navigable knowledge graph instead of a bag of parse results.

## Build Phase

The build stage does more than add nodes and edges.

Key behaviors to preserve:

- Accept both current and legacy edge-key shapes such as `edges` and `links`.
- Normalize node IDs and edge endpoints before dropping edges.
- Preserve original directed edge intent through `_src` and `_tgt`.
- Skip expected dangling edges that point at external or stdlib concepts.
- Merge `hyperedges` into graph metadata.

## Deduplication

The graph may receive overlapping entities from different extraction passes. The reference implementation handles this in layers:

- per-file extractor-level ID dedup
- graph-level node overwrite behavior on matching IDs
- optional semantic entity deduplication

For an Archify adaptation, keep dedup as an explicit subsystem. Do not bury it inside extractors.

## Community Detection

The cluster stage is the reference point here.

Key behaviors:

- Prefer Leiden if available.
- Fall back to Louvain.
- Convert directed graphs to undirected for clustering only.
- Split oversized communities.
- Re-split low-cohesion communities that are held together by broad hub nodes.
- Reindex communities by size for stable output ordering.

The adaptation should preserve community IDs as output metadata, not as hard-coded node properties created by extractors.

## Analysis Outputs

The analyze stage computes the summary features users actually consume.

### God Nodes

These are the highest-degree non-noise entities. The reference implementation explicitly filters out:

- file hub nodes
- concept-only nodes
- low-signal function/method stubs

Archify should keep this idea of excluding structural noise before ranking important nodes.

### Surprising Connections

The reference implementation ranks non-obvious edges using:

- confidence level
- cross-file or cross-community distance
- cross-file-type distance
- cross-repo distance
- peripheral-to-hub patterns

This is not just "show random inferred edges." The scoring logic is a major part of report quality.

### Suggested Questions

Suggested questions are derived from actual graph structure so the report points users toward the kinds of queries the graph can answer well.

## Report Contract

`GRAPH_REPORT.md` is not decorative. It is the navigation layer for users and agents. Archify should preserve that role:

- summarize graph size and extraction mix
- list god nodes
- highlight surprising connections
- summarize communities
- surface ambiguity and gaps
- provide graph-freshness cues

If your use case changes the report format, keep the same information density even if section names differ.

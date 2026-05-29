# Semantic Extraction

This is the part to follow for feature parity, but it should remain a layer on top of the code-first pipeline rather than the foundation.

## What It Covers

Per [docs/how-it-works.md](/Users/csuftitan/Desktop/graphify/docs/how-it-works.md), graphify extends beyond code into:

- markdown and text docs
- PDFs and papers
- images
- audio and video transcripts
- Google Workspace and Office conversions

All of those still end up in the same graph schema.

## Pipeline Position

Semantic extraction runs after a usable code graph already exists. That ordering matters because graphify uses graph structure from the code pass to improve later stages, including transcript prompting.

For an Archify adaptation, keep this sequencing:

1. Build a deterministic code graph first.
2. Convert non-code inputs into machine-readable sidecars when needed.
3. Chunk and semantically extract non-code content.
4. Merge semantic results into the same graph.

## Conversion Layer

`detect.py` and related helpers support turning some binary or pointer-style files into markdown-like text before semantic extraction.

Examples:

- `.docx` to markdown
- `.xlsx` to markdown and structural nodes
- Google Workspace shortcuts to markdown sidecars

For this adaptation, keep converters isolated from the semantic extractor itself. The semantic layer should consume normalized text or media transcripts, not raw product-specific formats.

## Media Handling

The current design in `docs/how-it-works.md` treats audio/video transcription as its own pass before generic semantic extraction. That is a good base to preserve:

- media becomes transcript text
- transcripts can be cached
- transcript text is then handled like any other semantic document

## Semantic Extractor Contract

Even when produced by a model, fragments must still match the same extraction schema used by AST extraction:

- nodes with stable IDs and labels
- edges with `relation` and `confidence`
- optional `hyperedges`

That shared contract is one of the most important design decisions to preserve.

## Merge Strategy

The semantic layer should never invent a second graph format. It should emit graph fragments and let `build.py` merge them with AST results.

Important behavior to keep:

- semantic output can overwrite AST node attributes when the same node ID is reused and richer metadata exists
- dedup happens after fragments are combined
- old semantic data can be preserved during code-only updates

## Use-Case Changes To Expect

This is the likeliest area for customization. Typical changes:

- different chunking rules
- a narrower ontology of node/edge types
- stricter confidence thresholds
- domain-specific prompt instructions
- selective support for file/media types

The adaptation should make those policy choices configurable without changing the base graph contract.

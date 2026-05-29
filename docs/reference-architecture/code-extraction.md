# Code Extraction

This is the base system to copy first. It is local, deterministic, and does not require model calls.

## Discovery And Classification

The detect stage is responsible for deciding what enters the graph.

Key behaviors to preserve:

- Extension-based classification with explicit sets such as `CODE_EXTENSIONS`.
- Shebang detection for extensionless executable scripts.
- Silent skipping of likely secret-bearing files.
- Optional classification of markdown/text as `paper` when the content matches academic-paper heuristics.

Implementation note for an Archify adaptation:

- Keep file classification separate from extraction.
- Make ignore rules and supported extensions configurable instead of scattering them across extractors.

## AST Extractor Shape

The extract stage dispatches by language and emits a shared extraction format:

```json
{
  "nodes": [],
  "edges": [],
  "hyperedges": []
}
```

Required node fields in practice:

- `id`
- `label`
- `source_file`
- `file_type`
- optional `source_location`

Required edge fields in practice:

- `source`
- `target`
- `relation`
- `confidence`
- optional `source_location`
- optional `confidence_score`

## Stable Node IDs

The adaptation should preserve the idea behind `_make_id()`:

- IDs are normalized and stable.
- IDs are derived from semantic names plus file context when needed.
- IDs are safe to merge across runs.

`_file_stem()` is also important because it prevents collisions for duplicate filenames in different directories.

## Language-Specific Rules

The reference implementation uses a generic extractor framework plus per-language configuration. Archify does not need to copy every supported language immediately, but it should preserve the architecture:

- A language config object.
- Shared AST walking logic.
- Per-language import handling.
- Per-language function/class/call node detection.

Important examples from the current implementation:

- Python import and relative import handling.
- JS/TS import path resolution, including `tsconfig` aliases and extensionless module resolution.
- AST-based call extraction with inferred edges from a second pass.

## Confidence Model In Code Extraction

The local extractor emits:

- `EXTRACTED` for direct syntax-backed relationships like imports and explicit calls.
- `INFERRED` for second-pass or resolver-based edges.
- `AMBIGUOUS` when a target cannot be resolved confidently.

The adaptation should keep confidence on the edge itself, not as a separate report-only concept.

## Validation Boundary

The reference architecture keeps a validation boundary before graph construction. Archify should keep this boundary:

- Extractors may vary.
- Graph construction should assume validated payloads.
- Broken extractor output should fail or warn before it enters the graph merge step.

## Baseline Acceptance Criteria

The code-first adaptation is acceptable when it can:

- Scan a repository and classify supported code files.
- Parse them into nodes and edges with stable IDs.
- Re-run on the same repository and produce stable counts.
- Preserve edge direction.
- Emit confidence-tagged structural relationships.

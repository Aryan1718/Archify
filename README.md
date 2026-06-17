<div align="center">

<pre>
    _              _     _  __
   / \   _ __ ___| |__ (_)/ _|_   _
  / _ \ | '__/ __| '_ \| | |_| | | |
 / ___ \| | | (__| | | | |  _| |_| |
/_/   \_\_|  \___|_| |_|_|_|  \__, |
                              |___/
</pre>

<p><code>npx archify-cli init</code></p>

</div>

`archify-cli` analyzes your repository and gives AI assistants the grounded context they need to write architecture docs.

## What It Does

Archify is built for repositories where you want architecture output based on actual code and docs instead of guesswork.

It can:

- scan the repository and build a grounded knowledge base in `.archify/`
- detect when existing analysis is still fresh and reuse it
- regenerate analysis only when the repository changes
- generate doc-specific packets and guides for assistant-driven writing
- write final root-level documents for supported doc types

## Who It Is For

Use Archify if you want to:

- understand an unfamiliar codebase faster
- generate architecture documentation from real repository evidence
- give Codex or Claude Code a grounded context pack before asking it to write docs
- keep architecture outputs refreshable as the codebase evolves

## Requirements

- `Node.js >= 20`
- `Python >= 3.11`
- an AI assistant workflow using Codex or Claude Code

Python is required because the analysis engine shipped inside the package is implemented in Python.

## Quick Start

From the repository root:

```bash
npx archify-cli init
```

Then tell your assistant:

```text
Use Archify on this repo
```

Typical flow:

1. Run `npx archify-cli init` once.
2. Ask your assistant to use Archify on the repo.
3. Archify checks status and decides whether it should analyze, generate, write, or reuse existing artifacts.

## Install Options

Run directly with `npx`:

```bash
npx archify-cli init
```

Or install it in a project:

```bash
npm i -D archify-cli
```

Then run:

```bash
npx archify-cli status
```

## Commands

| Command | Purpose |
| --- | --- |
| `npx archify-cli init` | Set up Archify in the current repository |
| `npx archify-cli status [--doc-type <type>]` | Show setup state, artifact freshness, and the next recommended action |
| `npx archify-cli analyze .` | Build or refresh grounded repository knowledge in `.archify/` |
| `npx archify-cli generate . [--doc-type <type>]` | Build the synthesis packet and guide for the selected document type |
| `npx archify-cli write . [--doc-type <type>]` | Write the selected root-level document from generated synthesis artifacts |
| `npx archify-cli clean` | Remove generated artifacts from `.archify/` |

## What Gets Created

Archify adds:

- `archify.config.json` for project configuration
- `.archifyignore` for scan exclusions
- project skill files for Codex or Claude Code installs
- `.archify/` for analysis, synthesis, and guide artifacts

Core artifacts include:

| File | Purpose |
| --- | --- |
| `archify.config.json` | Project-level Archify configuration |
| `.archifyignore` | Ignore rules for repository scanning |
| `.archify/manifest.json` | Analysis state and freshness metadata |
| `.archify/graph.json` | Repository graph output |
| `.archify/architecture-context.json` | Grounded architecture context |
| `.archify/docs/<docType>/packet.json` | Doc-scoped synthesis packet used to author the selected root document |
| `.archify/docs/<docType>/guide.json` | Section-by-section guide for generating the selected root document |
| `.archify/docs/<docType>/brief.md` | Human-readable synthesis brief |
| `.archify/docs/<docType>/guide.md` | Human-readable guide brief |

## Available Documents

Archify supports these document types:

| `--doc-type` value | Output file |
| --- | --- |
| `archify` | `archify.md` |
| `tech_stack` | `TECH_STACK.md` |
| `api_design` | `API_DESIGN.md` |
| `data_model` | `DATA_MODEL.md` |
| `conventions` | `CONVENTIONS.md` |
| `glossary` | `GLOSSARY.md` |
| `flows` | `FLOWS.md` |
| `test_cases` | `TEST_CASES.md` |

If `--doc-type` is omitted, Archify defaults to `archify` and writes `archify.md`.

Examples:

```bash
npx archify-cli status --doc-type tech_stack
npx archify-cli generate . --doc-type api_design
npx archify-cli write . --doc-type flows
```

## How The Analysis Works

Archify analyzes repository structure and supporting docs, including:

- source files
- routes and entrypoints
- dependencies
- database and migration files
- README and supporting architecture documents

The workflow is guide-driven:

- `analyze` produces grounded `.archify` artifacts
- `generate` produces a doc-scoped synthesis packet and guide
- `write` materializes the selected root document from those artifacts
- installed assistant skills read the selected packet and guide before drafting the final document

Grounded `.archify/` artifacts remain the primary source of confirmed facts.

## Notes

- `init` is the main setup command.
- `status` is the main inspection command.
- `analyze`, `generate`, and `write` are available for manual workflows, but the installed skill is designed to run them when needed.

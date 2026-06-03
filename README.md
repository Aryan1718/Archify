<div align="center">

<pre>
    _              _     _  __
   / \   _ __ ___| |__ (_)/ _|_   _
  / _ \ | '__/ __| '_ \| | |_| | | |
 / ___ \| | | (__| | | | |  _| |_| |
/_/   \_\_|  \___|_| |_|_|_|  \__, |
                              |___/
</pre>

<p><strong>Grounded codebase documentation</strong></p>

<p><code>npx archify init</code></p>

</div>

Archify extracts grounded architecture and codebase context from a repository so it is easier to study, understand, and build similar systems.

## Quick Start

From the root of the repository:

```bash
npx archify init
```

Then use Archify from your assistant:

```text
Use Archify on this repo
```

## What It Does

- Builds a grounded repository knowledge base inside `.archify/`
- Reuses existing artifacts when they are already fresh
- Refreshes analysis only when the repository has changed
- Generates synthesis packets and guide artifacts used to study the codebase and write `archify.md`

## How It Works

1. Run `npx archify init` once in the repository.
2. Ask your assistant to use Archify.
3. Archify checks status and decides what to do next.

What Archify does next:
- initialize if setup is missing
- analyze if knowledge is missing or stale
- generate if the design packet or guide artifacts are missing or stale
- reuse existing artifacts if everything is fresh

## Commands

| Command | Purpose |
| --- | --- |
| `npx archify init` | Set up Archify in the current repository |
| `npx archify status` | Show setup state, artifact freshness, and the next recommended action |
| `npx archify analyze .` | Build or refresh the grounded repository knowledge in `.archify/` |
| `npx archify generate .` | Build the synthesis packet and guide artifacts used for `archify.md` |
| `npx archify clean` | Remove generated artifacts from `.archify/` |

## Generated Files

Archify adds:

- `archify.config.json` for project configuration
- `.archifyignore` for scan exclusions
- project skill files for Codex or Claude Code installs
- `.archify/` for analysis, synthesis, and guide artifacts

## Core Artifacts

| File | Purpose |
| --- | --- |
| `archify.config.json` | Project-level Archify configuration |
| `.archifyignore` | Ignore rules for repository scanning |
| `.archify/manifest.json` | Analysis state and freshness metadata |
| `.archify/graph.json` | Repository graph output |
| `.archify/architecture-context.json` | Grounded architecture context |
| `.archify/design-packet.json` | Synthesis packet used to author `archify.md` |
| `.archify/archify.guide.json` | Section-by-section guide for generating `archify.md` |
| `archify.md` | Final architecture prompt pack written by the skill |

## Available Document

Today, Archify generates the grounded artifacts needed to produce:

- `archify.md`

## Planned Document Types

Archify is designed to extend the same `.archify` evidence model into additional document types:

- `TECH_STACK.md`
- `API_DESIGN.md`
- `DATA_MODEL.md`
- `CONVENTIONS.md`
- `GLOSSARY.md`
- `FLOWS.md`
- `TEST_CASES.md`

These outputs are planned and not generated yet.

All planned document names use uppercase snake case for consistency.

## Repository Understanding

Archify analyzes repository structure and documentation, including:

- source files
- routes and entrypoints
- dependencies
- database and migration files
- README and supporting architecture documents

Documentation generation is guide-driven:

- `analyze` produces grounded `.archify` artifacts
- `generate` produces a synthesis packet plus an `archify` guide
- the installed skill reads the packet and guide before drafting `archify.md`

## Notes

- `init` is the main setup command.
- `status` is the main inspection command.
- `analyze` and `generate` are available for manual workflows, but the installed skill is designed to run them when needed.
- Supporting docs such as `README.md` can be gathered alongside analysis, but grounded `.archify/` artifacts remain the primary source of confirmed facts.

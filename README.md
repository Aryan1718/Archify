# Archify

Archify helps an AI assistant understand a codebase before it writes architecture output.

It builds a grounded knowledge folder inside the repo, then lets the agent use that knowledge to explain the system, answer architecture questions, and prepare a final `archify.md` prompt pack.

## How it works

Archify has two parts:

1. A small CLI that sets up the repo and maintains the local `.archify/` knowledge folder.
2. An agent skill that uses that knowledge to do the real architecture work.

The normal user flow is simple:

1. Open the repository.
2. Run `npx archify init`
3. Ask your AI assistant to use Archify on the repo.

That is the main product flow.

## Quick start

From the root of the project you want to analyze:

```bash
npx archify init
```

This sets up the repo by creating:

- `archify.config.json`
- `.archifyignore`
- the Archify skill instructions for the supported agent

After that, ask your AI assistant something like:

- `Use Archify on this repo`
- `Use Archify to explain this codebase`
- `Use Archify to create architecture docs for this project`

The agent should handle the internal Archify steps for you.

## What gets created

When Archify runs analysis, it writes grounded artifacts into `.archify/`.

These artifacts can include:

- `graph.json`
- `facts.json`
- `modules.json`
- `routes.json`
- `database.json`
- `services.json`
- `dependencies.json`
- `docs-summary.json`
- `architecture-context.json`
- `architecture-context.md`
- `manifest.json`
- `design-packet.json`
- `design-brief.md`

In plain terms, this is the repo knowledge base that the agent uses.

## Main commands

Most users only need one command:

```bash
npx archify init
```

Other commands are available for maintenance or advanced use:

```bash
npx archify status
npx archify analyze .
npx archify generate .
npx archify clean
```

What they mean:

- `init` sets up Archify in the current repo.
- `status` shows whether Archify is installed and whether the repo knowledge is ready.
- `analyze` builds or refreshes the grounded knowledge in `.archify/`.
- `generate` builds the internal design packet used to create `archify.md`.
- `clean` removes generated artifacts from `.archify/`.

For most end users, `analyze` and `generate` are internal or advanced commands. The agent should usually run them when needed.

## Recommended user experience

The intended experience is:

1. Run `npx archify init` once in the repo.
2. Use your AI assistant normally.
3. Ask the assistant to use Archify when you want architecture understanding or architecture output.

The user should not need to manually think about:

- when to run `analyze`
- when to run `generate`
- when to re-read the README
- when to refresh the knowledge base

That logic belongs in the agent workflow.

## What Archify analyzes

Today Archify can:

- scan and classify repository files
- extract structure from Python, JavaScript, TypeScript, and SQL
- read markdown and text docs as supporting context
- build a graph of files, symbols, and relationships
- cluster and summarize the graph
- generate architecture-facing artifacts from grounded repo evidence

## Output philosophy

Archify tries to keep a clean separation between:

- confirmed facts from the codebase
- inferred architecture
- README or docs used as supporting context
- open questions that still need human confirmation

That separation is important because it makes the final architecture output more trustworthy.

## Current direction

Archify is being shaped around a simple model:

- the CLI handles setup and maintenance
- the agent handles the actual architecture workflow

That is why the main entry point for users is `npx archify init`, followed by asking their AI assistant to use Archify on the repo.

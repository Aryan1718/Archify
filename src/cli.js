import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  analyzeCommand,
  cleanCommand,
  generateCommand,
  initCommand,
  statusCommand,
  writeCommand
} from "./commands.js";
import { ArchifyError } from "./errors.js";

function printUsage() {
  console.log(`Archify Phase 0

Usage:
  npx archify init [--install-mode global]
  npx archify init [--install-mode project --project-path <path> --platform codex|claude-code|both]
  npx archify status [--doc-type <type>]
  npx archify analyze <path>
  npx archify generate <path> [--doc-type <type>]
  npx archify write <path> [--doc-type <type>] [--force]
  npx archify clean

Recommended flow:
  1. Run \`npx archify init\` once in the repository you want to work on.
  2. Ask your AI assistant to use Archify on that repo.
  3. Let the agent refresh \`.archify/\` knowledge and generate outputs internally.

Notes:
  - \`init\` is the normal setup command for end users.
  - \`analyze\` and \`generate\` are still available for manual or advanced workflows.
`);
}

function parseOptions(args) {
  const options = {};
  const positional = [];

  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];

    if (value === "--install-mode") {
      options.installMode = args[index + 1];
      index += 1;
      continue;
    }

    if (value === "--platform") {
      options.platform = args[index + 1];
      index += 1;
      continue;
    }

    if (value === "--project-path") {
      options.projectPath = args[index + 1];
      index += 1;
      continue;
    }

    if (value === "--help" || value === "-h") {
      options.help = true;
      continue;
    }

    if (value === "--force") {
      options.force = true;
      continue;
    }

    if (value === "--doc-type") {
      options.docType = args[index + 1];
      index += 1;
      continue;
    }

    positional.push(value);
  }

  return { options, positional };
}

function printResult(result) {
  console.log(JSON.stringify(result, null, 2));
}

export async function main(argv) {
  const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const repoRoot = process.cwd();
  const { options, positional } = parseOptions(argv);
  const [command, ...rest] = positional;

  if (options.help) {
    printUsage();
    process.exitCode = 0;
    return;
  }

  try {
    let result;

    switch (command || "init") {
      case "init":
        result = await initCommand(repoRoot, options);
        break;
      case "status":
        result = await statusCommand(repoRoot, options);
        break;
      case "analyze":
        result = await analyzeCommand(appRoot, repoRoot, rest[0]);
        break;
      case "generate":
        result = await generateCommand(appRoot, repoRoot, rest[0], options);
        break;
      case "write":
        result = await writeCommand(appRoot, repoRoot, rest[0], options);
        break;
      case "clean":
        result = await cleanCommand(repoRoot);
        break;
      default:
        throw new ArchifyError(`Unknown command "${command}".`, {
          code: "COMMAND_UNKNOWN",
          exitCode: 2
        });
    }

    printResult(result);
  } catch (error) {
    const err = error instanceof ArchifyError
      ? error
      : new ArchifyError(error.message || String(error));
    console.error(`[${err.code}] ${err.message}`);
    process.exitCode = err.exitCode;
  }
}

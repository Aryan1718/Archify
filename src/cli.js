import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  analyzeCommand,
  cleanCommand,
  generateCommand,
  initCommand
} from "./commands.js";
import { ArchifyError } from "./errors.js";

function printUsage() {
  console.log(`Archify Phase 0

Usage:
  npx archify [--install-mode global]
  npx archify [--install-mode project --project-path <path> --platform codex|claude-code|both]
  npx archify init [--install-mode global]
  npx archify init [--install-mode project --project-path <path> --platform codex|claude-code|both]
  npx archify analyze <path>
  npx archify generate <path>
  npx archify clean

Recommended flow:
  1. Run \`npx archify\` once and choose a shared global install or a project path plus one-or-more platforms.
  2. Invoke the installed \`archify\` skill in your agent.
  3. Let the skill run \`analyze\` and \`generate\` internally.
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
      case "analyze":
        result = await analyzeCommand(appRoot, repoRoot, rest[0]);
        break;
      case "generate":
        result = await generateCommand(appRoot, repoRoot, rest[0]);
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

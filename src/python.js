import path from "node:path";
import { spawnSync } from "node:child_process";

import { ArchifyError } from "./errors.js";

function getPythonLaunchers() {
  const configured = process.env.ARCHIFY_PYTHON?.trim();
  if (configured) {
    return [{ command: configured, args: [] }];
  }

  if (process.platform === "win32") {
    return [
      { command: "python", args: [] },
      { command: "py", args: ["-3"] },
      { command: "python3", args: [] }
    ];
  }

  return [
    { command: "python3", args: [] },
    { command: "python", args: [] }
  ];
}

export function runPythonEngine({ appRoot, repoRoot, command, targetPath, config, docType }) {
  const pythonRoot = path.join(appRoot, "python");
  const args = [
    "-m",
    "archify_engine.cli",
    command,
    "--repo-root",
    repoRoot,
    "--target-path",
    targetPath,
    "--config-json",
    JSON.stringify(config)
  ];
  if (docType) {
    args.push("--doc-type", docType);
  }

  const existingPythonPath = process.env.PYTHONPATH;
  const pythonPath = existingPythonPath
    ? `${pythonRoot}${path.delimiter}${existingPythonPath}`
    : pythonRoot;

  let result;
  let startError;
  for (const launcher of getPythonLaunchers()) {
    result = spawnSync(launcher.command, [...launcher.args, ...args], {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: pythonPath
      },
      encoding: "utf8"
    });

    if (!result.error) {
      startError = null;
      break;
    }

    startError = result.error;
  }

  if (startError) {
    throw new ArchifyError(
      `Failed to start Python engine: ${startError.message}`,
      { code: "PYTHON_ENGINE_START_FAILED", exitCode: 2 }
    );
  }

  if (result.status !== 0) {
    const stderr = result.stderr.trim() || result.stdout.trim() || "Unknown Python engine error";
    throw new ArchifyError(
      `Python engine failed for "${command}": ${stderr}`,
      { code: "PYTHON_ENGINE_FAILED", exitCode: result.status || 1 }
    );
  }

  try {
    return JSON.parse(result.stdout);
  } catch (error) {
    throw new ArchifyError(
      `Python engine returned invalid JSON for "${command}": ${error.message}`,
      { code: "PYTHON_ENGINE_INVALID_OUTPUT", exitCode: 2 }
    );
  }
}

import path from "node:path";
import { spawnSync } from "node:child_process";

import { ArchifyError } from "./errors.js";

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

  const result = spawnSync("python3", args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: pythonPath
    },
    encoding: "utf8"
  });

  if (result.error) {
    throw new ArchifyError(
      `Failed to start Python engine: ${result.error.message}`,
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

import fs from "node:fs/promises";
import path from "node:path";

import {
  OPERATIONAL_ARTIFACTS,
  OUTPUT_DIR,
  REQUIRED_GENERATE_ARTIFACTS,
  RESERVED_ARTIFACTS
} from "./constants.js";
import { ensureConfig, ensureIgnoreFile, ensureOutputDir, loadConfig } from "./config.js";
import { ArchifyError } from "./errors.js";
import { pathExists, removeContents } from "./fs-utils.js";
import { resolveSetupOptions } from "./prompt.js";
import { runPythonEngine } from "./python.js";
import { installSkillTemplates } from "./skills.js";

function resolveTargetPath(repoRoot, inputPath) {
  const targetPath = path.resolve(repoRoot, inputPath ?? ".");
  return targetPath;
}

async function validateTargetPath(targetPath) {
  const exists = await pathExists(targetPath);
  if (!exists) {
    throw new ArchifyError(`Target path does not exist: ${targetPath}`, {
      code: "TARGET_MISSING",
      exitCode: 2
    });
  }
}

async function validateGenerateArtifacts(repoRoot, outputDir) {
  const missing = [];

  for (const artifact of REQUIRED_GENERATE_ARTIFACTS) {
    const artifactPath = path.join(repoRoot, outputDir, artifact);
    if (!(await pathExists(artifactPath))) {
      missing.push(artifact);
      continue;
    }

    if (artifact.endsWith(".json")) {
      const raw = await fs.readFile(artifactPath, "utf8");
      const parsed = JSON.parse(raw);
      if (parsed.status !== "ready") {
        missing.push(`${artifact} (status=${parsed.status ?? "unknown"})`);
      }
    }
  }

  if (missing.length > 0) {
    throw new ArchifyError(
      `Generate requires completed analysis artifacts in ${outputDir}. Missing or incomplete: ${missing.join(", ")}.`,
      { code: "GENERATE_PREREQS_MISSING", exitCode: 2 }
    );
  }
}

export async function initCommand(repoRoot, options) {
  const setup = await resolveSetupOptions(repoRoot, options);
  const installRoot = setup.projectRoot;
  const { configPath, created: createdConfig, config } = await ensureConfig(installRoot, setup);
  const { ignorePath, created: createdIgnore } = await ensureIgnoreFile(installRoot);
  const skillTargets = await installSkillTemplates(installRoot, setup);

  return {
    command: "init",
    installMode: setup.installMode,
    platforms: setup.platforms,
    installRoot,
    configPath,
    ignorePath,
    skillTargets,
    outputDir: config.defaults.outputDir,
    createdConfig,
    createdIgnore
  };
}

export async function analyzeCommand(appRoot, repoRoot, targetArg) {
  const { data: config } = await loadConfig(repoRoot);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  await ensureOutputDir(repoRoot, config.defaults.outputDir || OUTPUT_DIR);

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "analyze",
    targetPath,
    config
  });

  return {
    command: "analyze",
    targetPath,
    outputDir: config.defaults.outputDir || OUTPUT_DIR,
    reservedArtifacts: RESERVED_ARTIFACTS,
    operationalArtifacts: OPERATIONAL_ARTIFACTS,
    result
  };
}

export async function generateCommand(appRoot, repoRoot, targetArg) {
  const { data: config } = await loadConfig(repoRoot);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  await validateGenerateArtifacts(repoRoot, config.defaults.outputDir || OUTPUT_DIR);

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "generate",
    targetPath,
    config
  });

  return {
    command: "generate",
    targetPath,
    outputDir: config.defaults.outputDir || OUTPUT_DIR,
    result
  };
}

export async function cleanCommand(repoRoot) {
  const { data: config } = await loadConfig(repoRoot);
  const outputDir = path.join(repoRoot, config.defaults.outputDir || OUTPUT_DIR);
  const exists = await pathExists(outputDir);

  if (exists) {
    await removeContents(outputDir);
  }

  return {
    command: "clean",
    outputDir,
    removed: exists
  };
}

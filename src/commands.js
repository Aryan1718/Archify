import fs from "node:fs/promises";
import path from "node:path";

import {
  ALL_ANALYSIS_ARTIFACTS,
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

export async function statusCommand(repoRoot) {
  const configPath = path.join(repoRoot, "archify.config.json");
  const configExists = await pathExists(configPath);

  if (!configExists) {
    return {
      command: "status",
      installed: false,
      repoRoot,
      summary: "Archify is not set up in this repository yet.",
      nextStep: "Run `npx archify init` in this repository.",
    };
  }

  const { data: config } = await loadConfig(repoRoot);
  const outputDirName = config.defaults.outputDir || OUTPUT_DIR;
  const outputDir = path.join(repoRoot, outputDirName);
  const outputDirExists = await pathExists(outputDir);
  const manifestPath = path.join(outputDir, "manifest.json");
  const manifestExists = outputDirExists ? await pathExists(manifestPath) : false;

  let manifest = null;
  let manifestStatus = "missing";
  if (manifestExists) {
    try {
      manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
      manifestStatus = manifest?.status ?? "unknown";
    } catch {
      manifestStatus = "invalid";
    }
  }

  const artifactStates = await Promise.all(
    ALL_ANALYSIS_ARTIFACTS.map(async (artifact) => ({
      name: artifact,
      present: outputDirExists ? await pathExists(path.join(outputDir, artifact)) : false
    }))
  );

  const availableArtifacts = artifactStates.filter((item) => item.present).map((item) => item.name);
  const missingArtifacts = artifactStates.filter((item) => !item.present).map((item) => item.name);
  const analysisReady = manifestStatus === "ready";
  const generatedPacketReady = availableArtifacts.includes("design-packet.json");

  return {
    command: "status",
    installed: true,
    repoRoot,
    outputDir,
    outputDirExists,
    analysisReady,
    generatedPacketReady,
    summary: analysisReady
      ? "Archify is set up and repository knowledge is available."
      : "Archify is set up, but repository knowledge has not been built yet.",
    nextStep: analysisReady
      ? "Ask your AI assistant to use Archify on this repo, or run `npx archify clean` to remove generated artifacts."
      : "Ask your AI assistant to use Archify on this repo, or run `npx archify analyze .` if you want to build the knowledge base manually.",
    config: {
      installMode: config.skillInstall.mode,
      platforms: config.skillInstall.platforms,
      outputDir: outputDirName,
    },
    manifest: manifest
      ? {
          status: manifest.status ?? "unknown",
          mode: manifest.mode ?? null,
          targetPath: manifest.targetPath ?? null,
          generatedAt: manifest.generatedAt ?? null,
        }
      : null,
    availableArtifacts,
    missingArtifacts,
  };
}

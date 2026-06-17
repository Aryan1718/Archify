import fs from "node:fs/promises";
import path from "node:path";

import {
  CONFIG_FILE,
  DEFAULT_CONFIG,
  DEFAULT_IGNORE_LINES,
  getSharedGlobalSkillDir,
  IGNORE_FILE,
  PROJECT_CLAUDE_SKILL_DIR,
  PROJECT_SKILL_DIR,
  SHARED_INSTALL_PLATFORM,
  SHARED_INSTALL_PLATFORMS,
  SKILL_TEMPLATE_VERSION
} from "./constants.js";
import { ArchifyError } from "./errors.js";
import { ensureDir, pathExists } from "./fs-utils.js";

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function resolveSkillTargetPath({ installMode, platform, projectRoot }) {
  if (installMode === "global") {
    return getSharedGlobalSkillDir();
  }

  return platform === "claude-code"
    ? path.join(projectRoot, PROJECT_CLAUDE_SKILL_DIR)
    : path.join(projectRoot, PROJECT_SKILL_DIR);
}

function resolveSkillTargets({ installMode, platforms, projectRoot }) {
  const targetPlatforms = installMode === "global"
    ? [SHARED_INSTALL_PLATFORM]
    : platforms;

  return targetPlatforms.map((platform) => ({
    platform,
    path: resolveSkillTargetPath({ installMode, platform, projectRoot }),
    projectRoot
  }));
}

function mergeDefaults(base, incoming) {
  if (Array.isArray(base)) {
    return Array.isArray(incoming) ? incoming : [...base];
  }

  if (!isObject(base)) {
    return incoming === undefined ? base : incoming;
  }

  const result = { ...base };
  const source = isObject(incoming) ? incoming : {};

  for (const [key, value] of Object.entries(base)) {
    result[key] = mergeDefaults(value, source[key]);
  }

  for (const [key, value] of Object.entries(source)) {
    if (!(key in result)) {
      result[key] = value;
    }
  }

  return result;
}

export async function loadConfig(repoRoot) {
  const configPath = path.join(repoRoot, CONFIG_FILE);
  let parsed;

  try {
    const raw = await fs.readFile(configPath, "utf8");
    parsed = JSON.parse(raw);
  } catch (error) {
    if (error.code === "ENOENT") {
      throw new ArchifyError(
        `Missing ${CONFIG_FILE}. Run "archify-cli init" in ${repoRoot} before using this command.`,
        { code: "CONFIG_MISSING", exitCode: 2 }
      );
    }

    if (error instanceof SyntaxError) {
      throw new ArchifyError(
        `Invalid ${CONFIG_FILE}: ${error.message}`,
        { code: "CONFIG_INVALID", exitCode: 2 }
      );
    }

    throw error;
  }

  return {
    path: configPath,
    data: mergeDefaults(DEFAULT_CONFIG, parsed)
  };
}

export async function ensureConfig(repoRoot, { installMode, platforms, projectRoot }) {
  const configPath = path.join(repoRoot, CONFIG_FILE);
  const existing = await pathExists(configPath);
  const config = existing
    ? (await loadConfig(repoRoot)).data
    : structuredClone(DEFAULT_CONFIG);
  const targets = resolveSkillTargets({ installMode, platforms, projectRoot });
  const storedPlatform = installMode === "global"
    ? SHARED_INSTALL_PLATFORM
    : (platforms[0] ?? null);
  const storedPlatforms = installMode === "global"
    ? [...SHARED_INSTALL_PLATFORMS]
    : platforms;

  config.skillInstall.mode = installMode;
  config.skillInstall.platform = storedPlatform;
  config.skillInstall.platforms = storedPlatforms;
  config.skillInstall.installedAt = new Date().toISOString();
  config.skillInstall.version = SKILL_TEMPLATE_VERSION;
  config.skillInstall.target = targets[0] ?? null;
  config.skillInstall.targets = targets;

  await fs.writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");

  return { configPath, created: !existing, config };
}

export async function ensureIgnoreFile(repoRoot) {
  const ignorePath = path.join(repoRoot, IGNORE_FILE);
  const exists = await pathExists(ignorePath);

  if (!exists) {
    await fs.writeFile(ignorePath, `${DEFAULT_IGNORE_LINES.join("\n")}\n`, "utf8");
  }

  return { ignorePath, created: !exists };
}

export async function ensureOutputDir(repoRoot, outputDir) {
  const resolvedOutputDir = path.join(repoRoot, outputDir);
  await ensureDir(resolvedOutputDir);
  return resolvedOutputDir;
}

import path from "node:path";

import {
  INSTALL_MODES,
  INSTALL_PLATFORM_ALIASES,
  INSTALL_PLATFORMS,
  SHARED_INSTALL_PLATFORMS
} from "./constants.js";
import { ArchifyError } from "./errors.js";
import { isWritableDirectory, pathExists } from "./fs-utils.js";
import {
  printHeader,
  promptMultiSelect,
  promptSingleChoice,
  promptText
} from "./terminal-ui.js";

function isInteractive() {
  return Boolean(process.stdin.isTTY && process.stdout.isTTY);
}

function validateChoice(value, validValues, errorCode, label) {
  if (!validValues.includes(value)) {
    throw new ArchifyError(
      `Invalid ${label} "${value}". Expected ${validValues.map((item) => `"${item}"`).join(" or ")}.`,
      { code: errorCode, exitCode: 2 }
    );
  }

  return value;
}

async function validateProjectPath(projectPath) {
  const exists = await pathExists(projectPath);
  if (!exists) {
    throw new ArchifyError(`Project path does not exist: ${projectPath}`, {
      code: "PROJECT_PATH_MISSING",
      exitCode: 2
    });
  }

  const writable = await isWritableDirectory(projectPath);
  if (!writable) {
    throw new ArchifyError(`Project path must be a writable directory: ${projectPath}`, {
      code: "PROJECT_PATH_INVALID",
      exitCode: 2
    });
  }

  return projectPath;
}

async function resolveInstallModeInteractive() {
  const answer = await promptSingleChoice("Where do you want to install Archify?", [
    {
      label: "This project",
      value: "project",
      hint: "Creates config and skills inside the current repository."
    },
    {
      label: "Global",
      value: "global",
      hint: "Installs the shared skill once for this machine."
    }
  ]);
  return validateChoice(answer, INSTALL_MODES, "INSTALL_MODE_INVALID", "install mode");
}

async function resolveProjectPathInteractive(repoRoot) {
  const customPath = await promptText(
    'Project path to install into',
    { defaultValue: "." }
  );
  if (!customPath) {
    throw new ArchifyError("Project path is required for project installs.", {
      code: "PROJECT_PATH_REQUIRED",
      exitCode: 2
    });
  }

  return validateProjectPath(path.resolve(repoRoot, customPath));
}

async function resolvePlatformInteractive() {
  const selected = await promptMultiSelect(
    "Which platforms should Archify install for?",
    [
      {
        label: "Codex",
        value: "codex",
        hint: "Install the skill into .agents/skills/archify"
      },
      {
        label: "Claude Code",
        value: "claude-code",
        hint: "Install the skill into .claude/skills/archify"
      }
    ],
    { initialSelected: ["codex", "claude-code"] }
  );

  if (selected.length === 0) {
    throw new ArchifyError("At least one platform is required.", {
      code: "PLATFORM_REQUIRED",
      exitCode: 2
    });
  }

  return selected;
}

function normalizePlatforms(platforms) {
  return [...new Set(platforms)];
}

function parsePlatforms(rawValue) {
  const normalized = rawValue.trim().toLowerCase();
  const aliased = INSTALL_PLATFORM_ALIASES[normalized];
  if (aliased) {
    return normalizePlatforms(aliased);
  }

  const values = normalizePlatforms(
    normalized
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  );

  if (values.length === 0) {
    throw new ArchifyError("At least one platform is required.", {
      code: "PLATFORM_REQUIRED",
      exitCode: 2
    });
  }

  for (const value of values) {
    validateChoice(value, INSTALL_PLATFORMS, "PLATFORM_INVALID", "platform");
  }

  return values;
}

function resolveNonInteractiveInstallMode(explicitMode) {
  if (!explicitMode) {
    throw new ArchifyError(
      'Install mode is required in non-interactive environments. Re-run with "--install-mode project" or "--install-mode global".',
      { code: "INSTALL_MODE_REQUIRED", exitCode: 2 }
    );
  }

  return validateChoice(explicitMode, INSTALL_MODES, "INSTALL_MODE_INVALID", "install mode");
}

function resolveNonInteractivePlatform(explicitPlatform) {
  if (!explicitPlatform) {
    throw new ArchifyError(
      'Platform is required in non-interactive environments. Re-run with "--platform codex", "--platform claude-code", or "--platform both".',
      { code: "PLATFORM_REQUIRED", exitCode: 2 }
    );
  }

  return parsePlatforms(explicitPlatform);
}

export async function resolveSetupOptions(repoRoot, options) {
  const explicitMode = options.installMode?.trim().toLowerCase();
  const explicitPlatform = options.platform?.trim().toLowerCase();
  const explicitProjectPath = options.projectPath?.trim();
  const interactive = isInteractive();

  if (!interactive) {
    const installMode = resolveNonInteractiveInstallMode(explicitMode);

    if (installMode === "global" && explicitPlatform) {
      throw new ArchifyError('The "--platform" flag can only be used with "--install-mode project".', {
        code: "PLATFORM_UNEXPECTED",
        exitCode: 2
      });
    }

    if (installMode === "global" && explicitProjectPath) {
      throw new ArchifyError('The "--project-path" flag can only be used with "--install-mode project".', {
        code: "PROJECT_PATH_UNEXPECTED",
        exitCode: 2
      });
    }

    if (installMode === "global") {
      return { installMode, platforms: [...SHARED_INSTALL_PLATFORMS], projectRoot: repoRoot };
    }

    if (!explicitProjectPath) {
      throw new ArchifyError(
        'Project path is required in non-interactive environments for project installs. Re-run with "--project-path <path>".',
        { code: "PROJECT_PATH_REQUIRED", exitCode: 2 }
      );
    }

    const platforms = resolveNonInteractivePlatform(explicitPlatform);
    const projectRoot = await validateProjectPath(path.resolve(repoRoot, explicitProjectPath));
    return { installMode, platforms, projectRoot };
  }

  printHeader();

  const installMode = explicitMode
    ? validateChoice(explicitMode, INSTALL_MODES, "INSTALL_MODE_INVALID", "install mode")
    : await resolveInstallModeInteractive();

  if (installMode === "global" && explicitPlatform) {
    throw new ArchifyError('The "--platform" flag can only be used with "--install-mode project".', {
      code: "PLATFORM_UNEXPECTED",
      exitCode: 2
    });
  }

  const projectRoot = installMode === "project"
    ? (
      explicitProjectPath
        ? await validateProjectPath(path.resolve(repoRoot, explicitProjectPath))
        : await resolveProjectPathInteractive(repoRoot)
    )
    : repoRoot;

  if (installMode === "global" && explicitProjectPath) {
    throw new ArchifyError('The "--project-path" flag can only be used with "--install-mode project".', {
      code: "PROJECT_PATH_UNEXPECTED",
      exitCode: 2
    });
  }

  const platforms = installMode === "global"
    ? [...SHARED_INSTALL_PLATFORMS]
    : (
      explicitPlatform
        ? parsePlatforms(explicitPlatform)
        : await resolvePlatformInteractive()
    );

  return { installMode, platforms, projectRoot };
}

import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

export async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

export async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

export async function statPath(targetPath) {
  return fs.stat(targetPath);
}

export async function isWritableDirectory(targetPath) {
  try {
    const stats = await fs.stat(targetPath);
    if (!stats.isDirectory()) {
      return false;
    }

    await fs.access(targetPath, fsSync.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

export async function removeContents(dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  await Promise.all(
    entries.map(async (entry) => {
      const entryPath = path.join(dirPath, entry.name);
      await fs.rm(entryPath, { recursive: true, force: true });
    })
  );
}

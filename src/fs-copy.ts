import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";

/**
 * Lists files under dir (relative to dir), recursing into subdirectories.
 * Skips __pycache__ directories and *.pyc files: these are local Python
 * bytecode caches left behind by running the skill's scripts, not part of
 * the shipped template source, and are never useful in an install target.
 */
export function listTemplateFiles(dir: string, base: string = dir): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...listTemplateFiles(full, base));
    } else {
      if (entry.name.endsWith(".pyc")) continue;
      out.push(relative(base, full));
    }
  }
  return out;
}

/**
 * Recursively copies srcDir into destDir, overwriting existing files
 * (idempotent installs), applying the same __pycache__/.pyc filter as
 * listTemplateFiles. Returns the list of relative paths written.
 */
export function copyTree(srcDir: string, destDir: string): string[] {
  const files = listTemplateFiles(srcDir);
  for (const rel of files) {
    const srcFile = join(srcDir, rel);
    const destFile = join(destDir, rel);
    mkdirSync(dirname(destFile), { recursive: true });
    copyFileSync(srcFile, destFile);
  }
  return files;
}

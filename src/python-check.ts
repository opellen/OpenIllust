import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

// On Windows, version managers (pyenv-win, nvm, etc.) commonly put a
// `python.bat`/`.cmd` shim on PATH. Node's spawnSync resolves bare command
// names via the OS loader, which does not apply PATHEXT the way cmd.exe
// does, so a shimmed "python" comes back ENOENT unless we go through a
// shell. This mirrors a documented pyenv-win .bat quirk (see CLAUDE.md).
const useShell = process.platform === "win32";

export interface PythonVersionResult {
  found: boolean;
  version?: string;
  major?: number;
  minor?: number;
  ok: boolean; // true when found and >= 3.10
  raw?: string;
}

const MIN_MAJOR = 3;
const MIN_MINOR = 10;

/**
 * Runs `python --version` and reports whether it meets the >=3.10
 * prerequisite. A missing interpreter or an unparsable version is reported
 * (found: false / ok: false) but is never thrown — this check is a warning,
 * never an install failure.
 */
export function checkPythonVersion(): PythonVersionResult {
  const res = spawnSync("python", ["--version"], { encoding: "utf8", shell: useShell });
  if (res.error || res.status !== 0) {
    return { found: false, ok: false };
  }
  const raw = `${res.stdout ?? ""}${res.stderr ?? ""}`.trim(); // old Python 2/3.x printed to stderr
  const m = raw.match(/Python (\d+)\.(\d+)/);
  if (!m) {
    return { found: true, ok: false, raw };
  }
  const major = Number(m[1]);
  const minor = Number(m[2]);
  const ok = major > MIN_MAJOR || (major === MIN_MAJOR && minor >= MIN_MINOR);
  return { found: true, ok, major, minor, version: `${major}.${minor}`, raw };
}

export interface PipInstallResult {
  attempted: boolean;
  success: boolean;
  message: string;
}

/**
 * Runs `python -m pip install -r <requirementsPath>` against the installed
 * skill's requirements.txt. Failures (missing file, non-zero exit, spawn
 * error) are surfaced as a warning result, never thrown.
 */
export function installRequirements(requirementsPath: string): PipInstallResult {
  if (!existsSync(requirementsPath)) {
    return { attempted: false, success: false, message: `requirements.txt not found at ${requirementsPath}` };
  }
  const res = spawnSync("python", ["-m", "pip", "install", "-r", requirementsPath], {
    encoding: "utf8",
    shell: useShell,
  });
  if (res.error) {
    return { attempted: true, success: false, message: `pip install failed to start: ${res.error.message}` };
  }
  const success = res.status === 0;
  const tail = `${res.stdout ?? ""}${res.stderr ?? ""}`.trim().split("\n").slice(-5).join("\n");
  return {
    attempted: true,
    success,
    message: success ? "pip install completed" : `pip install failed (exit ${res.status}):\n${tail}`,
  };
}

import * as cp from "child_process";
import * as path from "path";
import * as vscode from "vscode";

function platformDir(): string {
  return `${process.platform}-${process.arch}`;
}

export function binaryPath(context: vscode.ExtensionContext): string {
  const exeName = process.platform === "win32" ? "smartcopy.exe" : "smartcopy";
  return path.join(context.extensionPath, "bin", platformDir(), exeName);
}

export interface ProgressUpdate {
  label: string;
  completed: number;
  total: number;
}

export interface RunResult<T> {
  data: T;
}

/**
 * Runs the bundled smartcopy binary with --json and resolves with its
 * terminal result. The process's exit code is deliberately not consulted -
 * the CLI exits non-zero for perfectly normal, structured outcomes too
 * (verify found mismatches, copy skipped a locked file).
 */
export function runCommand<T = unknown>(
  context: vscode.ExtensionContext,
  args: string[],
  onProgress?: (update: ProgressUpdate) => void
): Promise<RunResult<T>> {
  const exe = binaryPath(context);
  const child = cp.spawn(exe, [...args, "--json"], { cwd: context.extensionPath });

  let buffer = "";
  let stderr = "";
  let settled = false;

  return new Promise<RunResult<T>>((resolve, reject) => {
    const handleLine = (line: string): void => {
      const trimmed = line.trim();
      if (!trimmed) {
        return;
      }
      let parsed: any;
      try {
        parsed = JSON.parse(trimmed);
      } catch {
        return; // ignore any stray non-JSON noise defensively
      }
      if (parsed.event === "progress") {
        onProgress?.({ label: parsed.label, completed: parsed.completed, total: parsed.total });
      } else if (parsed.event === "result") {
        settled = true;
        resolve({ data: parsed.data as T });
      } else if (parsed.event === "error") {
        settled = true;
        reject(new Error(parsed.message));
      }
    };

    child.stdout.on("data", (chunk: Buffer) => {
      buffer += chunk.toString("utf8");
      let idx: number;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        handleLine(line);
      }
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (err) => {
      reject(new Error(`Failed to launch smartcopy binary at ${exe}: ${err.message}`));
    });

    child.on("close", (code) => {
      if (!settled && buffer.trim()) {
        handleLine(buffer);
      }
      if (!settled) {
        reject(new Error(stderr.trim() || `smartcopy produced no valid JSON (exit ${code ?? -1})`));
      }
    });
  });
}

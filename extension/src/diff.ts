import * as path from "path";
import * as vscode from "vscode";

/**
 * Opens VS Code's own native diff editor for one mismatched file, rather
 * than rendering a diff ourselves - reuses the same polished UI as Git
 * diffs instead of building a second one.
 */
export async function openDiff(srcRoot: string, destRoot: string, relativePath: string): Promise<void> {
  // relativePath comes from the CLI as posix-style ("a/b.txt") regardless
  // of OS; path.join normalizes it for the current platform.
  const parts = relativePath.split("/");
  const srcUri = vscode.Uri.file(path.join(srcRoot, ...parts));
  const destUri = vscode.Uri.file(path.join(destRoot, ...parts));

  await vscode.commands.executeCommand(
    "vscode.diff",
    srcUri,
    destUri,
    `${relativePath} (source ↔ destination)`
  );
}

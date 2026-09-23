import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { ProgressUpdate, runCommand } from "./binary";
import { openDiff } from "./diff";

type IgnoreStatus = "copyignore" | "gitignore" | "none" | "unknown";

interface DashboardState {
  source: string | null;
  dest: string | null;
  ignoreFile: string | null;
  ignoreStatus: IgnoreStatus;
}

export class DashboardProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "smartcopy.dashboard";

  private view: vscode.WebviewView | undefined;
  private state: DashboardState = { source: null, dest: null, ignoreFile: null, ignoreStatus: "unknown" };

  constructor(private readonly context: vscode.ExtensionContext) {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (folder) {
      this.state.source = folder.uri.fsPath;
    }
    this.refreshIgnoreStatus();
  }

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.file(path.join(this.context.extensionPath, "media"))],
    };
    webviewView.webview.html = this.renderHtml(webviewView.webview);

    webviewView.webview.onDidReceiveMessage((message) => this.handleMessage(message));

    this.postState();
  }

  public setActiveFolder(folderPath: string): void {
    this.state.source = folderPath;
    this.refreshIgnoreStatus();
    this.postState();
  }

  public refresh(): void {
    this.refreshIgnoreStatus();
    this.postState();
  }

  private refreshIgnoreStatus(): void {
    if (this.state.ignoreFile) {
      // Status display is governed by the explicit override in this case;
      // the webview shows the chosen filename directly instead of a badge.
      return;
    }
    if (!this.state.source) {
      this.state.ignoreStatus = "unknown";
      return;
    }
    if (fs.existsSync(path.join(this.state.source, ".copyignore"))) {
      this.state.ignoreStatus = "copyignore";
    } else if (fs.existsSync(path.join(this.state.source, ".gitignore"))) {
      this.state.ignoreStatus = "gitignore";
    } else {
      this.state.ignoreStatus = "none";
    }
  }

  private postState(): void {
    this.view?.webview.postMessage({ type: "state", ...this.state });
  }

  private async handleMessage(message: any): Promise<void> {
    switch (message.type) {
      case "ready":
        this.postState();
        return;
      case "pickSource":
        await this.pickFolder("source");
        return;
      case "pickDest":
        await this.pickFolder("dest");
        return;
      case "pickIgnoreFile":
        await this.pickIgnoreFile();
        return;
      case "clearIgnoreFile":
        this.state.ignoreFile = null;
        this.refreshIgnoreStatus();
        this.postState();
        return;
      case "pickZipOutput":
        await this.pickZipOutput();
        return;
      case "run":
        await this.runAction(message.action, message.options ?? {});
        return;
      case "openDiff":
        if (this.state.source && this.state.dest) {
          await openDiff(this.state.source, this.state.dest, message.relativePath);
        }
        return;
      case "revealInOS":
        await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(message.targetPath));
        return;
      case "copyToClipboard":
        await vscode.env.clipboard.writeText(message.text);
        this.view?.webview.postMessage({ type: "toast", message: "Copied to clipboard" });
        return;
    }
  }

  private async pickFolder(which: "source" | "dest"): Promise<void> {
    const picked = await vscode.window.showOpenDialog({
      canSelectFolders: true,
      canSelectFiles: false,
      canSelectMany: false,
      openLabel: which === "source" ? "Use as Source" : "Use as Destination",
    });
    if (!picked || picked.length === 0) {
      return;
    }
    this.state[which] = picked[0].fsPath;
    if (which === "source") {
      this.refreshIgnoreStatus();
    }
    this.postState();
  }

  private async pickIgnoreFile(): Promise<void> {
    const picked = await vscode.window.showOpenDialog({
      canSelectFolders: false,
      canSelectFiles: true,
      canSelectMany: false,
      openLabel: "Use as Ignore File",
      title: "Select a .copyignore, .gitignore, or any other ignore file",
    });
    if (!picked || picked.length === 0) {
      return;
    }
    this.state.ignoreFile = picked[0].fsPath;
    this.postState();
  }

  private async pickZipOutput(): Promise<void> {
    const picked = await vscode.window.showSaveDialog({
      filters: { "Zip files": ["zip"] },
      saveLabel: "Use as Zip Output",
    });
    if (!picked) {
      return;
    }
    this.view?.webview.postMessage({ type: "zipOutput", path: picked.fsPath });
  }

  private requireSource(action: string): string | null {
    if (!this.state.source) {
      this.view?.webview.postMessage({ type: "error", action, message: "Choose a source folder first." });
      return null;
    }
    return this.state.source;
  }

  private requireDest(action: string): string | null {
    if (!this.state.dest) {
      this.view?.webview.postMessage({ type: "error", action, message: "Choose a destination folder first." });
      return null;
    }
    return this.state.dest;
  }

  private withIgnoreFile(args: string[]): string[] {
    if (this.state.ignoreFile) {
      args.push("--ignore-file", this.state.ignoreFile);
    }
    return args;
  }

  private onProgressFor(action: string): (update: ProgressUpdate) => void {
    return (update) => this.view?.webview.postMessage({ type: "progress", action, ...update });
  }

  private async runAction(action: string, options: Record<string, unknown>): Promise<void> {
    const source = this.requireSource(action);
    if (!source) {
      return;
    }

    this.view?.webview.postMessage({ type: "running", action });

    try {
      switch (action) {
        case "preview": {
          const args = this.withIgnoreFile(["preview", source]);
          if (this.state.dest) {
            args.push("--compare-dest", this.state.dest);
          }
          const data = await runCommand(this.context, args);
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "stats": {
          const data = await runCommand(this.context, ["stats", source]);
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "init": {
          const args = ["init", source];
          if (options.preset) {
            args.push("--preset", String(options.preset));
          }
          if (options.force) {
            args.push("--force");
          }
          const data = await runCommand(this.context, args);
          this.postState();
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "command": {
          const dest = this.requireDest(action);
          if (!dest) {
            return;
          }
          const args = this.withIgnoreFile(["command", source, dest]);
          const data = await runCommand(this.context, args);
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "verify": {
          const dest = this.requireDest(action);
          if (!dest) {
            return;
          }
          const args = this.withIgnoreFile(["verify", source, dest]);
          const data = await runCommand(this.context, args, this.onProgressFor(action));
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "zip": {
          const args = this.withIgnoreFile(["zip", source]);
          if (options.output) {
            args.push("--output", String(options.output));
          }
          const data = await runCommand(this.context, args, this.onProgressFor(action));
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "copy": {
          const dest = this.requireDest(action);
          if (!dest) {
            return;
          }
          const args = this.withIgnoreFile(["copy", source, dest, "--yes"]);
          if (options.incremental) {
            args.push("--incremental");
          }
          if (options.prune) {
            args.push("--prune", "--yes-prune");
          }
          const data = await runCommand(this.context, args, this.onProgressFor(action));
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        default:
          this.view?.webview.postMessage({ type: "error", action, message: `Unknown action: ${action}` });
      }
    } catch (err) {
      this.view?.webview.postMessage({
        type: "error",
        action,
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  private renderHtml(webview: vscode.Webview): string {
    const mediaUri = (file: string) =>
      webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, "media", file)));

    const nonce = Array.from({ length: 16 }, () => Math.floor(Math.random() * 16).toString(16)).join("");

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';" />
  <link rel="stylesheet" href="${mediaUri("dashboard.css")}" />
  <title>SmartCopy</title>
</head>
<body>
  <div class="hero" aria-hidden="true">
    <svg class="hero-icon" viewBox="0 0 24 24" width="16" height="16">
      <path fill="currentColor" d="M2 5a2 2 0 0 1 2-2h4.5l1.5 1.5H20a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5z" />
    </svg>
    <div class="hero-track">
      <div class="hero-branch"></div>
      <span class="hero-arrow">
        <svg viewBox="0 0 16 16" width="11" height="11" xmlns="http://www.w3.org/2000/svg" fill="none">
  <path fill-rule="evenodd" clip-rule="evenodd" stroke="#888888" stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round" d="M13.71 4.29l-3-3L10 1H4L3 2v12l1 1h9l1-1V5l-.29-.71zM13 14H4V2h5v4h4v8zm-3-9V2l3 3h-3z"/>
</svg>
      </span>
      <span class="hero-reject">
        <svg viewBox="0 0 16 16" width="11" height="11" xmlns="http://www.w3.org/2000/svg" fill="none">
  <path fill-rule="evenodd" clip-rule="evenodd" stroke="#f14c4c" stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round" d="M13.71 4.29l-3-3L10 1H4L3 2v12l1 1h9l1-1V5l-.29-.71zM13 14H4V2h5v4h4v8zm-3-9V2l3 3h-3z"/>
</svg>
      </span>
    </div>
    <svg class="hero-icon" viewBox="0 0 24 24" width="16" height="16">
      <path fill="currentColor" d="M2 5a2 2 0 0 1 2-2h4.5l1.5 1.5H20a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5z" />
    </svg>
  </div>
  <div id="root"></div>
  <script nonce="${nonce}" src="${mediaUri("dashboard.js")}"></script>
</body>
</html>`;
  }
}

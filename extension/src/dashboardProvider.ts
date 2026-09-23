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
          const data = await runCommand(this.context, ["preview", source]);
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
          const data = await runCommand(this.context, ["command", source, dest]);
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "verify": {
          const dest = this.requireDest(action);
          if (!dest) {
            return;
          }
          const data = await runCommand(this.context, ["verify", source, dest], this.onProgressFor(action));
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "zip": {
          const data = await runCommand(this.context, ["zip", source], this.onProgressFor(action));
          this.view?.webview.postMessage({ type: "result", action, data: data.data });
          return;
        }
        case "copy": {
          const dest = this.requireDest(action);
          if (!dest) {
            return;
          }
          const data = await runCommand(
            this.context,
            ["copy", source, dest, "--yes"],
            this.onProgressFor(action)
          );
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
  <div id="root"></div>
  <script nonce="${nonce}" src="${mediaUri("dashboard.js")}"></script>
</body>
</html>`;
  }
}

import * as vscode from "vscode";
import { DashboardProvider } from "./dashboardProvider";

export function activate(context: vscode.ExtensionContext): void {
  const provider = new DashboardProvider(context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(DashboardProvider.viewType, provider, {
      // Without this, VS Code deallocates the webview's script/DOM state
      // whenever the view isn't visible (switching to another sidebar tab)
      // and recreates it fresh when you come back - losing the progress
      // bar, active-button highlight, and even an already-finished result.
      webviewOptions: { retainContextWhenHidden: true },
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("smartcopy.openDashboardFor", async (uri?: vscode.Uri) => {
      const folder = uri ?? vscode.workspace.workspaceFolders?.[0]?.uri;
      await vscode.commands.executeCommand("workbench.view.extension.smartcopy");
      if (folder) {
        provider.setActiveFolder(folder.fsPath);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("smartcopy.refresh", () => {
      provider.refresh();
    })
  );
}

export function deactivate(): void {}

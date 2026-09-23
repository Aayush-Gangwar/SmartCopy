import * as vscode from "vscode";
import { DashboardProvider } from "./dashboardProvider";

export function activate(context: vscode.ExtensionContext): void {
  const provider = new DashboardProvider(context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(DashboardProvider.viewType, provider)
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("smartcopy.refresh", () => {
      provider.refresh();
    })
  );
}

export function deactivate(): void {}

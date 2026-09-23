import * as assert from "assert";
import * as vscode from "vscode";

suite("SmartCopy Extension", () => {
  test("activates and registers its commands for real", async () => {
    const ext = vscode.extensions.getExtension("smartcopy.smartcopy-vscode");
    assert.ok(ext, "extension should be discoverable by id");
    await ext!.activate();

    const commands = await vscode.commands.getCommands(true);
    assert.ok(commands.includes("smartcopy.openDashboardFor"));
    assert.ok(commands.includes("smartcopy.refresh"));

    // Executes for real (not just checking the manifest), proving
    // registerCommand actually ran during activation.
    await vscode.commands.executeCommand("smartcopy.refresh");
  });
});

import * as cp from "child_process";
import * as path from "path";
import { downloadAndUnzipVSCode, runTests } from "@vscode/test-electron";

async function main(): Promise<void> {
  try {
    const extensionDevelopmentPath = path.resolve(__dirname, "../../");
    const extensionTestsPath = path.resolve(__dirname, "./suite/index");

    const vscodeExecutablePath = await downloadAndUnzipVSCode();

    if (process.platform === "darwin") {
      // GitHub's macOS runners can leave the downloaded .app's quarantine
      // attribute in a state that makes Gatekeeper silently block the
      // bundled Electron binary - spawn() then reports a bare ENOENT
      // instead of a permissions error, which is otherwise indistinguishable
      // from a genuinely missing file. Stripping extended attributes right
      // after download is the standard workaround for this.
      const appBundle = vscodeExecutablePath.split(".app")[0] + ".app";
      cp.execFileSync("xattr", ["-cr", appBundle]);
    }

    await runTests({ vscodeExecutablePath, extensionDevelopmentPath, extensionTestsPath });
  } catch (err) {
    console.error("Failed to run extension tests");
    console.error(err);
    process.exit(1);
  }
}

main();

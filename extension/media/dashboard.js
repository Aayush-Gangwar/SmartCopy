(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById("root");

  let state = { source: null, dest: null, ignoreFile: null, ignoreStatus: "unknown" };
  let running = null;
  let lastResultNode = null;

  function h(tag, attrs, children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined) continue;
        if (k === "class") el.className = v;
        else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v);
      }
    }
    (children || []).forEach((c) => {
      if (c === null || c === undefined) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function humanSize(bytes) {
    if (bytes === undefined || bytes === null) return "-";
    const units = ["B", "KB", "MB", "GB"];
    let n = bytes;
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function run(action, options) {
    vscode.postMessage({ type: "run", action, options: options || {} });
  }

  function actionButton(label, action, onClick) {
    return h("button", { onclick: onClick }, [label]);
  }

  function folderRow(label, key, pickMsg) {
    const value = state[key] || "(not set)";
    return h("div", { class: "row" }, [
      h("span", { class: "row-label" }, [label]),
      h("span", { class: "row-value" }, [value]),
      h("button", { onclick: () => vscode.postMessage({ type: pickMsg }) }, ["Change..."]),
    ]);
  }

  function renderFileList(title, items) {
    if (!items || items.length === 0) return null;
    return h("div", { class: "file-list" }, [
      h("div", { class: "file-list-title" }, [`${title} (${items.length})`]),
      h("ul", {}, items.map((f) => h("li", {}, [f]))),
    ]);
  }

  function renderPreview(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [
        `${data.included_count} files (${humanSize(data.included_size)}) will be copied - ` +
          `${data.skipped_dirs.length + data.skipped_files.length} skipped (${humanSize(data.skipped_size)} saved)`,
      ]),
      h("div", { class: "columns" }, [
        h("div", { class: "col" }, [
          h("h4", {}, ["Will Copy"]),
          h("ul", {}, (data.top_copy || []).map((f) => h("li", {}, [f]))),
        ]),
        h("div", { class: "col" }, [
          h("h4", {}, ["Will Skip"]),
          h("ul", {}, (data.top_skip || []).map((f) => h("li", {}, [f]))),
        ]),
      ]),
    ]);
  }

  function renderStats(data) {
    return h("div", { class: "result" }, [
      h("div", {}, [`Detected: ${data.preset_names.join(", ")}`]),
      h("div", { class: "summary" }, [`${humanSize(data.skipped_size)} of bloat found`]),
      renderFileList("Bloat found", [...data.skipped_dirs, ...data.skipped_files]),
    ]);
  }

  function renderCopy(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [
        `Copied ${data.files_copied} files (${humanSize(data.bytes_copied)}), ${data.dirs_skipped} dirs skipped`,
      ]),
    ]);
  }

  function renderVerify(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [
        data.ok ? `Verified ${data.checked} files - all match.` : `${data.checked} files checked, problems found.`,
      ]),
      renderFileList("Missing", data.missing),
      renderFileList("Size mismatch", data.size_mismatch),
      renderFileList("Hash mismatch", data.hash_mismatch),
    ]);
  }

  function renderZip(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [`Wrote ${data.files_written} files to ${data.output}`]),
    ]);
  }

  function renderCommand(data) {
    return h("div", { class: "result" }, [h("pre", { class: "code" }, [data.command])]);
  }

  function renderInit(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [`Created ${data.target}`]),
      h("div", {}, [`Preset(s): ${data.presets.join(", ")}`]),
    ]);
  }

  function renderError(message) {
    return h("div", { class: "result" }, [h("div", { class: "summary danger" }, [message])]);
  }

  function renderResult(action, data) {
    switch (action) {
      case "preview":
        return renderPreview(data);
      case "stats":
        return renderStats(data);
      case "copy":
        return renderCopy(data);
      case "verify":
        return renderVerify(data);
      case "zip":
        return renderZip(data);
      case "command":
        return renderCommand(data);
      case "init":
        return renderInit(data);
      default:
        return h("pre", {}, [JSON.stringify(data, null, 2)]);
    }
  }

  function render() {
    root.innerHTML = "";

    root.appendChild(folderRow("Source", "source", "pickSource"));
    root.appendChild(folderRow("Destination", "dest", "pickDest"));

    root.appendChild(
      h("div", { class: "actions" }, [
        actionButton("Preview", "preview", () => run("preview")),
        actionButton("Stats", "stats", () => run("stats")),
        actionButton("Command", "command", () => run("command")),
        actionButton("Verify", "verify", () => run("verify")),
        actionButton("Zip", "zip", () => run("zip")),
        actionButton("Init", "init", () => run("init")),
        actionButton("Copy", "copy", () => run("copy")),
      ])
    );

    const resultsContainer = h("div", { class: "results" }, []);
    if (running) {
      resultsContainer.appendChild(h("div", { class: "summary" }, [`Running ${running}...`]));
    } else if (lastResultNode) {
      resultsContainer.appendChild(lastResultNode);
    }
    root.appendChild(resultsContainer);
  }

  window.addEventListener("message", (event) => {
    const message = event.data;
    switch (message.type) {
      case "state":
        state = {
          source: message.source,
          dest: message.dest,
          ignoreFile: message.ignoreFile,
          ignoreStatus: message.ignoreStatus,
        };
        render();
        return;
      case "running":
        running = message.action;
        render();
        return;
      case "result":
        running = null;
        lastResultNode = renderResult(message.action, message.data);
        render();
        return;
      case "error":
        running = null;
        lastResultNode = renderError(message.message);
        render();
        return;
    }
  });

  render();
  vscode.postMessage({ type: "ready" });
})();

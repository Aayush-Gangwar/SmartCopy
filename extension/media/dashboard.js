(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById("root");

  const PRESETS = ["general", "node", "python", "java", "dotnet", "rust"];

  let state = { source: null, dest: null, ignoreFile: null, ignoreStatus: "unknown" };
  let running = null;
  let runningProgress = null; // {label, completed, total}
  let lastResultNode = null;
  let lastAction = null; // drives which action button shows as "active"
  let awaitingPruneConfirm = false;
  let pendingCopyOptions = null;
  let zipOutput = null;

  // Form control values, kept outside the DOM so they survive the full
  // re-render every "running"/"progress"/"result" message triggers -
  // otherwise every rerender recreated these inputs from scratch and threw
  // away whatever the user had just picked.
  let formState = { preset: "", force: false, incremental: false, prune: false };
  // Same reasoning for whether each options section is expanded.
  let sectionState = { init: false, zip: false, copy: false };

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
    const classes = lastAction === action ? "active" : undefined;
    const busy = running !== null;
    return h("button", { class: classes, disabled: busy ? "" : undefined, onclick: busy ? null : onClick }, [
      label,
    ]);
  }

  // Anything that changes the inputs an in-flight operation is already
  // using (source/dest/ignore-file) is disabled while one is running -
  // otherwise a late-arriving result could describe inputs you've since
  // changed away from.
  function secondaryButton(label, onClick) {
    const busy = running !== null;
    return h("button", { disabled: busy ? "" : undefined, onclick: busy ? null : onClick }, [label]);
  }

  function folderRow(label, key, pickMsg) {
    const value = state[key] || "(not set)";
    return h("div", { class: "row" }, [
      h("span", { class: "row-label" }, [label]),
      h("span", { class: "row-value" }, [value]),
      secondaryButton("Change...", () => vscode.postMessage({ type: pickMsg })),
    ]);
  }

  function optionsSection(label, key, contentNodes) {
    const details = h("details", { class: "options-section" }, [h("summary", {}, [label]), ...contentNodes]);
    details.open = sectionState[key];
    details.addEventListener("toggle", () => {
      sectionState[key] = details.open;
    });
    return details;
  }

  function statusBadge() {
    const map = {
      copyignore: "Using .copyignore",
      gitignore: "Falling back to .gitignore",
      none: "No ignore file - use Init",
      unknown: "-",
    };
    return h("span", { class: "badge" }, [map[state.ignoreStatus] || map.unknown]);
  }

  function ignoreFileRow() {
    if (state.ignoreFile) {
      return h("div", { class: "row" }, [
        h("span", { class: "row-label" }, ["Ignore file"]),
        h("span", { class: "row-value" }, [state.ignoreFile]),
        secondaryButton("Clear override", () => vscode.postMessage({ type: "clearIgnoreFile" })),
      ]);
    }
    return h("div", { class: "row" }, [
      statusBadge(),
      secondaryButton("Override ignore file...", () => vscode.postMessage({ type: "pickIgnoreFile" })),
    ]);
  }

  function meter(pct) {
    return h("div", { class: "meter" }, [h("div", { class: "meter-fill", style: `width:${pct}%` }, [])]);
  }

  function loadingDots() {
    return h("span", { class: "loading-dots" }, [h("span", {}, ["."]), h("span", {}, ["."]), h("span", {}, ["."])]);
  }

  function showToast(message) {
    const toast = h("div", { class: "toast" }, [message]);
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 1800);
  }

  function renderFileList(title, items) {
    if (!items || items.length === 0) return null;
    return h("div", { class: "file-list" }, [
      h("div", { class: "file-list-title" }, [`${title} (${items.length})`]),
      h("ul", {}, items.map((f) => h("li", {}, [f]))),
    ]);
  }

  function renderPreview(data) {
    const total = (data.included_size || 0) + (data.skipped_size || 0);
    const pct = total ? Math.round((data.skipped_size / total) * 100) : 0;
    return h("div", { class: "result" }, [
      meter(pct),
      h("div", { class: "summary" }, [
        `${data.included_count} files (${humanSize(data.included_size)}) will be copied - ` +
          `${data.skipped_dirs.length + data.skipped_files.length} skipped (${humanSize(data.skipped_size)} saved, ${pct}%)`,
      ]),
      h("div", { class: "columns" }, [
        h("div", { class: "col" }, [
          h("h4", {}, ["Will Copy"]),
          h("ul", {}, (data.top_copy || []).map((f) => h("li", {}, [f]))),
        ]),
        h("div", { class: "col" }, [
          h("h4", {}, ["Will Skip"]),
          // Full recursive list (not just top-level, unlike "Will Copy") -
          // matches the CLI's own render_preview, which shows every
          // skipped path since that's the detail that actually builds
          // trust in what's being excluded.
          h(
            "ul",
            {},
            [...(data.skipped_dirs || []), ...(data.skipped_files || [])]
              .sort()
              .map((f) => h("li", {}, [f]))
              .concat(
                [...(data.skipped_symlinks || [])]
                  .sort()
                  .map((f) => h("li", {}, [`${f} (symlink, not followed)`]))
              )
          ),
        ]),
      ]),
    ]);
  }

  function renderStats(data) {
    const total = (data.included_size || 0) + (data.skipped_size || 0);
    const pct = total ? Math.round((data.skipped_size / total) * 100) : 0;
    return h("div", { class: "result" }, [
      h("div", {}, [`Detected: ${data.preset_names.join(", ")}`]),
      meter(pct),
      h("div", { class: "summary" }, [`${humanSize(data.skipped_size)} of bloat out of ${humanSize(total)} total (${pct}%)`]),
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
    const container = h("div", { class: "result" }, [
      h("div", { class: "summary" }, [
        data.ok ? `Verified ${data.checked} files - all match.` : `${data.checked} files checked, problems found.`,
      ]),
      renderFileList("Missing", data.missing),
    ]);
    const diffable = [...data.size_mismatch, ...data.hash_mismatch];
    if (diffable.length) {
      container.appendChild(
        h("div", { class: "file-list" }, [
          h("div", { class: "file-list-title" }, [`Content differs (${diffable.length})`]),
          h(
            "ul",
            {},
            diffable.map((relPath) =>
              h(
                "li",
                { class: "clickable", onclick: () => vscode.postMessage({ type: "openDiff", relativePath: relPath }) },
                [`${relPath} (click to diff)`]
              )
            )
          ),
        ])
      );
    }
    return container;
  }

  function renderZip(data) {
    return h("div", { class: "result" }, [
      h("div", { class: "summary" }, [`Wrote ${data.files_written} files to ${data.output}`]),
      h(
        "button",
        { onclick: () => vscode.postMessage({ type: "revealInOS", targetPath: data.output }) },
        ["Reveal in Explorer"]
      ),
    ]);
  }

  function renderCommand(data) {
    return h("div", { class: "result" }, [
      h("pre", { class: "code" }, [data.command]),
      h("button", { onclick: () => vscode.postMessage({ type: "copyToClipboard", text: data.command }) }, [
        "Copy to Clipboard",
      ]),
    ]);
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

  function showPruneConfirmModal(targets, onConfirm) {
    const overlay = h("div", { class: "modal-overlay" }, []);
    const box = h("div", { class: "modal" }, [
      h("h4", {}, ["Confirm removal"]),
      targets.length
        ? h("div", {}, [
            h("p", {}, [
              `${targets.length} file(s) in the destination are not in the current source and will be removed:`,
            ]),
            h(
              "ul",
              { class: "modal-list" },
              targets.slice(0, 100).map((t) => h("li", {}, [t]))
            ),
          ])
        : h("p", {}, ["Nothing to prune - destination already matches."]),
      h("div", { class: "modal-actions" }, [
        h("button", { onclick: () => overlay.remove() }, ["Cancel"]),
        h(
          "button",
          {
            onclick: () => {
              overlay.remove();
              onConfirm();
            },
          },
          ["Delete and Copy"]
        ),
      ]),
    ]);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
  }

  function render() {
    root.innerHTML = "";

    root.appendChild(folderRow("Source", "source", "pickSource"));
    root.appendChild(folderRow("Destination", "dest", "pickDest"));
    root.appendChild(ignoreFileRow());

    const incrementalCheckbox = h("input", {
      type: "checkbox",
      id: "incremental",
      onchange: (e) => {
        formState.incremental = e.target.checked;
      },
    });
    incrementalCheckbox.checked = formState.incremental;

    const pruneCheckbox = h("input", {
      type: "checkbox",
      id: "prune",
      onchange: (e) => {
        formState.prune = e.target.checked;
      },
    });
    pruneCheckbox.checked = formState.prune;

    const presetSelect = h(
      "select",
      {
        onchange: (e) => {
          formState.preset = e.target.value;
        },
      },
      [h("option", { value: "" }, ["(auto-detect)"]), ...PRESETS.map((p) => h("option", { value: p }, [p]))]
    );
    presetSelect.value = formState.preset;

    const forceCheckbox = h("input", {
      type: "checkbox",
      id: "force",
      onchange: (e) => {
        formState.force = e.target.checked;
      },
    });
    forceCheckbox.checked = formState.force;

    root.appendChild(
      h("div", { class: "actions" }, [
        actionButton("Preview", "preview", () => run("preview")),
        actionButton("Stats", "stats", () => run("stats")),
        actionButton("Command", "command", () => run("command")),
        actionButton("Verify", "verify", () => run("verify")),
      ])
    );

    root.appendChild(
      optionsSection("Init options", "init", [
        h("div", { class: "copy-row" }, [
          h("label", {}, ["Preset:", presetSelect]),
          h("label", {}, [forceCheckbox, " Force overwrite"]),
          actionButton("Init", "init", () =>
            run("init", { preset: formState.preset || undefined, force: formState.force })
          ),
        ]),
      ])
    );

    root.appendChild(
      optionsSection("Zip options", "zip", [
        h("div", { class: "copy-row" }, [
          h("span", { class: "row-value" }, [zipOutput || "(default output path)"]),
          secondaryButton("Choose Output...", () => vscode.postMessage({ type: "pickZipOutput" })),
          actionButton("Zip", "zip", () => run("zip", { output: zipOutput || undefined })),
        ]),
      ])
    );

    root.appendChild(
      optionsSection("Copy options", "copy", [
        h("div", { class: "copy-row" }, [
          h("label", {}, [incrementalCheckbox, " Incremental"]),
          h("label", {}, [pruneCheckbox, " Remove stale files (mirror)"]),
          actionButton("Copy", "copy", () => {
            const options = { incremental: formState.incremental, prune: formState.prune };
            if (options.prune && state.dest) {
              pendingCopyOptions = options;
              awaitingPruneConfirm = true;
              run("preview");
            } else {
              run("copy", options);
            }
          }),
        ]),
      ])
    );

    const resultsContainer = h("div", { class: "results" }, []);
    if (running) {
      const cancelButton = h("button", { onclick: () => vscode.postMessage({ type: "cancel" }) }, ["Cancel"]);
      if (runningProgress && runningProgress.total > 0) {
        const pct = Math.round((runningProgress.completed / runningProgress.total) * 100);
        resultsContainer.appendChild(
          h("div", { class: "result" }, [
            meter(pct),
            h("div", { class: "run-row" }, [
              h("span", { class: "summary" }, [
                `${runningProgress.label}: ${runningProgress.completed}/${runningProgress.total} (${pct}%)`,
              ]),
              cancelButton,
            ]),
          ])
        );
      } else {
        resultsContainer.appendChild(
          h("div", { class: "run-row" }, [
            h("span", { class: "summary" }, [`Running ${running}`, loadingDots()]),
            cancelButton,
          ])
        );
      }
    } else if (lastResultNode) {
      resultsContainer.appendChild(lastResultNode);
    }
    root.appendChild(resultsContainer);
  }

  window.addEventListener("message", (event) => {
    const message = event.data;
    switch (message.type) {
      case "state": {
        const prev = state;
        state = {
          source: message.source,
          dest: message.dest,
          ignoreFile: message.ignoreFile,
          ignoreStatus: message.ignoreStatus,
        };
        // A result describes a specific (source, dest, ignore file)
        // combination - if any of those actually changed, the result
        // still on screen no longer describes what's selected, so it's
        // actively misleading rather than just stale. Clear it rather
        // than leave it looking current.
        if (prev.source !== state.source || prev.dest !== state.dest || prev.ignoreFile !== state.ignoreFile) {
          lastResultNode = null;
        }
        render();
        return;
      }
      case "zipOutput":
        zipOutput = message.path;
        render();
        return;
      case "toast":
        showToast(message.message);
        return;
      case "running":
        running = message.action;
        lastAction = message.action;
        runningProgress = null;
        render();
        return;
      case "progress":
        runningProgress = { label: message.label, completed: message.completed, total: message.total };
        render();
        return;
      case "result":
        running = null;
        runningProgress = null;
        if (message.action === "preview" && awaitingPruneConfirm) {
          awaitingPruneConfirm = false;
          render();
          showPruneConfirmModal(message.data.would_prune || [], () => run("copy", pendingCopyOptions));
          return;
        }
        if (message.action === "init") {
          // "force overwrite" is a one-shot safety flag - auto-clear it
          // after a successful use instead of leaving it silently checked
          // for whatever gets clicked next.
          formState.force = false;
          formState.preset = "";
        }
        lastResultNode = renderResult(message.action, message.data);
        render();
        showToast(`${message.action} complete`);
        return;
      case "error":
        running = null;
        runningProgress = null;
        awaitingPruneConfirm = false;
        lastResultNode = renderError(message.message);
        render();
        showToast(`${message.action} failed`);
        return;
      case "cancelled":
        running = null;
        runningProgress = null;
        awaitingPruneConfirm = false;
        render();
        showToast(`${message.action} cancelled`);
        return;
    }
  });

  render();
  vscode.postMessage({ type: "ready" });
})();

# REA investigation and Preview workflow findings

Research date: 2026-10-16, Singapore time.

## Result and evidence boundary

REA 6.5.0 runs locally through its CLI. Its current skill, version 42, was read from `.agents/skills/reverse-engineer-anything/SKILL.md` in the official repository at commit `42fc6c53ae188978deb3bedfe88287b6b316ba22`. The previous `skill-src` path is obsolete.

No Preview.app bundle, Mac runtime, or remote Mac was provided. We did not inspect, decompile, execute, or measure Apple Preview. Feature findings below come from Apple's documentation, not REA target evidence. The REA portion established the available tooling and the precise host/target blockers. Ticket 1 is partially complete; runtime reconstruction remains unresolved.

## Local setup and actual commands

The shell has Node v24.19.0. Neither `npm` nor `rea` was initially on PATH. All acquisition stayed under `.scratch/rea`; no user agent configuration or global package installation changed.

Commands run from the project folder:

```powershell
git clone --depth 1 https://github.com/morluto/rea.git .scratch/rea/source
Invoke-WebRequest https://registry.npmjs.org/npm/-/npm-11.16.0.tgz -OutFile .scratch/rea/npm.tgz
New-Item -ItemType Directory -Force .scratch/rea/npm
tar -xzf .scratch/rea/npm.tgz -C .scratch/rea/npm
node .scratch/rea/npm/package/bin/npm-cli.js install --prefix .scratch/rea/runtime rea-agents@6.5.0 --no-audit --no-fund
node .scratch/rea/runtime/node_modules/rea-agents/scripts/rea.mjs --help
node .scratch/rea/runtime/node_modules/rea-agents/scripts/rea.mjs doctor --client codex --json
node .scratch/rea/runtime/node_modules/rea-agents/scripts/rea.mjs setup --client codex --dry-run --json
node .scratch/rea/runtime/node_modules/rea-agents/scripts/rea.mjs capabilities --json
```

The initial plain `npm install` failed because npm was absent from PATH. The project-local launcher installed 173 packages in 12 seconds. npm reported a pending Frida install script; it was not approved or run. Frida is unnecessary for these read-only diagnostics.

Raw results are retained in `.scratch/rea/cli-help.txt`, `doctor.json`, `setup-plan.json`, and `capabilities.json`.

Doctor observed Windows x64, a compatible Node runtime, missing REA MCP registration, missing installed global REA skill identity, and no configured Hopper, Ghidra, IDA or JADX providers. This is readiness evidence, not a PDF application analysis.

Capabilities explicitly reported native macOS UI observation and native macOS utilities unavailable because they require macOS. A shallow inventory of common Windows application locations found Foxit Software. Foxit was not substituted as a reference or analyzed because the requested reference is Preview.

A `list-browser-targets --json` attempt returned a validation error for the missing explicit CDP endpoint. Its help confirmed that an endpoint is required. No browser attachment or target enumeration happened. The failure is retained in `browser-targets.json`.

The dry-run plan proposed changing `C:/Users/xue_c/.codex/config.toml`, with backup `config.toml.rea.backup`, and installing the skill in `C:/Users/xue_c/.agents/skills/reverse-engineer-anything`. The plan was not applied. CLI use avoids this configuration change and an agent restart.

## Documented Preview workflows

These are supplementary primary-source findings. They establish user-facing behavior only.

- Apple's [annotation guide](https://support.apple.com/guide/preview/annotate-a-pdf-prvw11580/mac) describes a Markup toolbar with text boxes, sketches, signatures, and form filling. It explicitly states that Preview cannot edit existing PDF text. Our requested text-correction tool therefore extends Preview's documented capability. Apple also distinguishes editable annotations on Save/Export from flattened print output. Redactions become permanent after document closure; linked table-of-contents entries may remain.
- Apple's [forms and signature guide](https://support.apple.com/guide/preview/fill-out-and-sign-pdf-forms-prvw35725/mac) describes direct entry into existing form fields, a text-box fallback, and placing/resizing saved signatures. The proposed Windows app adapts capture to mouse drawing and imported signature images, as requested.
- Apple's [page management guide](https://support.apple.com/guide/preview/add-delete-or-move-pdf-pages-prvw11793/mac) documents thumbnail selection, Delete, dragging to reorder, insertion from another file, and transferring pages between PDFs. These support the agreed thumbnail-sidebar workflow.

## Implementation decisions derived from the user's requirements

These are our choices, not recovered Preview internals:

- Load and render only needed pages; populate thumbnails progressively for hundred-page documents.
- Keep indexing/OCR off the GUI thread. Retain text and bounding boxes locally by document fingerprint and page. Show indexed results progressively and reuse the cache for later searches.
- Ship offline English, Simplified Chinese and Traditional Chinese OCR models. Measure cold OCR and cached search separately; no Apple or Adobe performance comparison has been measured.
- Treat a scan correction as removal of image/text content in a selected region followed by replacement text. Treat a text-PDF correction similarly where safe; do not promise word-processor reflow.
- Preserve originals by default. Redaction output must remove source content, hidden OCR, annotations and relevant metadata rather than paint a black rectangle over the page. Verify extraction and rendered output after saving.
- Store page-space geometry so zoom/rotation do not corrupt drawing, text, signatures, forms or redaction placement.

## Remaining reference investigation

With an authorized Preview.app artifact, REA can inventory packaged resources where its provider supports them; deep native analysis additionally needs a configured engine. Native runtime UI inspection requires a Mac. Until those inputs exist, the available evidence supports a Preview-inspired workflow, not a claim of recovered Preview implementation or behavior parity.

Sources: [official REA repository](https://github.com/morluto/rea), [current REA skill](https://github.com/morluto/rea/blob/42fc6c53ae188978deb3bedfe88287b6b316ba22/.agents/skills/reverse-engineer-anything/SKILL.md).

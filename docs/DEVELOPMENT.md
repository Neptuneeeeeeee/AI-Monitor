# Build and development

For downloading and running the app, use the [installation guide](INSTALL.md). Release DMG/ZIP files already contain Python; developer tools are required only when building from source.

## Requirements

macOS 14 or later, Apple Command Line Tools, Swift 5.9 or later, and a working `/usr/bin/python3`. The published v1.9.4 download targets Apple Silicon. The UI is currently mainly Chinese; README translations do not add application-language settings.

```bash
bash scripts/test.sh
bash scripts/build.sh
```

Build a self-contained preview and package it:

```bash
bash scripts/build.sh --bundle-python
python3 scripts/package_release.py --preview
```

Runtime downloads are SHA-256 pinned in `Config/runtime-lock.json`. Tests use disposable account storage and fixtures. Build and packaging commands do not install the app, query your accounts or publish to GitHub.

## Preview and local installation

`bash scripts/preview.sh` opens the real views with synthetic data and disabled account services. See [interactive preview](INTERACTIVE_PREVIEW.md).

`bash scripts/install.sh` prints an installation plan. Add `--install` to install, `--replace` to replace a stopped copy of the same edition, and `--launch` to open it. Read the plan before making changes.

A standalone checkout writes to `dist/`; the dual workspace writes to `output/public/`. The output `.app` is a local shortcut to a signed candidate in the edition's cache. Distribute the real ZIP or DMG, not that shortcut.

## Project boundaries and release status

This public checkout builds without a private sibling. [Architecture](ARCHITECTURE.md) and [Git workflow](GIT_WORKFLOW.md) describe the optional independent Local project. Source commits and content hashes are recorded in `BUILD.json`.

The v1.9.4 downloadable preview is not Developer-ID-signed or Apple-notarized. The source license and full third-party review remain pending. [Release checks](RELEASE_CHECKLIST.md), [privacy](../PRIVACY.md), [security](../SECURITY.md) and [third-party notices](../THIRD_PARTY_NOTICES.md) describe the remaining constraints. Do not commit private settings, credentials, logs or signing material.

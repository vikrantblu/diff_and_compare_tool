# diff_and_compare_tool — Next-Gen Diff & Merge Studio

A high-performance, cross-platform file comparison, 3-way merge, and multi-format data synchronization desktop suite built with Python (PySide6) and modern Windows 11 Fluent design principles.

[![CI Test Suite](https://github.com/vikrantblu/diff_and_compare_tool/actions/workflows/test.yml/badge.svg)](https://github.com/vikrantblu/diff_and_compare_tool/actions/workflows/test.yml)
[![CodeQL Analysis](https://github.com/vikrantblu/diff_and_compare_tool/actions/workflows/codeql.yml/badge.svg)](https://github.com/vikrantblu/diff_and_compare_tool/actions/workflows/codeql.yml)
![Application Status](https://img.shields.io/badge/Platform-Windows%2011%20x64%20Standalone-blue)
![Python](https://img.shields.io/badge/Python-3.11+-brightgreen)
![Framework](https://img.shields.io/badge/UI-PySide6%20Qt6-blueviolet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-vikrantblu%2Fdiff__and__compare__tool-blue?logo=github)](https://github.com/vikrantblu/diff_and_compare_tool)
[![Discussions](https://img.shields.io/badge/Discussions-Join%20Chat-teal?logo=github)](https://github.com/vikrantblu/diff_and_compare_tool/discussions)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-ea4aaa?logo=github-sponsors)](https://github.com/sponsors/vikrantblu)

---

## 🌟 10 Multi-Format Comparison Studios & Automation Suite

> 🌐 **Product Website & Interactive Guide**: Open [docs/index.html](docs/index.html) (or publish `/docs` on GitHub Pages) for an interactive Fluent Light overview, commercial feature comparison, and CLI reference.

1. **⇄ 2-Way Text, Code & Word (`.docx`) Diff**:
   - **Synchronized Bottom Line Details Pane**: Stacked Left vs Right character-by-character intraline inspector for the active cursor row.
   - **Display Scope Filtering**: Switch between `All Lines`, `Diffs Only`, `Context ±3`, and `Same Only` with collapsible hidden-line markers while keeping true 1-based line numbers intact.
   - **Read-Only Pane Lock & Interactive Encoding/EOL Converter**: Lock baseline files against accidental edits or hunk transfers; click the `UTF-8 | LF` pill to convert encoding (`UTF-8`, `UTF-8 BOM`, `UTF-16 LE/BE`, `Windows-1252`) or line endings (`LF`, `CRLF`, `CR`).
   - **Word `.docx` Text & Table Extraction**: Open Microsoft Word `.docx` files directly side-by-side (auto-locked read-only) without requiring Microsoft Word.
   - **External File Watcher**: Non-blocking reload banner notifies you immediately if an external editor, formatter, or Git command modifies an open file on disk.
   - **Tree-sitter AST Semantic Diffing**: Structural diffing for Python and JavaScript/TypeScript that detects reordered functions and docstring updates without false-positive line diffs.
   - **View Virtualization for 100k+ Lines**: Windowed sliding-window rendering keeps memory footprint bounded, rendering massive files smoothly.
   - **Diff Minimap & Visual Overview Ruler**: 16px navigation gutter displaying color-coded tick marks (green additions, red deletions, blue modifications, orange conflicts, purple moves) with hover tooltips and click-to-jump navigation.
   - **Custom Unimportant Difference Rules & Presets**: Define and persist custom regex substitution rules in Noise Filters alongside timestamps, GUIDs, commit hashes, and comments, and toggle `Ignore Unimportant` in one click.
   - **Side-by-Side HTML Reports & Unified `.patch`**: Export Fluent Light interactive Side-by-Side HTML reports, `.patch` files, or copy unified diff directly to clipboard.
   - **Manual Alignment ("Align With...")**: Explicitly anchor matching lines across panes by right-clicking and selecting **Align With...** (or pressing `Ctrl+Shift+A`), then clicking the target line on the opposing editor. Press `Ctrl+F7` or click the alignments pill to clear.
   - **Find & Replace Bar**: Docked search (`Ctrl+F` / `Ctrl+H`) with Case Sensitivity (`Aa`), Regex (`.*`), and Replace / Replace All.
   - **Local-First AI PR Summary & Privacy Shield**: Automated Markdown pull request summaries (local Ollama or OpenAI-compatible endpoints) with automated credential and PII scrubbing, or 100% zero-outbound offline heuristics.

2. **⧉ 3-Way Merge Studio**:
   - 3 synchronized viewports: **Mine (Local)** | **Base (Ancestor)** | **Theirs (Remote)** + collapsible **4th Merged Output Preview** with standard diff3 conflict markers.
   - Resolution actions: `Accept Mine`, `Accept Theirs`, `Accept Base`, `Take Both`, `AI Resolve`, full resolution Undo stack, and honors CLI `--output` destination on save.

3. **📁 Folder & Archive Comparison & Interactive Sync Hub**:
   - **Flatten Folders Mode (`Flatten`)**: View all files across nested directory hierarchies in one sortable list by relative path.
   - **±2s Timestamp Tolerance & BLAKE3**: Handles FAT/SMB/DST timestamp skew alongside SHA-256, BLAKE3, and Rules-Based modes.
   - **Interactive Folder Sync Hub (`Sync Hub...`)**: Supports Mirror L->R, Bi-directional Sync, and Update Left/Right with per-row checkboxes and Windows Recycle Bin safe-delete support.
   - **HTML & CSV Folder Reports**: Export standalone folder audit reports or CSV summaries straight from the ribbon.
   - **Smart `.gitignore` & Virtual Archive VFS**: Prunes bloat dirs and browses `.zip`, `.jar`, `.tar`, `.tgz` entries transparently without extraction.

4. **🖼 Visual Media & Document Diff Studio (Images, Multi-Page PDF, SVG)**:
   - **Live (X, Y) RGBA Pixel Inspector**: Hover anywhere on the canvas to read Left vs Right RGBA pixel values and per-channel deltas.
   - **Interactive Zoom (`Fit` / `100%` / `Ctrl+Wheel`), Swap & Drag-and-Drop**.
   - **Multi-Page PDF & EXIF**: PyMuPDF (`fitz`) page rasterization, aligned extracted text diff, EXIF metadata table, Swipe Curtain, Onion-Skin, Pixel Heatmap, Flicker/Blink, and Side-by-Side views.

5. **📊 Tabular / Spreadsheet Diff (CSV, TSV, Excel, Parquet, SQLite)**:
   - Sheet & SQLite table selectors, **Float Tolerance**, **Keyed Row Alignment** with duplicate-key reporting, Diff CSV export, and synchronized grids.

6. **🌳 Structured Tree Diff (JSON, YAML, XML)** & **🛡️ 7. API Contract Audit (OpenAPI, GraphQL, Protobuf)**:
   - JSONPath & XPath query filtering, Semantic Unordered Array matching, recursive search, XML tag rename detection, and breaking vs warning vs additive contract audits.

8. **⚡ Hex & Binary Inspection Studio**:
   - **Virtualized `QTableView` + Memory-Mapped I/O (MMF)**: Inspects multi-GB binaries with byte-delta highlighting, Go-to-Offset, Find Hex/ASCII patterns, and live 8/16/32/64-bit integer Data Inspector.

9. **🌿 Git Working-Tree Changeset Browser (`Ctrl+G`) & Live Hunk Staging**:
   - Browse modified, staged, untracked, and conflicted files across any Git repo (`Ctrl+G` or Home button) and open `HEAD vs Working Copy` directly.
   - Stage, unstage, or discard individual hunks via `git apply --cached`, plus 1-click **Tools → Configure as Git Difftool & Mergetool**.

10. **⌘ Command Palette (`Ctrl+K`) & Headless CI/CD Automation**:
   - Universal keyboard launcher (`Ctrl+K` / `Ctrl+Shift+P`) across all 10 studios, active view actions, Git tools, and Recent Comparisons.
   - Headless `--folder-diff`, `--diff`, and `--contract-diff` with HTML/JSON reporting and exit codes (`0 = match`, `1 = mismatch/breaking`, `2 = error`), plus CLI Stdin Diffing (`--diff - <file>`), Write-Ahead Log (WAL) crash recovery, and Windows 11 Mica Alt Fluent Light shell integration.

---

## 🚀 Quickstart & Installation

### 1. Windows Installation (Double-Click Setup EXE)
- **Double-Click Standalone Installer**:
  Run [`dist/Setup_diff_and_compare_tool.exe`](file:///D:/myrepo/diff_and_compare_tool/dist/Setup_diff_and_compare_tool.exe)
  - Full native Windows installation wizard with ultra-compressed single executable payload.
  - Automatically registers Windows Explorer right-click context menu, App Paths (`Win+R`), User `PATH`, Start Menu & Desktop shortcuts, and Windows "Installed Apps" uninstaller.
  - Installs to `%LOCALAPPDATA%\Programs\diff_and_compare_tool` (requires **no Administrator privileges**).
- **1-Click Batch Installer**:
  Double-click `Install.cmd` inside `dist/diff_and_compare_installer/` or `windows/`.
- **PowerShell Script**:
  ```powershell
  .\windows\Install-DiffAndCompare.ps1
  ```

**What gets installed & registered:**
- Deploys application to `%LOCALAPPDATA%\Programs\diff_and_compare_tool`.
- **Windows Explorer Context Menu**: Right-click any file, folder, or directory background (`Compare with diff_and_compare_tool`, `Select Left`, `Select Right`).
- **Windows App Paths**: Launch from `Win+R` or CLI simply by typing `diff_and_compare`.
- **Windows Installed Apps**: Full entry in Windows Settings / Control Panel "Installed Apps" with icon, version, publisher, and native uninstaller (`unins000.exe`).
- **Shortcuts**: Start Menu and Desktop shortcuts.
- **User PATH**: Adds directory to user environment `PATH`.

To uninstall anytime: run `unins000.exe`, or double-click `Uninstall.cmd`, or remove via Windows Settings -> Installed Apps.

### 2. Standalone CLI & Registry Management
```powershell
# Register all Windows features (Context Menu, App Paths, Installed Apps entry)
python app/main.py --install-all
python app/main.py --uninstall-all

# Shell Context Menu only
python app/main.py --install-shell
python app/main.py --uninstall-shell

# Export customized .reg file for current install
python app/main.py --export-reg Register-MySetup.reg
```

### 3. Git Difftool & Mergetool Integration
```bash
# Configure as git difftool (using standalone binary or PATH)
git config --global diff.tool diff_and_compare
git config --global difftool.diff_and_compare.cmd "diff_and_compare.exe --diff \"\$LOCAL\" \"\$REMOTE\""

# Or configure using Python source:
# git config --global difftool.diff_and_compare.cmd "\"python\" \"/path/to/diff_and_compare_tool/app/main.py\" --diff \"\$LOCAL\" \"\$REMOTE\""

# Configure as git mergetool (using standalone binary or PATH)
git config --global merge.tool diff_and_compare
git config --global mergetool.diff_and_compare.cmd "diff_and_compare.exe --merge \"\$LOCAL\" \"\$BASE\" \"\$REMOTE\" --output \"\$MERGED\""

# Or configure using Python source:
# git config --global mergetool.diff_and_compare.cmd "\"python\" \"/path/to/diff_and_compare_tool/app/main.py\" --merge \"\$LOCAL\" \"\$BASE\" \"\$REMOTE\" --output \"\$MERGED\""
```

### 4. Headless CI/CD Batch Automation
```powershell
# Folder comparison with HTML report and automated exit code (0 = match, 1 = diff)
python app/main.py --folder-diff src_v1/ src_v2/ --report-html folder_audit.html --exit-code

# File comparison with HTML report
python app/main.py --diff config_prod.json config_staging.json --report-html config_diff.html --exit-code
```

### 5. Build Standalone Executables & Installer Packages
```powershell
# Build binaries for host architecture
python build.py

# Build binaries AND package into turnkey installer folder & release ZIP
python build.py --package

# Build specifically for Windows ARM64
python build.py --target-arch arm64
```

---

## 🔮 Strategic Next-Phase Roadmap

- **Remote Virtual Filesystem Adapters**: Streaming comparison across SSH/SFTP and S3-compatible buckets.
- **Native Code Signing & Winget Distribution**: Signed Windows installer releases distributed via `winget`.
- **Audio & Geospatial Studio Plugins**: Optional waveform spectral diffing and GeoJSON/Shapefile layer comparison.

---

## 📚 Technical Documentation

- **[Product Website & Feature Explorer](docs/index.html)**: Interactive Fluent Light landing page, commercial comparison matrix, and CLI reference.

- **[Functionality & User Guide](docs/FUNCTIONALITY_GUIDE.md)**: Exhaustive manual detailing all features, workflows, and keyboard shortcuts.
- **[System Architecture & Design Specification](docs/ARCHITECTURE_AND_DESIGN.md)**: Deep technical architecture, algorithms (Tree-sitter AST, Myers, DMP, Moved Blocks, Keyed Grid, MMF, VFS, Secret Scrubber), and Windows 11 shell integration.
- **[Windows 11 Context Menu Setup](windows/Register-Windows11ContextMenu.ps1)**: MSIX Sparse package integration for top-level Windows 11 context menu.

---

## 💖 Support & Sponsoring

**diff_and_compare_tool** is a free, open-source project created and maintained for developers, engineers, and power users.

If this tool saves you time, streamlines your merge conflicts, or enhances your workflow, please consider sponsoring its development:

<p align="center">
  <a href="https://github.com/sponsors/vikrantblu">
    <img src="https://img.shields.io/badge/Sponsor_on_GitHub-vikrantblu-ea4aaa?style=for-the-badge&logo=github-sponsors" alt="Sponsor on GitHub" />
  </a>
</p>

### Where your sponsorship goes:
- 🚀 **New Studio Engines**: Developing further specialized format comparisons (e.g. 3D meshes, audio waveform, geospatial GIS diffing).
- 🔏 **Windows Code Signing Certificate**: Eliminating Windows SmartScreen warnings on installer executables.
- ⚡ **Continuous Maintenance & Performance**: Keeping AST grammars, PySide6, and BLAKE3 acceleration up to date.
- 🌐 **Documentation & CI/CD Pipelines**: Automated multi-architecture release packaging (x64 and ARM64).

Even if you cannot sponsor financially, you can support the project by:
- ⭐ **Starring the repository** on GitHub.
- 📢 Sharing it with colleagues and developer communities.
- 💬 Joining [GitHub Discussions](https://github.com/vikrantblu/diff_and_compare_tool/discussions) and submitting feedback or pull requests!

---

## 🤝 Contributing & Community

Contributions are welcomed!
- Please read our [Contributing Guide](CONTRIBUTING.md) for details on code style, architecture, and testing.
- Please review our [Code of Conduct](CODE_OF_CONDUCT.md) for community guidelines.
- To report a security vulnerability, refer to our [Security Policy](SECURITY.md).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).




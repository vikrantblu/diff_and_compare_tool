# diff_and_compare_tool — Next-Gen Diff & Merge Studio

A high-performance, cross-platform file comparison, 3-way merge, and multi-format data synchronization desktop suite built with Python (PySide6) and modern Windows 11 Fluent design principles.

![Application Status](https://img.shields.io/badge/Platform-Windows%2011%20x64%20Standalone-blue)
![Python](https://img.shields.io/badge/Python-3.11+-brightgreen)
![Framework](https://img.shields.io/badge/UI-PySide6%20Qt6-blueviolet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-vikrantblu%2Fdiff__and__compare__tool-blue?logo=github)](https://github.com/vikrantblu/diff_and_compare_tool)
[![Discussions](https://img.shields.io/badge/Discussions-Join%20Chat-teal?logo=github)](https://github.com/vikrantblu/diff_and_compare_tool/discussions)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-ea4aaa?logo=github-sponsors)](https://github.com/sponsors/vikrantblu)

---

## 🌟 8 Multi-Format Comparison Studios & Automation Suite

1. **⇄ 2-Way Text & Code Diff**:
   - **Tree-sitter AST Semantic Diffing**: Structural diffing for Python and JavaScript/TypeScript that detects reordered functions and docstring updates without false-positive line diffs.
   - **View Virtualization for 100k+ Lines**: Windowed sliding-window rendering keeps memory footprint at $O(\text{window})$ ($\approx 50\text{ KB}$), rendering massive files with zero UI latency.
   - **Diff Minimap & Visual Overview Ruler**: 16px navigation gutter displaying color-coded tick marks (green additions, red deletions, yellow modifications, orange conflicts, purple moves) with hover tooltips and click-to-jump line navigation.
   - **Native Rust/C++ Acceleration (BLAKE3 PyO3)**: Hardware-accelerated 64-character BLAKE3 hashing with memory-mapped (`mmap`) streaming for multi-megabyte source files.
   - **Live In-Line Buffer Swap (`Ctrl+U`)**: Instantly swaps left and right editor buffers in-place without file reloads or resetting cursor position.
   - Myers line diff + `diff_match_patch` intraline character-level precision.
   - **Moved Block Detection**: Identifies relocated functions/code with purple (`#8250df`) highlights.
   - **Noise & Regex Filtering**: Filter timestamps, GUIDs, commit hashes, memory addresses, and comments.
   - **Unified Patch Export**: One-click POSIX / Git `.patch` file export.
   - **Manual Alignment ("Align With...")**: Explicitly anchor matching lines across panes by right-clicking and selecting **Align With...** (or pressing `F7`), then clicking the target line on the opposing editor. The engine pins both lines to the exact same display row with clean vertical spacer padding (`·`). Click the HUD pill button (`📌 X Manual Alignments [✕]`) or press `Ctrl+F7` to clear.
   - **Resilient Section & Sub-Block Realignment**: Needleman-Wunsch dynamic programming sub-block alignment (`align_replace_block`) with markdown/heading section number normalization (`strip_section_number`) eliminates cascading alignment shifts caused by inserted or renumbered sections.
   - **Local-First AI PR Summary & Privacy Shield**: Automated Markdown pull request summaries with strict automated credential and PII scrubbing prior to AI ingestion.

2. **⧉ 3-Way Merge Studio**:
   - 3 synchronized viewports: **Mine (Local)** | **Base (Ancestor)** | **Theirs (Remote)**.
   - **Real-Time Collapsible Output Preview Pane**: Live 4th pane previewing the merge output buffer with real-time recalculation upon conflict resolution.
   - Automated conflict detection with real-time status counter.
   - Resolution actions: `Accept Mine`, `Accept Theirs`, `Accept Base`, and `Take Both`.
   - **AI Conflict Resolver**: Synthesizes conflict-free resolutions preserving intent from both branches with automated secret scrubbing.

3. **📁 Folder & Archive Comparison & Interactive Sync Hub**:
   - **Centered Diff Gutter (`GutterItemDelegate`)**: Custom Qt delegate rendering comparison and orphan status icons (`≠`, `←`, `→`, `=`) centered at exact column width without clipping, depth-based indentation shift, or scrollbar overlap, with synchronized active selection across trees.
   - **Interactive Folder Sync Hub (`🔄 Sync Hub...`)**: Full synchronization execution engine supporting Mirror L->R, Bi-directional Sync, and Update Left/Right with timestamp preservation (`shutil.copy2`) and orphan pruning.
   - **Smart `.gitignore` & Exclusion Rules**: Automatically detects and parses `.gitignore` and `.hgignore` files, pruning bloat directories (`node_modules/`, `__pycache__/`, `.venv/`, `.git/`) in-place during directory traversal.
   - **Asynchronous Background Worker**: Non-blocking `QThread` scanning prevents "(Not Responding)" lockups across 50,000+ files with live progress telemetry and cancellation.
   - **Folders-First Dual-Tree Hierarchy**: Clean alphabetical directory grouping with default collapsed state for massive repository comparisons.
   - **Smart Subfolder Matcher**: Automatically detects when a nested module on one side corresponds to the opposing root with 1-click direct compare.
   - **Instant In-Memory Filtering**: Toggle `* All`, `≠ Diffs`, `= Same` in $<15\text{ms}$ without re-reading the filesystem.
   - **Multi-Mode Rules**: Byte-by-byte (BLAKE3 / SHA-256 / CRC32 hash), size & timestamp, and rules-based comparison.
   - **Virtual Archive VFS**: Browse and diff `.zip`, `.jar`, `.tar`, `.tgz` files without manual decompression.

4. **🖼 Visual Media & Document Diff Studio (Images, Multi-Page PDF, SVG)**:
   - **Multi-Page PDF Document Comparison**: PyMuPDF (`fitz`) raster rendering with Page Prev/Next controls (`◀ Page X/Y ▶`).
   - **Extracted Text Diff View**: Side-by-side extracted text comparison viewer (`📄 Text Diff`) for documents.
   - **Photographic EXIF & Document Metadata Inspection**: Side-by-side metadata table (`📷 EXIF / Metadata`) highlighting camera EXIF tags, dimensions, author, and document attributes with diff highlights.
   - **Vector SVG Support**: Native DOM tree rasterization.
   - **Swipe Curtain**: Interactive draggable split slider.
   - **Onion-Skin**: Smooth 0-100% opacity transparency overlay.
   - **Difference Heatmap**: Tolerance-based pixel delta heatmap.
   - **Flicker / Blink**: High-frequency alternating blink timer to spot micro-differences.

5. **📊 Tabular / Spreadsheet Diff (CSV, TSV, Excel, Parquet, SQLite)**:
   - **Apache Parquet Ingestion**: Direct loading of `*.parquet` columnar data via `pyarrow`.
   - **SQLite Database Ingestion**: Direct inspection and table diffing of `*.db`, `*.sqlite`, `*.sqlite3` databases.
   - **Floating-Point Numerical Tolerance**: `Float Tol:` spinbox in the command bar (e.g. `0.001` precision); numerical values differing by $\le \text{tolerance}$ are evaluated as equal.
   - **Keyed Row Alignment**: Primary Key selector aligns records even if rows are sorted or reordered.
   - Cell-level mutation tracking with old-vs-new tooltips.
   - Dual synchronized horizontal and vertical scrolling.

6. **🌳 Structured Tree Diff (JSON, YAML, XML)**:
   - **JSONPath & XPath Query Bar**: Interactive query evaluation (e.g. `$.store.book[*].title` or `//item`) filtering large documents before diffing.
   - **Semantic Unordered Array Matching**: "Unordered Arrays" checkbox matches JSON array elements by value or entity identifiers (`id`, `key`, `name`, `uuid`) rather than rigid sequential indices.
   - Hierarchical node comparison independent of indentation or line formatting.
   - Key sorting option to ignore dictionary ordering.

7. **⚡ Hex & Binary Inspection Studio**:
   - **Memory-Mapped I/O (MMF)**: Opens multi-gigabyte binaries without UI lag or memory exhaustion.
   - 16-byte aligned rows (Offset, Hexadecimal, ASCII).
   - Byte-level mismatch tracking and instant Next/Prev difference jumping.

8. **🤖 Headless CI/CD Automation & CLI Stdin Diffing**:
   - Automated batch execution without GUI:
     ```powershell
     python app/main.py --folder-diff dir_a/ dir_b/ --report-html report.html --exit-code
     python app/main.py --diff file_a.py file_b.py --report-html diff.html --exit-code
     ```
   - **CLI Stdin Diffing**: Pipe command outputs directly into the diff engine without temp files:
     ```powershell
     git show HEAD~1:main.py | python app/main.py --diff - main.py
     ```
   - Standardized exit codes: `0 = Identical`, `1 = Content mismatch`, `2 = Error`.
   - Standalone, self-contained HTML diff reports with responsive styling.

9. **⚡ Live Visual Git Chunk Staging (`git apply --cached`)**:
    - Stage, unstage, or discard hunks directly inside the 2-way diff viewport.
    - Right-click diff connector or use top-bar `Git` dropdown to perform partial commits without leaving the editor.
    - Instant "Compare with Git HEAD" button.

10. **🛡️ Write-Ahead Log (WAL) Crash Recovery**:
    - Append-only JSONL transaction journal in `%APPDATA%/diff_and_compare/wal/` recording live keystrokes.
    - Automatic recovery prompt restores unsaved buffers upon unexpected shutdowns or crashes.

11. **🪟 Windows 11 Platform Polish, Single-Instance IPC & Shell**:
    - **Single-Instance IPC Tab Remoting**: Named pipes dispatch CLI/Explorer arguments to existing window tabs without process bloat.
    - **Custom High-Resolution Application Icon**: Signature dual-card Fluent icon embedded into the executable, taskbar, titlebar, and Windows Explorer context menus with 7 discrete raster mipmaps (`256×256` down to `16×16`).
    - **Branded Explorer Context Menu**: Top-level entries (`Compare with diff_and_compare_tool`, `diff_and_compare_tool: Select Left`, `diff_and_compare_tool: Select Right`) with direct icon binding.
    - **Windows 11 DWM Mica Alt Backdrop**: Native Mica Alt tabbed material backdrop via `DwmSetWindowAttribute`, synchronizing with light/dark theme toggles.
    - **Dynamic Multi-Session Tab Lifecycle & Pinned Home**: Clean cold launch with only the Home dashboard visible by default, permanent non-closable Home tab, resilient on-demand studio instantiation from launcher cards, and zero ghost-tab desynchronization upon closing and reopening comparisons.
    - **Rich Session Restoration**: Persists open tabs, active studio indices, and exact left/right/ancestor file and folder paths across application restarts.

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

- **Direct CLI Stream Diffing**: Support piping directly from stdin via `diff_and_compare.exe --diff - target.py` without writing temporary files.
- **Live Visual Git Chunk Staging**: Inline gutter actions (`[+] Stage Chunk`, `[-] Discard Chunk`) executing `git apply --cached` directly from the 2-way diff view.
- **Crash Recovery Journaling (WAL)**: Append-only write-ahead log in `%APPDATA%/diff_and_compare/wal/` ensuring in-flight edits survive unexpected crashes.

---

## 📚 Technical Documentation

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



# diff_and_compare_tool — Complete Functionality & User Guide

**diff_and_compare_tool** is a modern, high-performance, cross-platform file comparison, 3-way merge, and multi-format data synchronization desktop suite built with Python (PySide6) and optimized for Windows 11 standalone operation.

---

## 1. Feature Matrix & Capabilities

| Module | Core Functionality | Highlights |
| :--- | :--- | :--- |
| **2-Way File Diff** | Side-by-side text & code comparison | **Tree-sitter AST Semantic Diffing**, **View Virtualization for 100k+ lines**, **Diff Minimap & 16px Overview Ruler**, **Native BLAKE3 PyO3 Hashing**, **In-line Buffer Swap (`Ctrl+U`)**, **Live Visual Git Chunk Staging (`git apply --cached`)**, Myers line diff + DMP intraline, Beyond Compare spacers, **Moved Blocks**, **Noise filters**, **Patch export**, and **AI PR summaries**. |
| **3-Way Merge Studio** | 3-way ancestor-based merge | Mine vs Base vs Theirs alignment, conflict detection, **Collapsible 4th Merge Output Preview Pane**, resolution ribbon (`Accept Mine`, `Accept Theirs`, `Accept Base`, `Take Both`), and **AI Conflict Resolver**. |
| **Directory & Archive Compare** | Folder and archive synchronization | **Interactive Folder Sync Hub (`🔄 Sync Hub...`)** (Mirror, Bi-directional, Update), **Smart `.gitignore` & exclusion rules**, **Adaptive Batch Throttling (250 items/50ms)**, BLAKE3/SHA-256 hash validation, and **Virtual Archive VFS** (browsing `.zip`, `.jar`, `.tar` without decompression). |
| **Visual Media & Document Diff** | Image & PDF comparison studio | **Multi-Page PDF Comparison (`fitz`)**, **Extracted Text Diff View**, **Photographic EXIF & Metadata Table**, **SVG Vector Rendering**, **Swipe Curtain slider**, **Onion-Skin transparency**, **Difference Heatmap**, and **Flicker/Blink mode**. |
| **Tabular / Spreadsheet Diff** | CSV, TSV, Excel, Parquet, SQLite | **Float Tolerance (`Float Tol:`)**, **Streaming Apache Parquet (`*.parquet`, 5000-row chunks)**, **Streaming SQLite (`*.db`, `*.sqlite`)**, **Keyed Row Alignment** (Primary Key selector), cell mutation tooltips, and synchronized dual grids. |
| **Structured Tree Diff** | JSON, YAML, and XML tree comparison | **JSONPath & XPath Query Bar**, **Semantic Unordered Array Matching**, hierarchical node comparison, **Key Sorting**, and diffs-only filter. |
| **Hex & Binary Diff** | Memory-mapped binary inspector | 16-byte chunking, offset, hexadecimal, ASCII views, **mmap streaming for multi-GB files**, and Next/Prev diff seeking. |
| **Headless CI/CD Automation** | Non-GUI batch diffing & reporting | `--folder-diff`, `--diff`, `--report-html`, `--exit-code` (0 = identical, 1 = mismatch, 2 = error). **CLI Stdin Diffing (`--diff - <file>`)**. Standalone responsive HTML reports. |
| **Single-Instance IPC & Shell** | Desktop tab remoting & Win11 shell | **Windows Named Pipes (`QLocalServer`/`QLocalSocket`)** routing Explorer/CLI files into active window tabs without launching new processes. Explorer context menu ("Compare with diff_and_compare_tool", "diff_and_compare_tool: Select Left", "diff_and_compare_tool: Select Right"). |
| **Write-Ahead Log (WAL)** | Zero-data-loss crash recovery | **Append-only JSONL transaction journal (`%APPDATA%/diff_and_compare/wal/`)** persisting live keystrokes and buffer states. Automatic crash recovery prompt on startup. |
| **Local-First AI & Privacy** | AI assistance with zero leakage | **Automated Secret & PII Scrubber** (redacts AWS keys, tokens, JWTs, passwords), local Ollama models (**`qwen2.5-coder`**, `deepseek-coder`, `codellama`), and `🛡️ Privacy Shield`. |
| **Windows 11 Polish & Shell** | Native OS effects & session restore | **Windows 11 DWM Mica Alt Backdrop**, **Rich Session Restoration** across tabs & file paths, **ARM64 Native Target**, and **IExplorerCommand context menus**. |
| **Git Tool Pluggability** | Version control integration | Direct CLI flags to function as external **`git difftool`** and **`git mergetool`**. |
| **Workspaces & Sessions** | Multi-session tab management | Concurrent tabs, dynamic "+ New Tab" creation, **automatic session restore**, and named comparison workspace profiles. |

---

## 2. 2-Way File Comparison View

### 2.1 Live In-Place Text Editing
- **Native Document Integrity**: Both left and right panes are fully functional code editors. You can type, backspace, delete, paste, select, and cut without restriction.
- **Debounced Real-Time Diffing (200ms)**: Diff calculations run reactively in the background as you type.
- **Non-Destructive Highlighting**: Color highlights are applied strictly via `QTextEdit.ExtraSelection` in Qt's paint layer. Keystrokes never reset your cursor or wipe your undo history.
- **Full Undo/Redo**: `Ctrl+Z` (Undo) and `Ctrl+Y` (Redo) work smoothly across all typing sessions.

### 2.2 Horizontal Line Alignment, Manual Anchoring ("Align With...") & Sub-Block Realignment
- **Automatic Alignment**: When one file contains insertions or deletions, the opposing file receives visual **spacer lines** (rendered as `·` in the gutter).
- **Zero Vertical Drift**: Matching functions and lines always align on the **exact same horizontal pixel row**.
- **Unnumbered Spacers**: Real file lines display their true 1-based line numbers; spacer rows remain unnumbered.
- **Clean File Saving**: The save engine automatically strips visual spacer lines via `get_clean_text()`, ensuring saved files on disk are 100% clean.
- **Aligned View Toggle**: You can toggle the "Aligned View (Spacers)" checkbox on the toolbar to switch between aligned spacer mode and raw unpadded mode at any time.
- **Manual Alignment ("Align With...")**:
  - Right-click any line on either the Left or Right editor and select **📌 Align With... (Line X)**, or position the cursor and press **`F7`**.
  - An interactive banner appears: *"Click a line in the Right/Left editor to align with Line X... [Cancel (Esc)]"*.
  - Click the matching target line on the opposing editor. The engine immediately locks both lines to the identical horizontal display row, computing optimal spacer padding above the anchor.
  - Active manual alignments are tracked in the command bar with a status pill: `📌 1 Manual Alignment [✕]`.
  - To clear alignments, click the `[✕]` pill button or press **`Ctrl+F7`**.
- **Resilient Section & Sub-Block Realignment**:
  - When comparing documents with inserted or renumbered sections (e.g., Markdown headings such as `### 8.2 IPC Tab Remoting` vs `### 8.3 Git Staging`), standard line-matching can cascade mismatches down the file.
  - The engine automatically applies **Needleman-Wunsch dynamic programming** within modification chunks paired with **heading section number normalization** (`strip_section_number`).
  - Headings with matching content (e.g. `### 8.3 Live Visual Git Chunk Staging` and `### 8.2 Live Visual Git Chunk Staging`) are recognized as matching and aligned directly across from each other, while inserted subsections cleanly receive vertical spacers on the opposing pane.

### 2.3 Tree-sitter AST Semantic Diffing
- **Structural Syntax Understanding**: Integrates Tree-sitter grammar parsers for Python, JavaScript, and TypeScript (with a native Python `ast` fallback).
- **False-Positive Elimination**: Reordered functions, classes, and methods are recognized as structural moves rather than separate blocks of deleted and inserted lines.
- **Docstring & Comment Disambiguation**: Differentiates between functional logic alterations and comment/docstring edits, annotating chunks with human-readable semantic explanations.
- **AST Semantic Toggle**: Enable or disable AST analysis with the `AST Semantic` checkbox in the command bar.

### 2.4 View Virtualization for Massive Files (100k+ Lines)
- **Sliding-Window Viewport**: Files exceeding 3,000 lines activate automatic windowed sliding virtualization (`WINDOW_SIZE = 300`).
- **Bounded Memory Footprint**: Keeps active viewport memory bounded at $O(\text{window})$ ($\approx 50\text{ KB}$) instead of loading hundreds of megabytes into Qt text layouts.
- **Zero Scroll Lag**: Scrolling through 100k+ line logs or generated code files remains silky smooth at 60 FPS.

### 2.5 Diff Minimap & Visual Overview Ruler
- **16px Overview Gutter**: Located on the right edge of editors, visualizing all document mutations scaled to the document height.
- **Color-Coded Semantic Ticks**:
  - 🟢 **Green**: Inserted lines.
  - 🔴 **Red**: Deleted lines.
  - 🟡 **Yellow / Blue**: Modified lines.
  - 🟠 **Orange**: Merge conflicts.
  - 🟣 **Purple**: Relocated / moved code blocks.
- **Interactive Navigation**: Hover over any tick mark to view line numbers and difference summaries; click any tick to jump the editor directly to that change.

### 2.6 Live In-Line Diff Swapping (`Ctrl+U`)
- **Instant Direction Flip**: Press `Ctrl+U` or click `⇄ Swap (Ctrl+U)` in the ribbon to swap left and right editor buffers in-place.
- **No File Reloads**: Swapping preserves active modifications, line alignment, and editor cursor state without re-reading files from disk.

### 2.7 Native Rust/C++ BLAKE3 Hash Acceleration
- **Native PyO3 BLAKE3**: Uses compiled native BLAKE3 hashing (`algo='blake3'`) with multi-threaded SIMD tree hashing.
- **NVMe Memory Streaming**: Automatically activates `mmap` streaming for files larger than 10 MB.

### 2.8 Moved Block Detection
- **Relocation Tracking**: Identifies code and text blocks moved across files rather than falsely labeling them as separate deletions and additions.
- **Visual Distinctiveness**: Relocated blocks are highlighted in purple (`#8250df`) with linked block indices and destination lines.

### 2.9 Noise & Regular Expression Filtering
- **Dynamic Regex Presets**: Pre-configured filters to ignore timestamps, GUIDs/UUIDs, Git commit hashes, memory addresses, and comments (C/C++/Java/JS and Python).
- **Whitespace Tolerance**: Compare exact whitespace, ignore leading/trailing whitespace, or ignore all whitespace.
- **Case Tolerance**: Ignore case differences across documents.

### 2.10 Unified Patch Export & AI PR Summarizer
- **Export .patch**: Exports standard POSIX / Git unified diff patch format (`--- a/... +++ b/... @@ ... @@`).
- **Local-First AI PR Summary**: One-click generation of structured Markdown PR descriptions, executive summaries, risk assessments, and test checklists with automated credential scrubbing.

### 2.11 Pane Headers & Diff Status Telemetry
- **Role Identification**: Distinct, elevated pill badges identify pane roles (`MINE / LEFT` in soft blue, `THEIRS / RIGHT` in soft green).
- **Clean Filename Baseline**: Displays active filenames with full filepath tooltips, free of distracting underlines or border artifacts.
- **Contextual Diff Badges**: Real-time per-file delta pills (`+added` in green, `-deleted` in red, `~modified` in blue) equipped with descriptive tooltips.
- **Encoding & Actions**: Displays live file encoding and line endings (`UTF-8 | LF`) alongside immediate `Browse...` and `Save` actions.

---

## 3. 3-Way Merge Studio

### 3.1 3-Pane Ancestor Viewport
- **Mine (Left)**: Your local working branch changes.
- **Base (Center)**: The common ancestor commit.
- **Theirs (Right)**: The incoming or remote branch changes.
- **Output (Bottom)**: Live merged result buffer with real-time recalculation and manual editing freedom.

### 3.2 Real-Time Merge Output Preview Pane
- **Interactive Output Viewport**: Expandable 4th bottom output preview pane toggled via `👁 Output Preview`.
- **Dynamic Resolution Updates**: Resolving conflict blocks immediately updates the merged text buffer in real time.
- **Synchronized Conflict Markers**: Overview ruler and gutter markers reflect remaining vs resolved conflict regions dynamically.

#### 3.3 Automated Conflict Detection & Resolution Ribbon
- **Conflict Status HUD**: Real-time counter showing remaining unresolved conflicts.
- **One-Click Resolutions**:
  - `Accept Mine`: Takes your branch's logic for the selected conflict block.
  - `Accept Theirs`: Takes incoming remote branch logic.
  - `Accept Base`: Reverts back to common ancestor logic.
  - `Take Both`: Appends both modifications in sequence.
  - `AI Resolve`: Uses local AI / semantic heuristics to synthesize a conflict-free resolution with automated secret scrubbing.

---

## 4. Folder & Virtual Archive Comparison Studio (Folders, VFS)

### 4.1 Asynchronous Background Comparison Engine
- **Non-Blocking Multithreaded Architecture**: Folder scanning (`os.walk`), hash computation, and item diffing execute inside a dedicated background worker (`FolderCompareWorker : QThread`). The application interface remains 100% responsive, preventing Windows from marking the application as "(Not Responding)" even when scanning 50,000+ files.
- **Real-Time Progress Indicator**: Live scanning telemetry displaying evaluated item counts (e.g. `● Scanning Left: 1,500 items found...`, `● Comparing items (3,200/13,107)...`).
- **Interactive Cancellation**: Users can interrupt long-running scans at any time using the `Cancel` button in the status log bar.

### 4.2 Interactive Folder Synchronization Hub (`🔄 Sync Hub...`)
- **Full Execution Engine**: Accessible via the `🔄 Sync Hub...` toolbar action button, providing structured synchronization modes:
  - **Mirror Left to Right**: Makes the right folder an exact replica of the left, copying modified/missing files and pruning right-side orphans.
  - **Bi-directional Sync**: Propagates newest file changes both ways based on timestamps while preserving unique files.
  - **Update Left**: Copies missing or newer files from Right to Left.
  - **Update Right**: Copies missing or newer files from Left to Right.
- **Pre-Flight Action Preview**: Presents an exhaustive itemized checklist detailing each operation (`copy_l2r`, `copy_r2l`, `delete_r`, `delete_l`) with exact file paths and byte sizes.
- **Safe Execution & Timestamp Preservation**: Uses `shutil.copy2` to preserve file modification timestamps across sync runs.

### 4.3 Smart `.gitignore` & Bloat Directory Exclusion
- **Automatic Ignore Detection**: Automatically detects and parses `.gitignore` and `.hgignore` files in root directories.
- **Default Bloat Pruning**: Automatically prunes non-source directories (`node_modules/`, `__pycache__/`, `.venv/`, `.git/`, `.idea/`, `.vscode/`) in-place during directory traversal, speeding up scans by up to 10×.
- **Toggle Control**: Enable or disable ignore filtering via the `Respect .gitignore` checkbox in the folder command ribbon.

### 4.4 Side-by-Side Dual-Tree Synchronization
- **Folders-First Alphabetical Grouping**: Folders are sorted case-insensitively and displayed at the top of each directory level, followed by files.
- **Default Collapsed Hierarchy**: Large folder comparisons start in a clean collapsed state, allowing all top-level items across both roots to fit on screen immediately without lag.
- **Center Difference Gutter (`GutterItemDelegate`)**:
  - **Pixel-Centered Status Icons**: A dedicated `QStyledItemDelegate` computes absolute viewport row bounds (`QRect(0, y, viewport_width, h)`), rendering comparison glyphs dead-center without rightward drift:
    - `≠` (Red bold): Content or structural difference in files or matched folders.
    - `←` (Blue): Left orphan (exists only on the left side).
    - `→` (Purple): Right orphan (exists only on the right side).
    - `=` (Slate): Content or hash match.
  - **Zero Tree Indentation (`setIndentation(0)`)**: Prevents nested subfolder items from shifting horizontally into the column border.
  - **Protected Viewport & Scrollbar Exclusion**: `ScrollBarAlwaysOff` ensures scrollbars never constrict the 64px gutter column, scrolling programmatically in lockstep with the outer trees.
  - **Synchronized Active Row Selection**: Clicking or navigating through any item in Left, Center Gutter, or Right updates current item selection across all 3 viewports simultaneously.
  - **Double-Click Diff Launch**: Double-clicking files directly in the center gutter opens them in the 2-Way Text Diff Studio, while folders toggle branch expansion.
- **Clean Spacer Alignment Without Ghost Carets**: Items that exist only on one side render clean, non-expandable placeholder rows on the opposing side (`DontShowIndicator`), preventing empty chevrons from cluttering the viewport.
- **O(1) Branch Synchronization**: Expand and collapse actions across Left, Center Gutter, and Right trees are synchronized instantaneously via direct memory-pointer cross-references without recursive lookups.

### 4.5 Smart Subfolder Matcher & Base Folder Navigation
- **Automatic Subfolder Detection**: When comparing a root repository against a modular subcomponent (or vice versa), the engine automatically detects if a subfolder on one side matches the opposite root.
- **1-Click Smart Suggestion Banner**: Displays an actionable banner (`💡 Subfolder Match: Left folder contains 'astro_engine', which corresponds directly to Right folder. [Compare Directly ➜]`) to re-root comparison with a single click.
- **Context Menu Navigation**:
  - `📂 Set as Left/Right Base Folder`: Right-click any folder to navigate directly into it as the new comparison root.
  - `📁 Open in File Explorer`: Reveal the folder or file in Windows Explorer.
  - `📋 Copy Path`: Copy the full path to the clipboard.
- **Up-One-Level (`↑`) Navigation**: Easily ascend parent folders on either side independently.
- **Intelligent Double-Click**: Double-clicking a folder toggles expansion; double-clicking a file immediately launches it in the 2-Way Text Diff Studio.

### 4.6 Instant In-Memory View Filtering & Validation Rules
- **Zero-Latency Filtering**: Toggling between `* All`, `≠ Diffs`, and `= Same` filters existing tree nodes in-memory (<15ms) without touching the hard drive or re-scanning files.
- **Wildcard Inclusion & Exclusion**: Real-time filename pattern filtering (e.g. `-*.tmp; *.py; -kb_*.*`).
- **Multi-Mode Validation Rules**:
  - **BLAKE3 / SHA-256**: Cryptographic hash comparison with memory-mapped streaming.
  - **Size & Timestamp Match**: High-speed metadata matching for large directory trees.
  - **Rules-Based**: Ignores line endings (CRLF vs LF) and whitespace variations in text files.

---

## 5. Multi-Format Comparison Studios

### 5.1 Visual Media & Document Diff Studio (Images, Multi-Page PDF, SVG)
- **Multi-Page PDF Document Comparison**: Powered by PyMuPDF (`fitz`), enabling page-by-page visual raster comparison with contextual vector pagination controls (`← Page X/Y →`), automatically shown only when multi-page documents are loaded.
- **Extracted Text Diff View**: Toggle `Text Diff` (with document icon) to inspect extracted document text side-by-side.
- **Photographic EXIF & Document Metadata Table**: Toggle `EXIF / Metadata` (with sliders icon) to display a side-by-side inspection table of camera EXIF tags, dimensions, creation dates, and author properties, highlighting mismatched values in soft yellow.
- **Vector SVG Support**: Native DOM tree rasterization.
- **Swipe Curtain**: Interactive split slider over the canvas; dragging left or right reveals the Left vs Right image with high visual precision.
- **Onion-Skin (Alpha Blend)**: Smooth opacity overlay slider (0% to 100%) to spot subtle shifts, alignments, or alpha changes.
- **Difference Heatmap**: Tolerance-based pixel delta computation highlighting mutations in neon pink/magenta while dimming identical pixels.
- **Flicker / Blink Mode**: High-frequency alternating blink timer (2Hz to 5Hz) making sub-pixel micro-mutations instantly pop to human vision.
- **Side-by-Side View**: Synchronized dual display with dimension metadata.

### 5.2 Tabular / Spreadsheet Diff (CSV, TSV, Excel, Parquet, SQLite)
- **Apache Parquet Ingestion**: Direct loading of `*.parquet` columnar files via `pyarrow`.
- **SQLite Database Ingestion**: Direct inspection and table diffing of `*.db`, `*.sqlite`, `*.sqlite3` databases with clean connection lifecycle management.
- **Floating-Point Numerical Tolerance**: `Float Tol:` spinbox in the command bar (e.g. `0.001` precision); numerical values differing by $\le \text{tolerance}$ are evaluated as equal.
- **Keyed Row Alignment**: Designate a Primary Key column (e.g. `id`, `user_id`, `sku`). Rows are matched and aligned by their key value regardless of row ordering or sorting.
- **Cell-Level Mutation Tracking**: Cells with modified values are highlighted in yellow with hover tooltips displaying `Original: X ➔ Modified: Y`.
- **Synchronized Dual Grids**: Vertical and horizontal scrollbars are locked in lockstep across both tables.
- **Diffs Only Filter**: Quickly hide thousands of identical rows and focus exclusively on changed records.

### 5.3 Structured Tree Diff (JSON, YAML, XML)
- **JSONPath & XPath Query Bar**: Interactive query evaluation (e.g. `$.store.book[*].title` or `//item`) filtering large documents before diffing.
- **Semantic Unordered Array Matching**: "Unordered Arrays" checkbox matches JSON array elements by value or entity identifiers (`id`, `key`, `name`, `uuid`) rather than rigid sequential indices.
- **Hierarchical Tree View**: Parses and compares tree structures independently of whitespace or line breaks.
- **Key Sorting**: Ignores dictionary/object key ordering variations.
- **Status Highlighting**: Added nodes (green), deleted nodes (red), modified values (yellow), and unchanged nodes (gray).
- **Expand / Collapse All & Search**: Instant filtering and navigation across deeply nested objects.

### 5.4 Hex & Binary Inspection Studio
- **Memory-Mapped I/O (MMF)**: Opens multi-gigabyte binary files, firmware images, and database dumps without loading the entire file into RAM.
- **16-Byte Rows**: Displays 8-digit hexadecimal offset (`00000000`), 16 hex byte pairs, and printable ASCII representation.
- **Byte Mutation Highlighting**: Identifies and highlights every differing byte index.
- **Next / Prev Difference Navigation**: Jump directly to the next or previous byte mismatch across millions of rows.

### 5.5 Virtual Archive Filesystem (VFS)
- **Transparent Archive Browsing**: Browse `.zip`, `.jar`, `.tar`, `.tgz`, `.tar.gz`, `.tar.bz2` compressed files directly in Folder Compare as virtual directory structures.
- **In-Memory Streaming**: Inspects contents, sizes, and CRCs without decompressing gigabytes of archives to disk.

---

## 6. Headless CI/CD Automation & Reporting

Automate diffing and verification directly in CI/CD build scripts, commit hooks, or headless servers without initializing a GUI:

### 6.1 CLI Syntax & Usage
```powershell
# Folder comparison with HTML report and automated exit code
python app/main.py --folder-diff dir_a/ dir_b/ --report-html folder_report.html --exit-code

# 2-Way File diff with HTML report
python app/main.py --diff file_a.py file_b.py --report-html diff_report.html --exit-code
```

### 6.2 Standardized Exit Codes
| Exit Code | Meaning |
| :---: | :--- |
| `0` | **Identical / Content Match**: Files or directories match according to rules. |
| `1` | **Mismatch Detected**: One or more files differ, or additions/deletions exist. |
| `2` | **Error**: Missing file, invalid directory path, or permission denied. |

---

## 7. Local-First AI Assistant & Secret Scrubber

### 7.1 Automated Secret & PII Scrubber
- **Pre-Ingestion Redaction**: Automatically scans and redacts sensitive credentials prior to AI prompt construction:
  - AWS Access Keys (`AKIA...`) and Secret Keys
  - JSON Web Tokens (`eyJ...`)
  - GitHub Personal Access Tokens (`ghp_...`)
  - RSA / SSH Private Keys (`-----BEGIN PRIVATE KEY-----`)
  - Passwords and Database URLs
  - IP addresses and Email addresses
- **Audit Badge**: Displays a green `🛡️ Privacy Shield Active` status badge in the UI and appends redaction audit notes to summaries.

### 7.2 Local LLM Integration
- **Ollama Coder Models**: Directly connects to local Ollama instances (`localhost:11434`) supporting models like **`qwen2.5-coder`**, `deepseek-coder`, `codellama`, and `llama3`.
- **Zero Outbound Heuristic Fallback**: Built-in intelligent heuristic engine operates completely offline without sending any data over the network.

---

## 8. Native Windows 11 & Shell Integration

### 8.1 Windows 11 DWM Mica Alt Backdrop
- Utilizes `ctypes.windll.dwmapi` to activate native Windows 11 Mica Alt (`DWMWA_SYSTEMBACKDROP_TYPE = 4`) and rounded corners (`DWMWCP_ROUND`).
- Dynamically responds to theme switching, matching Windows 11 Fluent dark and light aesthetics.

### 8.2 Dynamic Multi-Session Tab Lifecycle & Home Launcher
- **Clean Beyond Compare Launch Experience**: The application starts cleanly with only the signature **Home** launcher dashboard displayed by default, eliminating visual clutter from pre-opened blank comparison tabs.
- **Pinned Permanent Home Tab**: The `Home` tab is anchored at index 0 and protected from closure (the close `[✕]` button is permanently removed). You can return to the Home launcher at any time via the tab bar, the top-right `Home` corner button, or the `Session → Home Screen` menu item.
- **On-Demand Studio Instantiation**: Clicking any session card on the Home dashboard (**Image Diff Studio**, **Folder Compare**, **Folder Merge**, **Folder Sync**, **Text Compare**, **Text Merge**, **Table / CSV Compare**, or **Hex & Binary Diff**) dynamically checks for an open, empty tab or instantiates a fresh studio tab and immediately brings it into focus.
- **Resilient Close & Re-Open Behavior**: Closing any comparison tab via its `[✕]` button gracefully unmounts the view and cleans up active write-ahead logs (WAL). Re-clicking the corresponding Home launcher card immediately opens a new instance, completely preventing unresponsive or orphaned "ghost" tabs.
- **Multi-Tab Sessions & Dynamic Numbering**: Multiple comparisons of the same or different studio types can run concurrently. New tabs can be spawned from the `+ New Tab` dropdown or the `Session` menu, with automated numbering (e.g., `Text Diff (2)`, `Image Diff (2)`).
- **Drag-and-Drop & Smart File Routing**: Dropping files or folders onto the Home canvas or invoking `smart_open_comparison` automatically detects file formats (images, tables, archives, directories, text) and opens the corresponding studio tab.

### 8.3 Rich Session Restoration
- Automatically persists open tabs, active studio indices, and exact left/right/ancestor file and folder paths in `%APPDATA%/diff_and_compare/active_session.json`.
- Restores full comparison state on subsequent application launches.

### 8.4 ARM64 Native Target
- The packaging tool (`build.py`) supports native Windows ARM64 builds (`python build.py --target-arch arm64`) with pre-configured hidden imports for Tree-sitter, PyMuPDF, PyArrow, and BLAKE3.

### 8.5 Git Integration (`git difftool` & `git mergetool`)
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

### 8.6 Windows Explorer Context Menu & Complete Registry Integration
- **Branded Explorer Menu Verbs**:
  - `Compare with diff_and_compare_tool`: Directly launches comparison between selected targets or opens the selected item.
  - `diff_and_compare_tool: Select Left`: Stages the selected file or folder in local application cache as the Left comparison baseline.
  - `diff_and_compare_tool: Select Right`: Immediately launches comparison between the previously staged Left item and the selected Right target.
- **Registry Targets Registered**:
  - `HKCU\Software\Classes\*\shell`: Right-click on any file.
  - `HKCU\Software\Classes\Directory\shell`: Right-click on any folder.
  - `HKCU\Software\Classes\Directory\Background\shell`: Right-click on empty folder background (`%V`).
  - `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare.exe`: Launch via `Win+R` or CLI by typing `diff_and_compare`.
  - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool`: Full Windows Settings "Installed Apps" & "Add or Remove Programs" uninstaller registration.
  - `HKCU\Environment\PATH`: Automatic user PATH registration.
- **Custom High-Resolution Application Icon**:
  - Bound directly to `assets/app_icon.ico` in the Windows registry, ensuring the crisp dual-card Fluent logo displays next to every menu item in Windows Explorer.
  - Integrated with Windows AppUserModelID (`DiffAndCompareTool.Studio.1.0`) so the application displays its custom icon in the Windows taskbar, window titlebar, and Alt+Tab task switcher.
- **Installation & Uninstallation Options**:
  - **Double-Click Setup Executable**: Run `dist/Setup_diff_and_compare_tool.exe` (native Windows installation wizard with LZMA2 compression, auto-deploying binaries, icons, registry integration, and Windows Installed Apps registration).
  - **1-Click Turnkey Setup**: Double-click `Install.cmd` in `dist/diff_and_compare_installer` or `windows/` (deploys to `%LOCALAPPDATA%\Programs\diff_and_compare_tool` without requiring Administrator privileges).
  - **PowerShell Script**: Run `windows/Install-DiffAndCompare.ps1`.
  - **In-App Menu**: Managed seamlessly via **Tools → Windows Explorer Integration** or from the Home tab.
  - **CLI Command**:
    ```powershell
    # Full registry integration (Context Menu, App Paths, Installed Apps entry)
    python app/main.py --install-all
    python app/main.py --uninstall-all

    # Shell context menu only
    python app/main.py --install-shell
    python app/main.py --uninstall-shell

    # Export customized .reg file
    python app/main.py --export-reg MySetup.reg
    ```
  - **Uninstallation**: Double-click `Uninstall.cmd` or remove via Windows Settings -> Installed Apps -> `diff_and_compare_tool`.

---

## 9. Keyboard Shortcuts Reference

| Shortcut | Scope | Action |
| :--- | :--- | :--- |
| `Ctrl+U` | 2-Way Diff | Swap Left and Right Editor Buffers in-place |
| `F7` | 2-Way Diff / Hex | Jump to Previous Difference |
| `F8` | 2-Way Diff / Hex | Jump to Next Difference |
| `Ctrl+Z` | 2-Way Diff / Editor | Undo edit or accepted hunk transfer |
| `Ctrl+Y` / `Ctrl+Shift+Z` | 2-Way Diff / Editor | Redo edit or hunk transfer |
| `Ctrl+F` | Folders / VFS | Focus Explorer Search text box (real-time tree filter) |
| `Ctrl+F` | 2-Way Diff | Open in-editor Find bar (docked live search) |
| `F3` / `Enter` | 2-Way Diff | Find Next occurrence in diff editors |
| `Shift+F3` / `Shift+Enter` | 2-Way Diff | Find Previous occurrence in diff editors |
| `Esc` | Diff / Folders | Close Find bar or clear Explorer search |
| `Ctrl+S` | Editor | Save active file buffer |
| `Ctrl+A` | Editor | Select all text |
| `Alt+Up` | 3-Way Merge | Jump to Previous Conflict |
| `Alt+Down` | 3-Way Merge | Jump to Next Conflict |

---

## 10. Architecture Resilience & Strategic Roadmap

### 10.1 Decoupled Canonical Aligned Model
- Restricts Qt text widget allocations to an active 300-line sliding window while preserving the complete alignment map in memory as an array of `AlignedRow` structs ($\approx 20\text{--}40\text{ MB}$ for 500,000 lines).
- Computes gutter line numbers dynamically from canonical row indices, preserving mathematical line continuity and preventing spacer line (`·`) numbering drift.

### 10.2 Event-Loop Batch Throttling During Folder Scans
- Employs an adaptive batch throttle (250 items or 50ms interval) in `FolderCompareWorker` to prevent signal-emission saturation across Qt threads, maintaining 60 FPS UI responsiveness when scanning repositories with 50,000+ files.

### 10.3 Streaming Columnar Projection & Cursor Chunking
- **Parquet**: Uses `pyarrow.dataset.Scanner` to stream only projected columns and row batches, eliminating memory spikes on multi-gigabyte files.
- **SQLite**: Queries schema headers via `PRAGMA table_info` and streams primary-key-ordered rows using cursor `fetchmany(5000)` batches.

### 10.4 Binary Footprint Optimization & Modular Packaging
- Uses PyInstaller's `--onedir` distribution to eliminate the $500\text{ MB}$ startup decompression overhead of single-file packages.
- Strips unused Qt modules (`QtQuick`, `QtQml`, `QtSensors`, `QtTest`, `QtNetworkAuth`) and injects the custom icon directly into the PE header via `--icon assets/app_icon.ico`.

### 10.5 Direct CLI Stream & Stdin Diffing
- Pipe directly into the diff engine without intermediate disk files:
  ```powershell
  # Stdin diffing against active working copy
  git show HEAD~1:app/main.py | python app/main.py --diff - app/main.py

  # Headless automated CI/CD comparison on piped streams
  cat test_data.json | python app/main.py --headless --diff - expected.json --exit-code
  ```
- Synthesizes an in-memory stream buffer adopting the opposing file's extension, ensuring perfect syntax highlighting and `atexit` cleanup.

### 10.6 Live Visual Git Chunk Staging
- Full Git index staging directly within the 2-Way Diff View.
- Accessible via the **`Git` dropdown menu** in the top toolbar or by **right-clicking on the connector bridge** or editor chunks:
  - **`➕ Stage Hunk to Git Index`**: Applies the selected diff chunk via `git apply --cached --unidiff-zero -`.
  - **`↺ Unstage Hunk from Index`**: Removes hunk from index via `git apply --cached --reverse --unidiff-zero -`.
  - **`🗑 Discard Hunk Changes`**: Reverts local working copy modifications via `git apply --reverse --unidiff-zero -`.
  - **`🔍 Compare with Git HEAD`**: Loads committed Git HEAD content into the Left pane and working copy into the Right pane in one click.

### 10.7 Write-Ahead Log (WAL) Crash Recovery Journaling
- Automatic resilience against power outages, unexpected reboots, or task kills.
- Every live keystroke in the editor buffers is recorded to an append-only JSONL journal in `%APPDATA%/diff_and_compare/wal/`.
- On application restart after an abnormal termination, an automatic recovery prompt detects uncommitted modifications and allows instant single-click buffer restoration.
- Journals are cleanly pruned on normal application shutdown.



# Git Difftool & Mergetool Setup Guide

`diff_and_compare_tool` supports standard CLI flags out-of-the-box, allowing it to serve as your primary `git difftool` and `git mergetool`.

---

## 1. Configure as `git difftool`

### Option A: Standalone Executable (Installed or on PATH)
```bash
git config --global diff.tool diff_and_compare
git config --global difftool.diff_and_compare.cmd "diff_and_compare.exe --diff \"\$LOCAL\" \"\$REMOTE\""
git config --global difftool.prompt false
```

### Option B: Running from Python Source
```bash
git config --global diff.tool diff_and_compare
git config --global difftool.diff_and_compare.cmd "\"python\" \"/path/to/diff_and_compare_tool/app/main.py\" --diff \"\$LOCAL\" \"\$REMOTE\""
git config --global difftool.prompt false
```

### Usage:
```bash
git diff                   # View terminal diff
git difftool               # Opens changes in diff_and_compare_tool
git difftool HEAD~1 HEAD   # Compare commit with parent
```

---

## 2. Configure as `git mergetool`

### Option A: Standalone Executable (Installed or on PATH)
```bash
git config --global merge.tool diff_and_compare
git config --global mergetool.diff_and_compare.cmd "diff_and_compare.exe --merge \"\$LOCAL\" \"\$BASE\" \"\$REMOTE\" --output \"\$MERGED\""
git config --global mergetool.diff_and_compare.trustExitCode true
git config --global mergetool.prompt false
```

### Option B: Running from Python Source
```bash
git config --global merge.tool diff_and_compare
git config --global mergetool.diff_and_compare.cmd "\"python\" \"/path/to/diff_and_compare_tool/app/main.py\" --merge \"\$LOCAL\" \"\$BASE\" \"\$REMOTE\" --output \"\$MERGED\""
git config --global mergetool.diff_and_compare.trustExitCode true
git config --global mergetool.prompt false
```

### Usage during merge conflicts:
```bash
git merge feature-branch   # Conflict occurs!
git mergetool              # Opens 3-Way Merge Studio with Mine, Base, Theirs, and AI Resolve
```

---

## 3. Specialized CLI Modes

```powershell
# 1. Compare two images (Swipe curtain / Heatmap)
diff_and_compare.exe --image-diff logo_v1.png logo_v2.png

# 2. Compare two CSV / Excel spreadsheets
diff_and_compare.exe --table-diff sales_q1.csv sales_q2.csv

# 3. Compare two binary files in Hex inspection mode
diff_and_compare.exe --hex-diff firmware_v1.bin firmware_v2.bin
```

"""
Application Entry Point for diff_and_compare_tool (PySide6 Standalone)
Includes:
- Windows Explorer Context Menu integration ("Select Left", "Select Right", "Select files to compare")
- Home / Welcome Studio launcher
- Git Difftool & Mergetool CLI integration
- Intelligent multi-format routing (Folders, Text, Images, Tables, Structured, Hex).
"""

import sys
import os

# Ensure repository root is on Python sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.main_window import MainWindow
from app.core.shell_integration import (
    get_left_path, set_left_path, show_native_notification,
    install_context_menu, uninstall_context_menu,
    install_all, uninstall_all, export_reg_file
)


def parse_arguments(args_list=None):
    parser = argparse.ArgumentParser(
        description="diff_and_compare_tool — Next-Gen Multi-Format Diff & 3-Way Merge Studio"
    )
    parser.add_argument("files", nargs="*", help="Files or folders to compare or merge")
    parser.add_argument("--diff", "-d", nargs=2, metavar=("FILE1", "FILE2"), help="Perform 2-way file diff")
    parser.add_argument("--merge", "-m", nargs=3, metavar=("MINE", "BASE", "THEIRS"), help="Perform 3-way merge")
    parser.add_argument("--output", "-o", metavar="OUTPUT", help="Merged output path for 3-way merge")
    parser.add_argument("--folder-diff", nargs=2, metavar=("DIR1", "DIR2"), help="Compare two directories or archives")
    parser.add_argument("--image-diff", nargs=2, metavar=("IMG1", "IMG2"), help="Compare two image files")
    parser.add_argument("--table-diff", nargs=2, metavar=("CSV1", "CSV2"), help="Compare two CSV/Excel tables")
    parser.add_argument("--hex-diff", nargs=2, metavar=("BIN1", "BIN2"), help="Compare two binary files in hex mode")

    # Batch Command Line & Headless CI/CD Reporting arguments
    parser.add_argument("--report-html", metavar="HTML_PATH", help="Generate standalone HTML comparison report")
    parser.add_argument("--exit-code", action="store_true", help="Return standard exit codes (0=match, 1=mismatch, 2=error)")
    parser.add_argument("--headless", action="store_true", help="Run in headless non-GUI automated mode")
    parser.add_argument("--new-window", action="store_true", help="Open in a new window instead of existing instance")

    # Windows Explorer Shell Context Menu & Registry arguments
    parser.add_argument("--select-left", metavar="PATH", help="Select file/folder as Left comparison target")
    parser.add_argument("--select-right", metavar="PATH", help="Select file/folder as Right and launch comparison")
    parser.add_argument("--compare", nargs="+", metavar="PATH", help="Compare selected file(s) or folder(s)")
    parser.add_argument("--install-shell", action="store_true", help="Install Windows Explorer context menu")
    parser.add_argument("--uninstall-shell", action="store_true", help="Uninstall Windows Explorer context menu")
    parser.add_argument("--install-all", action="store_true", help="Register Explorer context menu, App Paths, and Windows Uninstall entry")
    parser.add_argument("--uninstall-all", action="store_true", help="Unregister Explorer context menu, App Paths, and Windows Uninstall entry")
    parser.add_argument("--export-reg", metavar="FILE", help="Export complete Windows Registry (.reg) file for this installation")

    return parser.parse_known_args(args_list)


def main():
    args, _ = parse_arguments()

    # Fast non-GUI actions: install / uninstall / export registry
    if args.install_all:
        ok, msg = install_all()
        print(msg)
        return
    if args.uninstall_all:
        ok, msg = uninstall_all()
        print(msg)
        return
    if args.export_reg:
        ok, msg = export_reg_file(args.export_reg)
        print(msg)
        return
    if args.install_shell:
        ok, msg = install_context_menu()
        print(msg)
        return
    if args.uninstall_shell:
        ok, msg = uninstall_context_menu()
        print(msg)
        return

    # Headless CI/CD Automated Execution
    if args.report_html or args.exit_code or args.headless:
        from app.core.headless_reporter import HeadlessReporter
        exit_code = 0
        summary = ""

        if args.folder_diff:
            exit_code, summary = HeadlessReporter.run_folder_comparison(
                args.folder_diff[0], args.folder_diff[1], report_html_path=args.report_html
            )
        elif args.diff:
            from app.core.stream_diff import resolve_stream_input
            p1, _ = resolve_stream_input(args.diff[0], args.diff[1])
            p2, _ = resolve_stream_input(args.diff[1], args.diff[0])
            exit_code, summary = HeadlessReporter.run_file_comparison(
                p1, p2, report_html_path=args.report_html
            )
        elif len(args.files) == 2:
            p1_raw, p2_raw = args.files[0], args.files[1]
            if os.path.isdir(p1_raw) and os.path.isdir(p2_raw):
                exit_code, summary = HeadlessReporter.run_folder_comparison(
                    p1_raw, p2_raw, report_html_path=args.report_html
                )
            else:
                from app.core.stream_diff import resolve_stream_input
                p1, _ = resolve_stream_input(p1_raw, p2_raw)
                p2, _ = resolve_stream_input(p2_raw, p1_raw)
                exit_code, summary = HeadlessReporter.run_file_comparison(
                    p1, p2, report_html_path=args.report_html
                )
        else:
            print("Error: In headless mode, specify two files or folders using --folder-diff, --diff, or positional arguments.")
            sys.exit(2)

        print(summary)
        if args.report_html:
            print(f"Report generated at: {os.path.abspath(args.report_html)}")
        sys.exit(exit_code)

    # Handle --select-left (quietly caches path and shows friendly notification)
    if args.select_left:
        target = os.path.abspath(args.select_left)
        set_left_path(target)
        show_native_notification(
            "diff_and_compare_tool",
            f"✓ Selected as Left:\n{target}\n\nNow right-click on the second file/folder in Windows Explorer and choose 'Select Right'."
        )
        return

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    # Set explicit Windows AppUserModelID so taskbar groups properly with custom icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("diff_and_compare_tool.Studio.2.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("diff_and_compare_tool")
    app.setOrganizationName("diff_and_compare_tool")

    # Native Windows modern font stack
    app_font = QFont("Segoe UI", 10)
    app.setFont(app_font)

    # Set official application icon
    from app.ui.styles.icons import get_app_icon
    app_icon = get_app_icon()
    app.setWindowIcon(app_icon)

    # Single-Instance IPC Check: forward arguments to running instance if one exists
    from app.core.ipc_manager import SingleInstanceManager
    if SingleInstanceManager.try_send_to_existing_instance(sys.argv[1:]):
        sys.exit(0)

    window = MainWindow()
    window.setWindowIcon(app_icon)

    # Start IPC server to receive commands from subsequent instances
    ipc_manager = SingleInstanceManager(window)
    ipc_manager.start_server(lambda payload: window.handle_remote_args(payload.get("args", []), payload.get("cwd", "")))
    app.aboutToQuit.connect(ipc_manager.cleanup)

    # Handle --select-right
    if args.select_right:
        right_target = os.path.abspath(args.select_right)
        left_target = get_left_path()
        if left_target and os.path.exists(left_target):
            window.smart_open_comparison(left_target, right_target)
        else:
            set_left_path(right_target)
            show_native_notification(
                "diff_and_compare_tool",
                f"Left side was not set yet.\n\nSaved '{os.path.basename(right_target)}' as Left.\nPlease right-click the second item and choose 'Select Right'."
            )
            return

    # Handle --compare
    elif args.compare:
        if len(args.compare) >= 2:
            window.smart_open_comparison(args.compare[0], args.compare[1])
        elif len(args.compare) == 1:
            left_target = get_left_path()
            item = os.path.abspath(args.compare[0])
            if left_target and os.path.exists(left_target) and os.path.abspath(left_target) != item:
                window.smart_open_comparison(left_target, item)
            else:
                set_left_path(item)
                show_native_notification(
                    "diff_and_compare_tool",
                    f"Selected as Left:\n{item}\n\nSelect a second file/folder and click 'Select Right' or 'Select files to compare'."
                )
                return

    elif args.folder_diff:
        window.open_folder_diff(args.folder_diff[0], args.folder_diff[1])
    elif args.diff:
        from app.core.stream_diff import resolve_stream_input
        p1, t1 = resolve_stream_input(args.diff[0], args.diff[1])
        p2, t2 = resolve_stream_input(args.diff[1], args.diff[0])
        window.open_file_diff(p1, p2, left_title=t1, right_title=t2)
    elif args.merge:
        window.open_3way_merge(args.merge[0], args.merge[1], args.merge[2], args.output)
    elif args.image_diff:
        window.open_image_diff(args.image_diff[0], args.image_diff[1])
    elif args.table_diff:
        window.open_table_diff(args.table_diff[0], args.table_diff[1])
    elif args.hex_diff:
        window.open_hex_diff(args.hex_diff[0], args.hex_diff[1])
    elif len(args.files) == 2:
        from app.core.stream_diff import resolve_stream_input
        p1, t1 = resolve_stream_input(args.files[0], args.files[1])
        p2, t2 = resolve_stream_input(args.files[1], args.files[0])
        window.smart_open_comparison(p1, p2, left_title=t1, right_title=t2)
    elif len(args.files) == 3:
        window.open_3way_merge(args.files[0], args.files[1], args.files[2], args.output)
    else:
        # Default: Show Home / Welcome screen!
        window.tabs.setCurrentWidget(window.home_tab)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

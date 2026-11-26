"""Package test initialization with deterministic Qt application exit cleanup."""

import atexit
import gc


def _cleanup_qt_on_exit() -> None:
    """Release QApplication deterministically before Py_FinalizeEx to prevent PySide6 shutdown crashes."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            QApplication.sendPostedEvents()
            QApplication.processEvents()
            gc.collect()
            QApplication.sendPostedEvents()
            QApplication.processEvents()
            import shiboken6
            shiboken6.delete(app)
    except Exception:
        pass


atexit.register(_cleanup_qt_on_exit)

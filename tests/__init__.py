"""Package test initialization with deterministic cross-platform Qt exit cleanup."""

import atexit
import gc
import sys


def _cleanup_qt_on_exit() -> None:
    """Cleanly dispose Qt top-level widgets and pixmap caches before Python finalization."""
    try:
        from PySide6.QtGui import QPixmapCache
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return

        for w in list(app.topLevelWidgets()):
            try:
                w.close()
                w.deleteLater()
            except Exception:
                pass

        QApplication.sendPostedEvents(None, 0)
        QApplication.processEvents()
        QPixmapCache.clear()
        gc.collect()
        QApplication.sendPostedEvents(None, 0)
        QApplication.processEvents()
        app.quit()

        # On Windows CI under PySide6 6.11 offscreen, explicitly deleting QApplication
        # before Py_FinalizeEx avoids an exit-code-1 teardown race; on Linux offscreen,
        # deleting QApplication here triggers a pure-virtual abort in libqoffscreen.
        if sys.platform == "win32":
            import shiboken6
            shiboken6.delete(app)
    except Exception:
        pass


atexit.register(_cleanup_qt_on_exit)

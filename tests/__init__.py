"""Package test initialization with deterministic cross-platform Qt exit cleanup."""

import atexit
import gc
import sys


def _cleanup_qt_on_exit() -> None:
    """Cleanly dispose Qt widgets/app on Windows CI before Python finalization."""
    if sys.platform != "win32":
        return

    try:
        from PySide6.QtGui import QPixmapCache
        from PySide6.QtWidgets import QApplication
        import shiboken6

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
        shiboken6.delete(app)
    except Exception:
        pass


atexit.register(_cleanup_qt_on_exit)

"""Package test initialization with deterministic cross-platform Qt exit cleanup."""

import atexit
import gc
import sys

_QT_APP = None


def ensure_qapp():
    """Creates or returns the singleton QApplication while retaining a Python reference."""
    global _QT_APP
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    _QT_APP = app
    return app


def cleanup_qt_widgets() -> None:
    """Closes and deletes any surviving top-level Qt widgets and flushes deferred deletions."""
    try:
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
        gc.collect()
        QApplication.sendPostedEvents(None, 0)
        QApplication.processEvents()
    except Exception:
        pass


def _cleanup_qt_on_exit() -> None:
    """Dispose Qt widgets cleanly and handle Windows CI offscreen exit teardown."""
    cleanup_qt_widgets()
    if sys.platform != "win32":
        return

    try:
        from PySide6.QtGui import QPixmapCache
        from PySide6.QtWidgets import QApplication
        import shiboken6

        app = QApplication.instance()
        if app is None:
            return
        QPixmapCache.clear()
        app.quit()
        shiboken6.delete(app)
    except Exception:
        pass


atexit.register(_cleanup_qt_on_exit)

"""Background workers for update checking and downloading (QThread based)."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from pygiffer import updater
from pygiffer.updater import ReleaseInfo


class UpdateCheckWorker(QThread):
    """Queries the latest release without blocking the UI thread."""

    up_to_date = pyqtSignal(str)          # current version
    update_available = pyqtSignal(object)  # ReleaseInfo
    failed = pyqtSignal(str)               # error message

    def run(self) -> None:
        try:
            info = updater.fetch_latest_release()
        except Exception as exc:  # network / parse errors
            self.failed.emit(str(exc))
            return
        if info.is_update:
            self.update_available.emit(info)
        else:
            from pygiffer.version import __version__

            self.up_to_date.emit(__version__)


class UpdateDownloadWorker(QThread):
    """Downloads (with cache/resume) + extracts the release, then prepares the swap."""

    progress = pyqtSignal(int, int)   # downloaded, total
    status = pyqtSignal(str)          # human-readable phase
    ready = pyqtSignal(object)        # UpdatePlan
    failed = pyqtSignal(str)

    def __init__(self, info: ReleaseInfo, parent=None):
        super().__init__(parent)
        self._info = info

    def run(self) -> None:
        try:
            self.status.emit("正在获取更新信息…")
            manifest = updater.fetch_manifest(self._info)
            plan = updater.prepare_update(self._info, manifest, progress=self._emit_progress)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.ready.emit(plan)

    def _emit_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)

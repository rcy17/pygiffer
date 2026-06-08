from __future__ import annotations

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from pygiffer.paths import cli_command


class CliProcessRunner(QObject):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        self._proc.finished.connect(self._on_finished)
        self._output_path = ""

    def start(self, cli_args: list[str], output_path: str) -> None:
        self._output_path = output_path
        program, args = cli_command(*cli_args)
        self._proc.start(program, args)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code == 0:
            self.finished_ok.emit(self._output_path)
            return
        err = bytes(self._proc.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if not err:
            err = f"CLI exited with code {exit_code}"
        self.finished_err.emit(err)

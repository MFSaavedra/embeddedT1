"""Background serial I/O so the GUI thread never blocks (spec 7: "usar threading").

SerialWorker owns the pyserial port. Its read loop runs in a QThread and talks to the GUI
only through Qt signals (thread-safe, delivered on the GUI thread). Writes are serialised
with a lock so any widget may call send() directly from the GUI thread.
"""
from __future__ import annotations

import threading
from typing import List, Optional

import serial
from PyQt5.QtCore import QThread, pyqtSignal
from serial.tools import list_ports

import protocol


def available_ports() -> List[str]:
    """Device names of the serial ports currently present (/dev/ttyUSB0, COM3, ...)."""
    return sorted(p.device for p in list_ports.comports())


class SerialWorker(QThread):
    frame_received = pyqtSignal(list)   # fields of a valid frame, e.g. ["ENV", "23.4", "31"]
    bad_line = pyqtSignal(str)          # a line that failed protocol.parse_frame()
    connected = pyqtSignal(str, int)    # port, baud
    disconnected = pyqtSignal()
    error = pyqtSignal(str)             # human-readable message for the status bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser: Optional[serial.Serial] = None
        self._write_lock = threading.Lock()
        self._stop = threading.Event()

    # ------------------------------------------------------------ GUI-thread API

    def open(self, port: str, baud: int) -> bool:
        """Open the port and start the read loop. Emits connected() or error()."""
        if self.isRunning():
            return False
        try:
            # Opening the port toggles DTR/RTS, which resets most ESP32 dev boards. The
            # first second of data is bootloader output; parse_frame() rejects it.
            self._ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        except (serial.SerialException, OSError, ValueError) as exc:
            self.error.emit(f"No se pudo abrir {port}: {exc}")
            return False
        self._stop.clear()
        self.start()
        self.connected.emit(port, baud)
        return True

    def close(self) -> None:
        """Stop the read loop and close the port (safe to call when not connected)."""
        self._stop.set()
        if self.isRunning():
            self.wait(2000)
        self._close_port()

    def send(self, payload: str) -> bool:
        """Frame and transmit a command payload such as "CFG,X,1,4,100"."""
        ser = self._ser
        if ser is None or not ser.is_open:
            self.error.emit("No conectado")
            return False
        try:
            with self._write_lock:
                ser.write(protocol.build_frame(payload))
        except (serial.SerialException, OSError) as exc:
            self.error.emit(f"Error al enviar: {exc}")
            return False
        return True

    # --------------------------------------------------------------- thread body

    def run(self) -> None:
        ser = self._ser
        try:
            while not self._stop.is_set():
                try:
                    raw = ser.readline()            # b"" on timeout
                except (serial.SerialException, OSError) as exc:
                    # Typical cause: the cable was unplugged. TODO(PY1): reconnect policy.
                    self.error.emit(f"Conexión perdida: {exc}")
                    break
                if not raw:
                    continue
                line = raw.decode("ascii", errors="replace")
                fields = protocol.parse_frame(line)
                if fields is None:
                    self.bad_line.emit(line.rstrip())
                else:
                    self.frame_received.emit(fields)
        finally:
            self._close_port()
            self.disconnected.emit()

    def _close_port(self) -> None:
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:   # noqa: BLE001 - closing a dead port must never raise
                pass

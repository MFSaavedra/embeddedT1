"""@file serial_worker.py
@brief Background serial I/O so the GUI thread never blocks (spec 7: "usar threading").

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
    """@brief Device names of the serial ports currently present.

    @return Sorted list such as ["/dev/ttyUSB0"] or ["COM3", "COM4"]; empty if none.
    """
    return sorted(p.device for p in list_ports.comports())


class SerialWorker(QThread):
    """@brief Owns the serial port and runs the read loop in its own thread.

    Lifecycle: open() starts run() in the background, which emits frame_received / bad_line
    for every line until close() is called or the port fails. send() may be called from
    any thread while the port is open.
    """

    ## Fields of a valid frame, e.g. ["ENV", "23.4", "31"] (see protocol.parse_frame()).
    frame_received = pyqtSignal(list)
    ## A received line that failed protocol.parse_frame(), CR/LF stripped.
    bad_line = pyqtSignal(str)
    ## Emitted once the port is open: (port, baud).
    connected = pyqtSignal(str, int)
    ## Emitted when the read loop ends, whether by close() or by an I/O error.
    disconnected = pyqtSignal()
    ## Human-readable message for the status bar.
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        """@brief Create the worker without opening any port.

        @param parent  Optional QObject parent.
        """
        super().__init__(parent)
        ## Open pyserial port, or None while disconnected.
        self._ser: Optional[serial.Serial] = None
        ## Serialises send() calls coming from different threads.
        self._write_lock = threading.Lock()
        ## Set by close() so run() exits at the next read timeout.
        self._stop = threading.Event()

    # ------------------------------------------------------------ GUI-thread API

    def open(self, port: str, baud: int) -> bool:
        """@brief Open the port and start the read loop.

        Opening the port toggles DTR/RTS, which resets most ESP32 dev boards; the first
        second of data is bootloader output, which parse_frame() rejects.

        @param port  Device name, e.g. "/dev/ttyUSB0" or "COM3".
        @param baud  Baud rate; must match LINK_BAUD in the firmware.
        @return True if the port was opened (connected is emitted); False if the worker is
                already running or the port could not be opened (error is emitted).
        """
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
        """@brief Stop the read loop and close the port.

        Blocks up to 2 s for the thread to finish. Safe to call when not connected.
        """
        self._stop.set()
        if self.isRunning():
            self.wait(2000)
        self._close_port()

    def send(self, payload: str) -> bool:
        """@brief Frame and transmit a command payload.

        @param payload  Payload text such as "CFG,X,1,4,100" (see protocol.py).
        @return True if the frame was written; False if not connected or the write failed
                (error is emitted in both cases).
        """
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
        """@brief Thread body: read lines until stopped or the port fails.

        Every line is passed through protocol.parse_frame(): valid frames are emitted as
        frame_received, everything else as bad_line. On an I/O error (typically an
        unplugged cable) error is emitted and the loop ends. The port is always closed and
        disconnected emitted on exit.
        """
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
        """@brief Close and forget the port, swallowing any error from a dead device."""
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:   # noqa: BLE001 - closing a dead port must never raise
                pass

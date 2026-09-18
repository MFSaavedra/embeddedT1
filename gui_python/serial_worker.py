"""@file serial_worker.py
@brief Background serial I/O so the GUI thread never blocks (spec 7: "usar threading").

SerialWorker owns the pyserial port. Its read loop runs in a QThread and talks to the GUI
only through Qt signals (thread-safe, delivered on the GUI thread). Writes are serialised
with a lock so any widget may call send() directly from the GUI thread.
"""
from __future__ import annotations

import threading
import time
from typing import List, Optional

import serial
from PyQt5.QtCore import QThread, pyqtSignal
from serial.tools import list_ports

import protocol

## Seconds EN is held low when resetting the board after opening the port.
RESET_PULSE_S = 0.1
## Seconds given to the board after the reset pulse to reach app_main() before `connected`
## is emitted. Boot takes ~0.3 s including the ROM/bootloader logs; 1 s leaves margin.
BOOT_WAIT_S = 1.0


def available_ports() -> List[str]:
    """@brief Device names of the serial ports currently present.

    @return Sorted list such as ["/dev/ttyUSB0"] or ["COM3", "COM4"]; empty if none.
    """
    return sorted(p.device for p in list_ports.comports())


class SerialWorker(QThread):
    """@brief Owns the serial port and runs the read loop in its own thread.

    Lifecycle: open() starts run() in the background, which first resets the board (see
    _reset_board()), waits BOOT_WAIT_S for it to boot and emits connected, then emits
    frame_received / bad_line for every line until close() is called or the port fails.
    send() may be called from any thread while the port is open.
    """

    ## Fields of a valid frame, e.g. ["ENV", "23.4", "31"] (see protocol.parse_frame()).
    frame_received = pyqtSignal(list)
    ## A received line that failed protocol.parse_frame(), CR/LF stripped.
    bad_line = pyqtSignal(str)
    ## Emitted once the port is open and the board has been reset and given BOOT_WAIT_S to
    ## boot, i.e. when it is ready to receive commands: (port, baud).
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

        Returns as soon as the port is open; the board reset and boot wait happen in run(),
        so connected arrives roughly BOOT_WAIT_S later via the signal, not before this
        returns.

        @param port  Device name, e.g. "/dev/ttyUSB0" or "COM3".
        @param baud  Baud rate; must match LINK_BAUD in the firmware.
        @return True if the port was opened (connected will be emitted); False if the
                worker is already running or the port could not be opened (error is
                emitted).
        """
        if self.isRunning():
            return False
        try:
            self._ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        except (serial.SerialException, OSError, ValueError) as exc:
            self.error.emit(f"No se pudo abrir {port}: {exc}")
            return False
        self._stop.clear()
        self.start()
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
        """@brief Thread body: reset the board, wait for it to boot, then read lines until
        stopped or the port fails.

        Every line is passed through protocol.parse_frame(): valid frames are emitted as
        frame_received, everything else as bad_line. Lines received during the boot wait
        (ROM output at 115200, bootloader and app logs) take the same path, so they show
        up in the rejected counter like any other log line. On an I/O error (typically an
        unplugged cable) error is emitted and the loop ends. The port is always closed and
        disconnected emitted on exit.
        """
        ser = self._ser
        try:
            self._reset_board(ser)
            boot_deadline = time.monotonic() + BOOT_WAIT_S
            while not self._stop.is_set() and time.monotonic() < boot_deadline:
                if not self._pump_line(ser):
                    return
            if self._stop.is_set():
                return
            self.connected.emit(ser.port, ser.baudrate)
            while not self._stop.is_set():
                if not self._pump_line(ser):
                    return
        finally:
            self._close_port()
            self.disconnected.emit()

    def _reset_board(self, ser: serial.Serial) -> None:
        """@brief Pulse EN low through the dev board's DTR/RTS auto-reset circuit.

        Same sequence as esptool's hard reset: DTR deasserted keeps IO0 high so the chip
        boots the firmware (not the ROM download mode) while RTS is asserted for
        RESET_PULSE_S to pull EN low. Merely opening the port also toggles both lines,
        but the OS drives them in an order and with a timing that leave the ESP32 hung
        most of the time on Linux with a CP2102 board (measured 1-4 usable connects out
        of 10); an explicit pulse boots it every time. Both lines are left deasserted (EN
        and IO0 high). A port without modem lines is reported but not fatal: the user can
        still press the EN button.

        @param ser  The open port.
        """
        try:
            ser.dtr = False
            ser.rts = True
            time.sleep(RESET_PULSE_S)
            ser.rts = False
        except (serial.SerialException, OSError) as exc:
            self.error.emit(f"No se pudo reiniciar el ESP32 (pulsa EN en la placa): {exc}")

    def _pump_line(self, ser: serial.Serial) -> bool:
        """@brief Read one line (or time out) and emit frame_received / bad_line for it.

        @param ser  The open port.
        @return False if the port failed (error has been emitted), True otherwise.
        """
        try:
            raw = ser.readline()            # b"" on timeout
        except (serial.SerialException, OSError) as exc:
            # Typical cause: the cable was unplugged. TODO(PY1): reconnect policy.
            self.error.emit(f"Conexión perdida: {exc}")
            return False
        if raw:
            line = raw.decode("ascii", errors="replace")
            fields = protocol.parse_frame(line)
            if fields is None:
                self.bad_line.emit(line.rstrip())
            else:
                self.frame_received.emit(fields)
        return True

    def _close_port(self) -> None:
        """@brief Close and forget the port, swallowing any error from a dead device."""
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:   # noqa: BLE001 - closing a dead port must never raise
                pass

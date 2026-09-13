"""Frame layer for the ESP32 <-> PC serial link.

Frame format (ASCII, one frame per line), identical to esp32_firmware/main/protocol.c:

    $<payload>*<XX>\\n

payload : comma-separated fields; the first one is the message type ("ACC", "ENV", ...)
XX      : two upper-case hex digits = XOR of every payload byte (between '$' and '*')

Only framing and checksums live here. Message types and their fields are documented in
README.md ("Protocol") and interpreted in main_window.py. Keep this file and protocol.c
in sync.
"""
from __future__ import annotations

from typing import List, Optional

# Draft message types - finalise in README "Protocol" together with the firmware.
MSG_ACC = "ACC"    # ESP32 -> PC : accelerometer samples
MSG_ENV = "ENV"    # ESP32 -> PC : temperature / humidity reading
MSG_ACK = "ACK"    # ESP32 -> PC : command accepted
MSG_ERR = "ERR"    # ESP32 -> PC : command rejected or bad frame
CMD_CFG = "CFG"    # PC -> ESP32 : per-axis waveform / amplitude / sample rate
CMD_ENV = "ENV"    # PC -> ESP32 : environmental sensor period
CMD_INIT = "INIT"  # PC -> ESP32 : reset to defaults and (re)start streaming


def checksum(payload: str) -> int:
    """XOR of every payload byte."""
    cs = 0
    for b in payload.encode("ascii"):
        cs ^= b
    return cs


def build_frame(payload: str) -> bytes:
    """Wrap a payload as b"$payload*XX\\n", ready for serial.write()."""
    return f"${payload}*{checksum(payload):02X}\n".encode("ascii")


def parse_frame(line: str) -> Optional[List[str]]:
    """Validate one received line and split its payload into fields.

    Returns None for anything that is not a well-formed frame with a correct checksum
    (bootloader output, ESP_LOG lines, corrupted bytes) so callers can count and skip it.
    """
    line = line.strip()
    if len(line) < 5 or line[0] != "$" or line[-3] != "*":
        return None
    payload, hex_cs = line[1:-3], line[-2:]
    if not payload:
        return None
    try:
        expected = int(hex_cs, 16)
        actual = checksum(payload)
    except (ValueError, UnicodeEncodeError):
        return None
    if actual != expected:
        return None
    return payload.split(",")

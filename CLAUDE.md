# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Tarea 1 for CC5328 (Sistemas Embebidos y Sensores, U. de Chile): an ESP32 emulates a
tri-axial accelerometer + temperature/humidity sensor and streams them over UART0 to a
PyQt5 desktop app that plots them and reconfigures the firmware live. Two independent
codebases share one text protocol. `README.md` is the authoritative (Spanish) spec of the
protocol, design decisions and troubleshooting; `TODO.md` tracks grading criteria, the
remaining work (`PY1`, `PY5` items) and resolved open questions. README and GUI strings
are in Spanish (course deliverable); code comments, Doxygen text and `TODO.md` are in English.

## Commands

### Firmware (`esp32_firmware/`, ESP-IDF v6.1, target `esp32`)

`idf.py` is **not** on PATH; activate first in every shell:

```bash
. ~/.espressif/tools/activate_idf_v6.1.sh
cd esp32_firmware
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor      # Ctrl+] exits the monitor
rm sdkconfig && idf.py reconfigure        # after any change to sdkconfig.defaults
```

- `sdkconfig` is generated and git-ignored; permanent config goes in `sdkconfig.defaults`.
- The monitor and the GUI cannot share `/dev/ttyUSB0`; close one before opening the other.
- There is no on-device or host-side test harness for the C code. `accel_sim_eval()` is a
  pure function deliberately kept host-testable, but no such test exists yet.

### GUI (`gui_python/`, Python 3.8+, PyQt5 + pyserial + pyqtgraph + numpy)

The venv lives at the repo root (`.venv/`, git-ignored, already populated on this machine):

```bash
source .venv/bin/activate                 # or prefix commands with .venv/bin/
pip install -r gui_python/requirements.txt
python gui_python/main.py                 # run from repo root
pytest gui_python/tests                   # protocol, SerialWorker (fake port), MainWindow (offscreen Qt)
pytest gui_python/tests/test_protocol.py::test_round_trip   # single test
```

`gui_python/tests/conftest.py` prepends `gui_python/` to `sys.path`, so tests import
modules exactly as the app does (`import protocol`, not `gui_python.protocol`), and forces
Qt's offscreen platform so widget tests need no display. Widget tests take the `qapp`
fixture and drive slots directly (`test_main_window.py`); there is no event loop.
`test_serial_worker.py` is the template for testing `SerialWorker` without hardware or a
Qt event loop: monkeypatch `serial.Serial` with a fake port and connect the signals with
`Qt.DirectConnection` so they fire synchronously on the worker thread.

### Docs

`doxygen` from the repo root → `docs/doxygen/html/index.html` (git-ignored; `doxygen` is
not installed on this machine). All C and Python code carries Doxygen-style comments
(`@file`, `@brief`, `@param`, `@return`); Python docstrings use the same `@` tags, and
`##` line comments document attributes/constants. Keep new code in that style.

Outstanding work items are marked in code as `TODO(<id>)` matching `TODO.md`:
`grep -rn "TODO(" esp32_firmware/main gui_python`.

## Architecture

### The protocol is implemented twice and must stay identical

`esp32_firmware/main/protocol.[ch]` and `gui_python/protocol.py` are mirrors: frame
`$<payload>*<XX>\n`, `XX` = XOR of payload bytes as two hex digits. `test_protocol.py`'s
expected bytes double as the reference for the C side. Message types/fields are *not* in
the protocol layer — they live in `README.md` "Protocolo" and are interpreted in
`commands.c` (PC→ESP32: `CFG`, `ENV`, `INIT`, `BAUD`) and `main_window.py::_on_frame`
(ESP32→PC: `ACC`, `ENV`, `ACK`, `ERR`). Changing a message means touching README + both
interpreters.
Note `ENV` is both a command (PC→ESP32, period) and a data message (ESP32→PC, reading);
only the direction tells them apart (`CMD_ENV == MSG_ENV` in `protocol.py`).

Paired constants that must be changed together:
- `LINK_BAUD` (`app_config.h`) ↔ `DEFAULT_BAUD` (`widgets/connection_panel.py`) ↔
  `CONFIG_ESP_CONSOLE_UART_BAUDRATE` (`sdkconfig.defaults`). All are 921600. This is the
  *boot* speed, which the GUI must open the port at; the selector only renegotiates once
  connected (see below).
- `BAUD_RATES` (`widgets/connection_panel.py`) ↔ `uart_link_valid_baud()` (`uart_link.c`):
  the rates a `$BAUD` command may switch to.
- `ACCEL_DEFAULT_*` / `ENV_DEFAULT_PERIOD_S` (`app_config.h`) ↔ `DEFAULT_*` in
  `widgets/config_panel.py`.

### Firmware data flow (`esp32_firmware/main/`)

```
esp_timer 1 kHz ──on_tick()──▶ FreeRTOS queue ──stream_task()──▶ flush_axis() ──▶ uart_link_send_frame()
   (accel_sim.c)   per-axis decimation        batch ~15 ms/axis   "ACC,<axis>,<t0_ms>,<fs>,v1..vN"

uart_rx task (uart_link.c) ──line──▶ commands_handle_line() ──▶ proto_parse → handle_cfg/env/init ──▶ ACK/ERR
```

- One master tick; each axis samples every `1000/fs` ticks. Time is the global tick, so
  waveform phase is continuous across live `fs` changes.
- `on_tick()` runs in the esp_timer task, not an ISR, but must never block: queue send
  with 0 timeout, drops counted in `s_dropped` and reported once/second from `stream_task`.
- Per-axis config (`s_cfg`) is touched only via `accel_sim_set_axis/get_axis` (critical
  section) because three contexts access it: timer task, stream task, UART RX task.
- Streaming does **not** start at boot. `app_main` only wires modules; `handle_init()`
  (on `$INIT`) resets defaults, sends `ACK,INIT,<FW_VERSION>` *before* data, then starts
  both simulators. `env_sim` is stopped/restarted on INIT so it emits a fresh reading.
- UART0 carries both data frames and `ESP_LOG` output. `uart_vfs_dev_use_driver()` routes
  stdout through the driver so log lines are never spliced into a frame; they arrive as
  whole lines without `$` and the GUI discards/counts them. Never `printf` a `$`-prefixed
  string outside `uart_link_send_frame()`.
- Command validation: `parse_field()` in `commands.c` does strict integer parsing with
  range bounds *before* the narrowing casts; `accel_sim_set_axis` validates the allowed
  sets (func 1..3, amp 4/8/16, fs 50/100/200/500/1000). `BADARG` covers wrong field
  count, bad axis letter and out-of-set values; `BADFRAME` is only for framing/checksum
  failures in `commands_handle_line`.

### GUI data flow (`gui_python/`)

```
widgets (Qt signals) ──▶ MainWindow._send_*() ──▶ SerialWorker.send(payload)
SerialWorker(QThread).run() readline ──▶ frame_received / bad_line signals ──▶ MainWindow._on_frame ──▶ AccelPlots.push / EnvPanel
```

- `serial_worker.py` is the only module that imports pyserial; `main_window.py` is the
  only module that knows both widgets and the worker; widgets never see the port. Keep
  those boundaries.
- All serial I/O is on the `QThread`; results reach the GUI thread only through signals.
  `send()` is callable from any thread (write lock). No exception may escape `run()`.
- `run()` starts by pulsing EN (esptool-style: DTR off, RTS on 100 ms, RTS off) and reading
  for `BOOT_WAIT_S` before emitting `connected`; `open()` never emits it. A plain port open
  leaves the ESP32 hung most of the time on Linux/CP2102 (measured 1-4/10 usable connects,
  same with older firmware), the pulse gives 10/10. Do not remove or move it to `open()`.
- `AccelPlots`: per-axis numpy ring buffers; `push()` only appends; a single 33 ms
  `QTimer` redraws all curves. Never redraw per frame/sample. Titles show the *measured*
  samples/s, which doubles as the link-saturation indicator.
- Baud renegotiation is ordered, not simultaneous: `$BAUD` → firmware stops streaming,
  ACKs *at the old rate*, drains TX, switches → GUI switches on that ACK (deferred to the
  read loop by `SerialWorker.request_baud`, never from the GUI thread) → GUI sends `$INIT`,
  which confirms the rate and restarts streaming. Both ends auto-revert if the other goes
  silent (`LINK_BAUD_REVERT_MS` 5 s < `BAUD_NEGOTIATION_MS` 8 s — keep that order). The
  state machine lives in `main_window.py` "baud renegotiation"; `serial_worker.py` still
  knows no message types. `_on_disconnected` puts the selector back to `DEFAULT_BAUD`: the
  board reboots into `LINK_BAUD`, so reconnecting at a negotiated rate gives a connection
  that looks fine and receives nothing.
- `MainWindow` resets the config panel/plots on receipt of `$ACK,INIT`, not when INIT is
  sent. The "tramas OK / rechazadas" counters are kept mutually exclusive: a frame with a
  valid checksum but unparsable fields is moved from OK to rejected.

### Bandwidth is the central constraint

3 axes × 1000 Hz with `%.3f` text values needs ~284 kbaud, which is why the link is fixed
at 921600 and samples are batched per axis every `ACCEL_BATCH_MS` (max `ACCEL_BATCH_MAX`
per frame, frame ≤ `LINK_MAX_FRAME` = 512 B). Any change to the ACC value format, batch
size or baud rate must be re-checked against the table in README "Decisiones de diseño".

## Conventions

- Firmware module layout: `<module>.h` has the public API with full Doxygen; `<module>.c`
  keeps module state in `static` variables prefixed `s_` and static helpers documented
  inline. New source files must be added to `esp32_firmware/main/CMakeLists.txt` `SRCS`,
  and any new ESP-IDF component (e.g. `nvs_flash`) to `PRIV_REQUIRES` there: the project
  sets `MINIMAL_BUILD ON`, so a component that is not listed is not compiled at all.
- Signal-flow comments (`panels ──▶ MainWindow ──▶ worker`) at the top of Python modules
  describe the real wiring; update them when wiring changes.
- Widget wiring in `MainWindow.__init__` is wrapped in `# @cond` / `# @endcond` so Doxygen
  does not misread bound-method connects as attributes.
- Commit messages are plain (no Co-Authored-By / session trailers).

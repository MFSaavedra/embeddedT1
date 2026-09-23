# TODO — Tarea 1 CC5328 (ESP32 ↔ PyQt serial DAQ)

**Deadline: Monday 21 September 2026, 23:59** (Git repo link or ZIP).
Grading: code review 40 % + **live demo 60 %**, scale 1.0–7.0 (base 1.0 + 6.0 across the
criteria below). Build for the demo, not just the checklist.

Item IDs (`P1`, `FW2`, `PY4`, …) match the `TODO(...)` comments in the code —
`grep -rn "TODO(" esp32_firmware gui_python` lists exactly what is left.

---

## 0. Setup (done ✅ / to do ☐)

- [x] Repo skeleton: `esp32_firmware/`, `gui_python/`, `README.md`, `docs/`
- [x] Firmware compiles with ESP-IDF v6.1 (`idf.py build`) — plumbing only, sensors stubbed
- [x] GUI launches (`python gui_python/main.py`), protocol tests pass (`pytest gui_python/tests`)
- [x] Everyone can build + flash: `. ~/.espressif/tools/activate_idf_v6.1.sh`, `idf.py -p /dev/ttyUSB0 flash monitor`
- [x] Everyone is in the `dialout` group (Linux) and has the venv: `python3 -m venv .venv && pip install -r gui_python/requirements.txt`
- [x] First commit + push (`git add -A && git commit`), agree on branches/PRs

## 1. Protocol (do this first — both sides depend on it, and it is worth 0.6 on its own) ✅

- [x] **P1** Finalise the DRAFT in README "Protocolo": message types, fields, units, error
      codes, what `$INIT` does, whether streaming starts at boot or on `$INIT`
- [x] **P1** Decide the **bandwidth budget** (see *Design decisions*): samples per `$ACC`
      frame, number format, baud rate. Update `LINK_BAUD` (`app_config.h`) and
      `DEFAULT_BAUD` (`connection_panel.py`) together — default kept at 115200 per the
      PDF's example; README documents that ≥460800 is required for 3 × 1000 Hz
- [x] **P1** Keep `protocol.c` ↔ `protocol.py` identical (framing + XOR checksum already match)

## 2. Firmware — `esp32_firmware/main/` (1.8 pts + half of UART 1.2 pts)

- [x] **FW1** Waveforms in `accel_sim_eval()` — `a1 = A·sin(2πft)`, `a2 = A·cos(2πf₁t)·sin(2πf₂t)`,
      `a3 = (2A/2)·[sin(2πft)+cos(4πft)]` — implemented **literally** as printed (peak `2A`),
      documented in README "Decisiones de diseño"  *(0.5 pts)*
- [x] **FW2** Per-axis decimation of the 1 kHz master tick in `on_tick()` → push
      `accel_sample_t` to the queue; global `t = tick/1000` keeps phase continuous  *(fs 0.5 pts)*
- [x] **FW3** `stream_task()`: batch queued samples into `$ACC` frames per axis every
      ~10–20 ms (`ACCEL_BATCH_MS`/`ACCEL_BATCH_MAX` in `app_config.h`); overflow handling is
      delegated to `uart_link_send_frame()`, which already logs + drops oversized frames
- [x] **FW4** `env_sim_read()`: T ∈ [15.0, 30.0] °C step 0.1, H ∈ [20, 40] % step 1 via
      `esp_random()`; send `$ENV` in `on_period()`; sends one reading right after start so the
      GUI is not empty for 30–60 s  *(0.4 pts)*
- [x] **FW5** `commands.c`: `CFG` / `ENV` / `INIT` handlers implemented with validation →
      `ACK`/`ERR`; amplitude and fs apply immediately via `accel_sim_set_axis` (validates
      4/8/16 and 50/100/200/500/1000); `INIT` now starts streaming (see design decisions) and
      `main.c` no longer starts it at boot  *(amplitude 0.4 pts)*
- [x] **FW6** Link fixed at **921600** on both sides (`LINK_BAUD`, `DEFAULT_BAUD`, console and
      monitor baud in `sdkconfig.defaults`): with the implemented `$ACC` format 3 × 500 Hz
      needs 165 kbaud and 3 × 1000 Hz 284 kbaud (143 % / 247 % of 115200, 18 % / 31 % of
      921600). `on_tick()` now counts queue drops and `stream_task()` warns once per second
      if the link saturates. **After pulling: `rm esp32_firmware/sdkconfig && idf.py
      reconfigure`** (sdkconfig is generated and git-ignored). Console policy: keep
      `ESP_LOG` at INFO (log lines never start with `$`); `CONFIG_LOG_DEFAULT_LEVEL_NONE=y`
      remains an option for the demo
- [x] **FW7** Runtime baud renegotiation: `$BAUD,<baud>` → `$ACK,BAUD` at the old rate,
      `uart_wait_tx_done()` + `uart_set_baudrate()` in `uart_link_set_baud()`, streaming
      stopped across the switch and restarted by the `$INIT` that confirms it. Both ends
      fall back on their own (`LINK_BAUD_REVERT_MS` = 5 s firmware, `BAUD_NEGOTIATION_MS`
      = 8 s GUI), so a rate the USB bridge cannot sustain costs a few seconds instead of a
      trip to the EN button. Makes the GUI's baud selector do something other than break
      the link; not needed for bandwidth (921600 is at 31 % worst case)
- [x] Tested each step with `idf.py monitor` before touching the GUI (FW1–FW5 confirmed
      working end to end)
- [x] `f`, `f₁`, `f₂` kept at `app_config.h` defaults: 2 / 0.5 / 5 Hz (documented in README)

## 3. Python serial layer — `gui_python/serial_worker.py`, `protocol.py` — standing by

- [ ] **PY1** Hardening: unplug mid-stream → error + clean disconnect (already emits), port
      list refresh on error, optional auto-reconnect, no exceptions ever reach the GUI thread
- [ ] Test the parser with a CLI before the GUI: `python -c` loop printing parsed frames,
      or a pytest with a captured serial log from `idf.py monitor`
- [ ] Measure: at the highest rate does `readline()` keep up? If not, read chunks and split
      on `\n` yourself

## 4. GUI — `gui_python/main_window.py`, `widgets/` (1.8 pts)

- [x] **PY2** `_on_frame()`: routes `ACC` → `plots.push(axis, t0_ms, fs, values)` and `ENV`
      → `env.update_values(temp, hum)`; `try/except (ValueError, IndexError)` + counter for
      malformed frames (kept mutually exclusive with the "ok" counter)
- [x] **PY3** Commands: `_send_axis_config` / `_send_env_period` send the payloads; panel now
      resets **on `$ACK,INIT`** instead of optimistically on send; disable controls while
      disconnected (done); show ACK/ERR in the status bar (done)  *(dynamic controls 0.6 pts)*
- [x] **PY4** `widgets/accel_plots.py`: numpy ring buffers (per-axis, wraparound-safe),
      `push()` append-only, redraw from the 30 fps `QTimer` (never per sample), x axis in
      seconds, y range = ±A (done), title with **measured samples/s** per axis (updated every
      redraw tick) so an fs change is visible  *(real-time plots 0.8 pts)*
- [ ] **PY5** — standing by (optional). `widgets/env_panel.py`: numeric indicators (done) +
      optional history plot
- [ ] Control panel polish — standing by. Port refresh button (done), remember last
      port/baud, window length selector for the plots, clear/pause buttons  *(panel 0.4 pts)*

## 5. Hardening, docs, demo (1.2 pts + most of the 60 % demo) — standing by

- [ ] Error cases to demo on purpose: wrong port, port busy (`idf.py monitor` open), cable
      unplugged while streaming, reconnect, corrupt frame (type garbage in the monitor),
      failed renegotiation (both ends revert by themselves — the GUI can no longer open the
      port at the wrong rate on purpose, since the selector renegotiates instead; a genuine
      baud mismatch now needs a firmware built with a different LINK_BAUD)
- [ ] Soak test: 10+ minutes at 3 × 1000 Hz with no dropped frames, no GUI lag, stable memory
- [ ] **DOC1** README: fill *Integrantes*, final protocol table, design decisions, screenshots
      in `docs/screenshots/`, usage examples; keep build/run commands accurate
- [ ] Code quality pass: comments, module boundaries, no dead code, consistent naming;
      `grep -rn "TODO(" .` returns nothing
- [ ] **DEMO1** Rehearse a 5-minute script: connect → init → each waveform per axis → change
      A (4/8/16) → change fs (50…1000) → env period → error cases → explain protocol
- [ ] Package: push to `github.com/MFSaavedra/embeddedT1` (or ZIP) with `esp32_firmware/`,
      `gui_python/`, `README.md`; verify a clean clone builds and runs

---

## Requirements matrix (from the PDF) → where it lives

| Spec | Requirement | Firmware | GUI |
|---|---|---|---|
| 2.1.1 | 3 waveforms, selectable per axis | `accel_sim_eval`, `axis_cfg_t.func` | `AxisConfigWidget.func_combo` |
| 2.1.1 | A = 4 g default; 8 g, 16 g live | `axis_cfg_t.amp_g` + `CFG` | `amp_combo` → `set_amplitude` |
| 2.1.1 | fs = 100 Hz default; 50/200/500/1000 live | `axis_cfg_t.fs_hz`, tick divider | `fs_combo` |
| 2.1.1 | Independent per axis (X, Y, Z) | `s_cfg[AXIS_COUNT]` | 3 × `AxisConfigWidget` |
| 2.1.2 | T 15.0–30.0 °C (0.1), H 20–40 % (1) | `env_sim_read` | `EnvPanel` |
| 2.1.2 | Env period 30 s / 60 s from GUI | `env_sim_set_period` + `ENV` | `env_combo` |
| 2.1.3 | Formatted data TX, command RX | `uart_link`, `commands` | `serial_worker` |
| 2.2.1 | Port, baud, Connect/Disconnect, Init | — | `ConnectionPanel` |
| 2.2.2 | Per-axis controls + env period | — | `ConfigPanel` |
| 2.2.3 | 3 sliding-window plots, immediate reaction | — | `AccelPlots` |
| 2.2.3 | Env numeric indicators / history | — | `EnvPanel` |
| 6.3 | Checksums | `protocol.c` | `protocol.py` |
| 7 | Threading | FreeRTOS tasks + `esp_timer` | `SerialWorker(QThread)` |

## Grading breakdown (max 7.0 = 1.0 base + 6.0)

| Area | Pts | Items |
|---|---|---|
| Firmware & simulation | 1.8 | 3 waveforms 0.5 · dynamic amplitude 0.4 · dynamic fs 0.5 · env sensor 0.4 |
| UART communication | 1.2 | protocol design 0.6 · connection stability 0.6 |
| GUI (PyQt) | 1.8 | control panel 0.4 · dynamic controls 0.6 · **real-time plots 0.8** |
| Code & docs | 1.2 | modularity/comments 0.6 · README/instructions 0.6 |

Live demo (60 %) checks: link stability, every waveform, live parameter changes, plot
correctness, GUI responsiveness, **error handling**, team presentation.

---

## Design decisions & traps the PDF does not spell out

1. **Serial bandwidth.** Worst case 3 axes × 1000 Hz = 3000 samples/s. At 115200 baud
   (≈11.5 kB/s) that is < 4 bytes per sample — a per-sample text line cannot work. A value
   like `-3.912,` is 7 bytes → 21 kB/s → needs ≥ 230400 baud even with batching; **460800 or
   921600** gives headroom (ESP32 UART0 and CP2102/CH340 bridges handle 921600). Alternatives:
   fewer decimals, integer milli-g, or binary frames. Decide in P1.
2. **Independent per-axis sample rates.** All five rates divide 1000, so one 1 kHz `esp_timer`
   with per-axis dividers (1/2/5/10/20) is the cleanest. Never write to the UART from the
   timer callback — queue → task (already wired). Using the global tick as `t` keeps the
   waveform phase-continuous when fs changes.
3. **`f`, `f₁`, `f₂` are unspecified.** Keep the highest component (2f in waveform 3) well below
   fs/2 at fs = 50 Hz; f ≈ 2 Hz gives 25 samples per cycle at the lowest rate.
4. **Waveform 3 as printed is `(2A/2)·[…]` = `A·[…]`,** whose peak is 2A (sin x + cos 2x reaches
   −2). That contradicts "amplitud máxima". Likely a typo for A/2 — ask the auxiliar
   (Lucas Llort); otherwise implement literally and document the interpretation in README.
5. **UART0 is shared with the console.** Bootloader and `ESP_LOG` output arrive on the same
   port, and pyserial opening the port toggles DTR/RTS → the board resets. The parser
   discards anything that is not a valid frame (done); `uart_vfs_dev_use_driver()` prevents
   byte-level interleaving of logs and frames (done).
6. **"Inicializar ESP32" is undefined.** Proposed: `$INIT` resets to spec defaults, replies
   `$ACK,INIT,<fw-version>` and (re)starts streaming. Document it.
7. **Make the fs change visible.** Amplitude changes are obvious; fs changes on a seconds-based
   window are subtle. Show measured samples/s per plot (also a link-health indicator) and/or
   point markers.
8. **GUI threading.** Serial reads in the `QThread` → signals → ring buffers; redraw from a
   `QTimer` at ~30 fps. pyqtgraph, not matplotlib, at these rates.

## Open questions (ask the auxiliar / decide as a team) — resolved

- [x] `a3(t)` factor: `2A/2` (= A, peak 2A) or `A/2` (peak A)? → **`2A/2`, literal**, no
      deviation from the PDF; documented in README instead of guessing at a typo
- [x] Is a baud rate other than 115200 acceptable for the demo? (PDF says "por ejemplo")
      → the PDF only gives 115200 as an example; the link is fixed at **921600** on both
      sides (see FW6) because 115200 cannot carry 3 × 500 Hz, let alone 3 × 1000 Hz
- [x] Should streaming start at boot or only after "Inicializar ESP32"? → **only after
      `$INIT`**; `main.c` no longer starts it, `handle_init()` does
- [x] Do they want per-sample timestamps in the frames, or is `t0 + i/fs` per batch enough?
      → **`t0 + i/fs` per batch**, as implemented in `stream_task()`/`accel_plots.push()`

## Environment notes (this machine, 2026-09-13)

- ESP-IDF v6.1 via Espressif installer: `. ~/.espressif/tools/activate_idf_v6.1.sh`
  (`IDF_PATH=/opt/mfsaaved/.espressif/v6.1/esp-idf`); `idf.py` is **not** on PATH otherwise
- Board enumerates at `/dev/ttyUSB0`; user is in `dialout`
- `.venv/` at repo root (git-ignored) has PyQt5 5.15.11, pyserial 3.5, pyqtgraph 0.14, numpy, pytest
- `../hello_world` is the stock ESP-IDF example the firmware layout was derived from

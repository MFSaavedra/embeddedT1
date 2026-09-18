/**
 * @file app_config.h
 * @brief Compile-time constants and spec defaults for the Tarea 1 firmware.
 *
 * Runtime-configurable values (waveform, amplitude, sample rate, env period) live in
 * their modules; only their *defaults* and the allowed ranges are defined here.
 */
#pragma once

#include "driver/uart.h"

/** Firmware version, reported in the reply to INIT (`ACK,INIT,1.0`) so the GUI can display it. */
#define FW_VERSION "1.0"

/**
 * @name Serial link
 * @{
 */
#define LINK_UART_NUM       UART_NUM_0  /**< USB-serial bridge on the dev board (shared with the console). */
#define LINK_BAUD           115200      /**< TODO(FW6): raise to 921600 if the bandwidth budget needs it. */
#define LINK_RX_BUF_SIZE    1024        /**< Driver RX ring buffer, bytes. */
#define LINK_TX_BUF_SIZE    4096        /**< Driver TX ring buffer, bytes (frames are copied into it). */
#define LINK_MAX_LINE       128         /**< Longest accepted command line (PC -> ESP32), bytes. */
#define LINK_MAX_FRAME      512         /**< Longest frame we build (ESP32 -> PC), incl. '$', checksum and newline. */
/** @} */

/**
 * @name Accelerometer simulation
 * Signal frequencies f, f1 and f2 are NOT fixed by the spec - chosen by the team. Keep the
 * highest component (2f in waveform 3) well below fs/2 at the lowest fs (50 Hz).
 * @{
 */
#define ACCEL_TICK_HZ       1000        /**< Master tick; every allowed fs divides it exactly. */
#define ACCEL_QUEUE_LEN     256         /**< Samples buffered between the tick and the TX task. */
#define ACCEL_DEFAULT_FUNC  WAVE_SINE   /**< Spec: any of the 3 functions, selectable per axis. */
#define ACCEL_DEFAULT_AMP_G 4           /**< Spec: 4 g default; 8 g, 16 g selectable. */
#define ACCEL_DEFAULT_FS_HZ 100         /**< Spec: 100 Hz default; 50/200/500/1000 selectable. */
#define ACCEL_BATCH_MS      15          /**< Target frame period per axis: 10-20 ms, see TODO.md "Bandwidth". */
#define ACCEL_BATCH_MAX     24          /**< Samples per frame, headroom above 1000 Hz * 20 ms = 20. */

#define ACCEL_F_HZ          2.0f        /**< f  (Hz): base frequency of waveforms 1 and 3. */
#define ACCEL_F1_HZ         0.5f        /**< f1 (Hz): modulating (envelope) frequency of waveform 2. */
#define ACCEL_F2_HZ         5.0f        /**< f2 (Hz): carrier frequency of waveform 2. */
/** @} */

/**
 * @name Environment simulation
 * @{
 */
#define ENV_DEFAULT_PERIOD_S 30         /**< Spec: 30 s or 60 s, selectable from the GUI. */
#define ENV_TEMP_MIN_C      15.0f       /**< Spec: 15.0 .. 30.0 C, 0.1 C resolution. */
#define ENV_TEMP_MAX_C      30.0f       /**< Upper bound of the temperature range, C. */
#define ENV_HUM_MIN_PCT     20          /**< Spec: 20 .. 40 %, 1 % resolution. */
#define ENV_HUM_MAX_PCT     40          /**< Upper bound of the humidity range, %. */
/** @} */

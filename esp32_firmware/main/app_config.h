/**
 * @file app_config.h
 * @brief Compile-time constants and spec defaults for the Tarea 1 firmware.
 *
 * Runtime-configurable values (waveform, amplitude, sample rate, env period) live in
 * their modules; only their *defaults* and the allowed ranges are defined here.
 */
#pragma once

#include "driver/uart.h"

/* ---------------------------------------------------------------- serial link */
#define LINK_UART_NUM       UART_NUM_0  /* USB-serial bridge on the dev board (shared with console) */
#define LINK_BAUD           115200      /* TODO(FW6): raise to 921600 if the bandwidth budget needs it */
#define LINK_RX_BUF_SIZE    1024
#define LINK_TX_BUF_SIZE    4096
#define LINK_MAX_LINE       128         /* longest accepted command line (PC -> ESP32) */
#define LINK_MAX_FRAME      512         /* longest frame we build (ESP32 -> PC), incl. "$", "*XX\n" */

/* --------------------------------------------------------- accelerometer sim */
#define ACCEL_TICK_HZ       1000        /* master tick; every allowed fs divides it exactly */
#define ACCEL_QUEUE_LEN     256         /* samples buffered between the tick and the TX task */
#define ACCEL_DEFAULT_FUNC  WAVE_SINE   /* spec: any of the 3 functions, selectable per axis */
#define ACCEL_DEFAULT_AMP_G 4           /* spec: 4 g default; 8 g, 16 g selectable */
#define ACCEL_DEFAULT_FS_HZ 100         /* spec: 100 Hz default; 50/200/500/1000 selectable */

/* Signal frequencies are NOT fixed by the spec - chosen by the team. Keep the highest
 * component (2*f in waveform 3) well below fs/2 at the lowest fs (50 Hz). */
#define ACCEL_F_HZ          2.0f
#define ACCEL_F1_HZ         0.5f
#define ACCEL_F2_HZ         5.0f

/* ----------------------------------------------------------- environment sim */
#define ENV_DEFAULT_PERIOD_S 30         /* spec: 30 s or 60 s, selectable from the GUI */
#define ENV_TEMP_MIN_C      15.0f       /* spec: 15.0 .. 30.0 C, 0.1 C resolution */
#define ENV_TEMP_MAX_C      30.0f
#define ENV_HUM_MIN_PCT     20          /* spec: 20 .. 40 %, 1 % resolution */
#define ENV_HUM_MAX_PCT     40

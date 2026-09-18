/**
 * @file accel_sim.h
 * @brief Synthetic tri-axial accelerometer.
 *
 * Each axis has its own waveform, amplitude and sample rate (spec 2.1.1). A single master
 * tick at ACCEL_TICK_HZ (1 kHz) drives all three axes: an axis at fs Hz emits one sample
 * every ACCEL_TICK_HZ / fs ticks. Samples go through a queue to a streaming task that
 * batches them into ACC frames (accel_sim.c).
 *
 * Thread model: the tick runs in the esp_timer task, the streaming task is a FreeRTOS task
 * and configuration changes arrive from the UART RX task. The per-axis configuration is
 * therefore only accessed through accel_sim_set_axis() / accel_sim_get_axis(), which use
 * a critical section.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

/** Waveform selector, numbered as in the spec (and in the CFG command). */
typedef enum {
    WAVE_SINE  = 1,   /**< a1(t) = A sin(2 pi f t) */
    WAVE_AM    = 2,   /**< a2(t) = A cos(2 pi f1 t) sin(2 pi f2 t) - amplitude modulated */
    WAVE_MULTI = 3,   /**< a3(t) = (2A/2) [sin(2 pi f t) + cos(4 pi f t)] - multi-component, peak 2A */
} wave_func_t;

/** Accelerometer axis; the numeric value indexes the per-axis tables. */
typedef enum {
    AXIS_X = 0,       /**< X axis */
    AXIS_Y = 1,       /**< Y axis */
    AXIS_Z = 2,       /**< Z axis */
    AXIS_COUNT = 3    /**< Number of axes (not a valid axis) */
} axis_t;

/** Runtime configuration of one axis (validated by accel_sim_set_axis()). */
typedef struct {
    wave_func_t func;    /**< Waveform, see wave_func_t */
    uint8_t     amp_g;   /**< Amplitude A in g: 4, 8 or 16 */
    uint16_t    fs_hz;   /**< Sample rate in Hz: 50, 100, 200, 500 or 1000 */
} axis_cfg_t;

/** One sample, as queued from the master tick to the streaming task. */
typedef struct {
    uint32_t t_ms;       /**< Sample time in ms: master tick count, which only advances while streaming */
    uint8_t  axis;       /**< Source axis (an axis_t value) */
    float    value;      /**< Acceleration in g */
} accel_sample_t;

/**
 * @brief Create the sample queue, the 1 kHz master timer and the streaming task.
 *
 * Also resets every axis to the spec defaults. Does not start streaming: that is done by
 * accel_sim_start() (called by the INIT command). Call once, after uart_link_init().
 */
void accel_sim_init(void);

/** @brief Start the master tick so samples begin to flow to the UART. No-op if already running. */
void accel_sim_start(void);

/**
 * @brief Stop the master tick. No-op if not running.
 *
 * Samples already queued are still transmitted; a partially filled batch stays pending until
 * the next start.
 */
void accel_sim_stop(void);

/**
 * @brief Restore every axis to ACCEL_DEFAULT_FUNC / ACCEL_DEFAULT_AMP_G / ACCEL_DEFAULT_FS_HZ.
 *
 * Takes effect immediately, also while streaming.
 */
void accel_sim_reset_defaults(void);

/**
 * @brief Reconfigure one axis; takes effect on the next tick, phase-continuous.
 *
 * All fields are validated (accel_sim_valid_func(), accel_sim_valid_amp(),
 * accel_sim_valid_fs()) before anything is changed, so a rejected command leaves the axis
 * untouched.
 *
 * @param     axis  Axis to configure.
 * @param[in] cfg   New configuration.
 *
 * @return true if applied; false if @p axis or any field of @p cfg is out of range.
 *
 * @note Thread-safe: the copy into the shared table happens inside a critical section.
 */
bool accel_sim_set_axis(axis_t axis, const axis_cfg_t *cfg);

/**
 * @brief Snapshot of the current configuration of one axis.
 *
 * @param axis  Axis to query; must be a valid axis_t (not checked).
 *
 * @return Copy of the configuration, read inside a critical section.
 */
axis_cfg_t accel_sim_get_axis(axis_t axis);

/**
 * @brief Check that @p func names one of the three spec waveforms.
 * @param func  Raw value from a CFG command.
 * @return true if @p func is 1, 2 or 3.
 */
bool accel_sim_valid_func(int func);

/**
 * @brief Check that @p amp_g is an allowed amplitude.
 * @param amp_g  Raw value from a CFG command.
 * @return true if @p amp_g is 4, 8 or 16.
 */
bool accel_sim_valid_amp(unsigned amp_g);

/**
 * @brief Check that @p fs_hz is an allowed sample rate (all of them divide ACCEL_TICK_HZ).
 * @param fs_hz  Raw value from a CFG command.
 * @return true if @p fs_hz is 50, 100, 200, 500 or 1000.
 */
bool accel_sim_valid_fs(unsigned fs_hz);

/**
 * @brief Evaluate a waveform at time @p t_s.
 *
 * Pure function of its arguments (the signal frequencies come from app_config.h), kept
 * separate from the timer so it can be unit-tested on the host.
 *
 * @param func   Waveform to evaluate.
 * @param amp_g  Amplitude A in g.
 * @param t_s    Time in seconds.
 *
 * @return Acceleration in g; 0 for an unknown @p func.
 */
float accel_sim_eval(wave_func_t func, float amp_g, float t_s);

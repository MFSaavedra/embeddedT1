/**
 * @file accel_sim.h
 * @brief Synthetic tri-axial accelerometer.
 *
 * Each axis has its own waveform, amplitude and sample rate (spec 2.1.1). A single master
 * tick at ACCEL_TICK_HZ (1 kHz) drives all three axes: an axis at fs Hz emits one sample
 * every ACCEL_TICK_HZ / fs ticks. Samples go through a queue to a streaming task that
 * formats them into frames (accel_sim.c).
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    WAVE_SINE  = 1,   /* a1(t) = A sin(2 pi f t)                          */
    WAVE_AM    = 2,   /* a2(t) = A cos(2 pi f1 t) sin(2 pi f2 t)          */
    WAVE_MULTI = 3,   /* a3(t) = (2A/2) [sin(2 pi f t) + cos(4 pi f t)]   */
} wave_func_t;

typedef enum { AXIS_X = 0, AXIS_Y = 1, AXIS_Z = 2, AXIS_COUNT = 3 } axis_t;

typedef struct {
    wave_func_t func;
    uint8_t     amp_g;   /* 4 | 8 | 16 */
    uint16_t    fs_hz;   /* 50 | 100 | 200 | 500 | 1000 */
} axis_cfg_t;

typedef struct {
    uint32_t t_ms;       /* time of the sample since boot */
    uint8_t  axis;       /* axis_t */
    float    value;      /* acceleration in g */
} accel_sample_t;

void       accel_sim_init(void);                 /* queue, timer and streaming task */
void       accel_sim_start(void);                /* start emitting samples */
void       accel_sim_stop(void);
void       accel_sim_reset_defaults(void);       /* all axes back to spec defaults */
bool       accel_sim_set_axis(axis_t axis, const axis_cfg_t *cfg);   /* validated, thread-safe */
axis_cfg_t accel_sim_get_axis(axis_t axis);

bool accel_sim_valid_func(int func);
bool accel_sim_valid_amp(unsigned amp_g);
bool accel_sim_valid_fs(unsigned fs_hz);

/** Pure waveform evaluation; kept separate so it can be unit-tested on the host. */
float accel_sim_eval(wave_func_t func, float amp_g, float t_s);

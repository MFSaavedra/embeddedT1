#include "accel_sim.h"
#include "app_config.h"
#include "uart_link.h"

#include <math.h>
#include <stdio.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "accel_sim";

static const axis_cfg_t DEFAULT_CFG = {
    .func  = ACCEL_DEFAULT_FUNC,
    .amp_g = ACCEL_DEFAULT_AMP_G,
    .fs_hz = ACCEL_DEFAULT_FS_HZ,
};

static axis_cfg_t        s_cfg[AXIS_COUNT];
static portMUX_TYPE      s_cfg_lock = portMUX_INITIALIZER_UNLOCKED;
static esp_timer_handle_t s_tick_timer;
static QueueHandle_t     s_sample_queue;
static uint32_t          s_tick;        /* increments at ACCEL_TICK_HZ while running */
static volatile bool     s_running;

typedef struct {
    float    values[ACCEL_BATCH_MAX];
    uint32_t t0_ms;
    int      count;
} axis_batch_t;

static axis_batch_t s_batch[AXIS_COUNT];

/* --------------------------------- validation --------------------------------- */

bool accel_sim_valid_func(int func)      { return func >= WAVE_SINE && func <= WAVE_MULTI; }
bool accel_sim_valid_amp(unsigned amp_g) { return amp_g == 4 || amp_g == 8 || amp_g == 16; }
bool accel_sim_valid_fs(unsigned fs_hz)
{
    return fs_hz == 50 || fs_hz == 100 || fs_hz == 200 || fs_hz == 500 || fs_hz == 1000;
}

/* --------------------------------- waveforms --------------------------------- */

float accel_sim_eval(wave_func_t func, float amp_g, float t_s)
{
    switch (func) {
    case WAVE_SINE:
        /* a1(t) = A * sin(2*pi*f*t) */
        return amp_g * sinf(2.0f * (float)M_PI * ACCEL_F_HZ * t_s);
    case WAVE_AM:
        /* a2(t) = A * cos(2*pi*f1*t) * sin(2*pi*f2*t) */
        return amp_g * cosf(2.0f * (float)M_PI * ACCEL_F1_HZ * t_s)
                      * sinf(2.0f * (float)M_PI * ACCEL_F2_HZ * t_s);
    case WAVE_MULTI:
        /* a3(t) = (2A/2) * [sin(2*pi*f*t) + cos(4*pi*f*t)]  -- literal spec factor, peak = 2A */
        return (2.0f * amp_g / 2.0f)
             * (sinf(2.0f * (float)M_PI * ACCEL_F_HZ * t_s)
                + cosf(4.0f * (float)M_PI * ACCEL_F_HZ * t_s));
    default:
        return 0.0f;
    }
}

/* ---------------------------- master tick (1 kHz) --------------------------- */

/* Runs in the esp_timer task, NOT in an ISR: normal FreeRTOS calls are allowed, but it
 * must return quickly - never block on the queue or on the UART here. */
static void on_tick(void *arg)
{
    (void)arg;
    if (!s_running) {
        return;
    }
    s_tick++;

    for (int a = 0; a < AXIS_COUNT; a++) {
        axis_cfg_t cfg = accel_sim_get_axis((axis_t)a);
        uint32_t divider = ACCEL_TICK_HZ / cfg.fs_hz;   /* 1, 2, 5, 10 or 20 */
        if (s_tick % divider == 0) {
            float t_s = (float)s_tick / ACCEL_TICK_HZ;   /* global time: phase-continuous across fs changes */
            accel_sample_t s = {
                .t_ms  = s_tick * (1000 / ACCEL_TICK_HZ),
                .axis  = (axis_t)a,
                .value = accel_sim_eval(cfg.func, cfg.amp_g, t_s),
            };
            xQueueSend(s_sample_queue, &s, 0);   /* 0 timeout: drop instead of blocking the timer */
        }
    }
}

/* ------------------------------ streaming task ------------------------------- */

static void flush_axis(axis_t axis)
{
    axis_batch_t *b = &s_batch[axis];
    if (b->count == 0) {
        return;
    }
    axis_cfg_t cfg = accel_sim_get_axis(axis);
    char payload[LINK_MAX_FRAME];
    int len = snprintf(payload, sizeof(payload), "ACC,%c,%lu,%u",
                        "XYZ"[axis], (unsigned long)b->t0_ms, (unsigned)cfg.fs_hz);
    for (int i = 0; i < b->count && len > 0 && (size_t)len < sizeof(payload); i++) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len, ",%.3f", (double)b->values[i]);
    }
    uart_link_send_frame(payload);   /* logs + drops if still too long; see uart_link.c */
    b->count = 0;
}

static void stream_task(void *arg)
{
    (void)arg;
    accel_sample_t sample;
    for (;;) {
        if (xQueueReceive(s_sample_queue, &sample, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        axis_batch_t *b = &s_batch[sample.axis];
        if (b->count == 0) {
            b->t0_ms = sample.t_ms;
        }
        if (b->count < ACCEL_BATCH_MAX) {
            b->values[b->count++] = sample.value;
        }

        axis_cfg_t cfg = accel_sim_get_axis(sample.axis);
        uint32_t target = (cfg.fs_hz * ACCEL_BATCH_MS) / 1000;
        if (target < 1) {
            target = 1;
        }
        if (b->count >= (int)target || b->count >= ACCEL_BATCH_MAX) {
            flush_axis(sample.axis);
        }
    }
}

/* --------------------------------- public API --------------------------------- */

void accel_sim_init(void)
{
    accel_sim_reset_defaults();

    s_sample_queue = xQueueCreate(ACCEL_QUEUE_LEN, sizeof(accel_sample_t));
    configASSERT(s_sample_queue != NULL);

    const esp_timer_create_args_t args = {
        .callback        = on_tick,
        .arg             = NULL,
        .dispatch_method = ESP_TIMER_TASK,
        .name            = "accel_tick",
    };
    ESP_ERROR_CHECK(esp_timer_create(&args, &s_tick_timer));

    xTaskCreate(stream_task, "accel_stream", 4096, NULL, 9, NULL);
    ESP_LOGI(TAG, "init done (master tick %d Hz)", ACCEL_TICK_HZ);
}

void accel_sim_start(void)
{
    if (s_running) {
        return;
    }
    s_running = true;
    ESP_ERROR_CHECK(esp_timer_start_periodic(s_tick_timer, 1000000 / ACCEL_TICK_HZ));
    ESP_LOGI(TAG, "streaming started");
}

void accel_sim_stop(void)
{
    if (!s_running) {
        return;
    }
    s_running = false;
    ESP_ERROR_CHECK(esp_timer_stop(s_tick_timer));
    ESP_LOGI(TAG, "streaming stopped");
}

bool accel_sim_set_axis(axis_t axis, const axis_cfg_t *cfg)
{
    if (axis >= AXIS_COUNT || cfg == NULL || !accel_sim_valid_func(cfg->func) ||
        !accel_sim_valid_amp(cfg->amp_g) || !accel_sim_valid_fs(cfg->fs_hz)) {
        return false;
    }
    portENTER_CRITICAL(&s_cfg_lock);
    s_cfg[axis] = *cfg;
    portEXIT_CRITICAL(&s_cfg_lock);
    ESP_LOGI(TAG, "axis %c: func=%d amp=%u g fs=%u Hz",
             "XYZ"[axis], (int)cfg->func, (unsigned)cfg->amp_g, (unsigned)cfg->fs_hz);
    return true;
}

axis_cfg_t accel_sim_get_axis(axis_t axis)
{
    axis_cfg_t c;
    portENTER_CRITICAL(&s_cfg_lock);
    c = s_cfg[axis];
    portEXIT_CRITICAL(&s_cfg_lock);
    return c;
}

void accel_sim_reset_defaults(void)
{
    for (int a = 0; a < AXIS_COUNT; a++) {
        accel_sim_set_axis((axis_t)a, &DEFAULT_CFG);
    }
}

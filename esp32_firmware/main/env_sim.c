/**
 * @file env_sim.c
 * @brief Random temperature / humidity readings sent as ENV frames every 30 s or 60 s.
 *
 * Public API: env_sim.h.
 */
#include "env_sim.h"
#include "app_config.h"
#include "uart_link.h"

#include <stdio.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"

/** Log tag of this module. */
static const char *TAG = "env_sim";

static esp_timer_handle_t s_timer;                              /**< Periodic timer, runs on_period() */
static uint16_t           s_period_s = ENV_DEFAULT_PERIOD_S;    /**< Current period in seconds (30 or 60) */
static bool               s_running;                            /**< True between env_sim_start() and env_sim_stop() */

bool env_sim_valid_period(unsigned seconds) { return seconds == 30 || seconds == 60; }

env_reading_t env_sim_read(void)
{
    env_reading_t r;
    r.temp_c  = ENV_TEMP_MIN_C + (esp_random() % 151) / 10.0f;   /* 15.0 .. 30.0 step 0.1 */
    r.hum_pct = (uint8_t)(ENV_HUM_MIN_PCT + esp_random() % 21);  /* 20 .. 40 step 1 */
    return r;
}

/**
 * @brief Timer callback: draw one reading and send it as an ENV frame.
 *
 *     ENV,<temp_c>,<hum_pct>
 *
 * Runs in the esp_timer task context: a short uart_write_bytes() is fine here (it only
 * copies into the driver's TX ring buffer). Also called directly by env_sim_start().
 *
 * @param arg  Unused (esp_timer callback argument).
 */
static void on_period(void *arg)
{
    (void)arg;
    env_reading_t r = env_sim_read();
    char payload[32];
    snprintf(payload, sizeof payload, "ENV,%.1f,%u", (double)r.temp_c, (unsigned)r.hum_pct);
    uart_link_send_frame(payload);
}

void env_sim_init(void)
{
    const esp_timer_create_args_t args = {
        .callback        = on_period,
        .arg             = NULL,
        .dispatch_method = ESP_TIMER_TASK,
        .name            = "env_period",
    };
    ESP_ERROR_CHECK(esp_timer_create(&args, &s_timer));
}

void env_sim_start(void)
{
    if (s_running) {
        return;
    }
    s_running = true;
    ESP_ERROR_CHECK(esp_timer_start_periodic(s_timer, (uint64_t)s_period_s * 1000000ULL));
    on_period(NULL);   /* send one reading immediately so the GUI isn't empty for a full period */
    ESP_LOGI(TAG, "started, period %u s", (unsigned)s_period_s);
}

void env_sim_stop(void)
{
    if (!s_running) {
        return;
    }
    s_running = false;
    ESP_ERROR_CHECK(esp_timer_stop(s_timer));
}

bool env_sim_set_period(uint16_t seconds)
{
    if (!env_sim_valid_period(seconds)) {
        return false;
    }
    s_period_s = seconds;
    if (s_running) {                       /* restart so the new period applies immediately */
        ESP_ERROR_CHECK(esp_timer_stop(s_timer));
        ESP_ERROR_CHECK(esp_timer_start_periodic(s_timer, (uint64_t)s_period_s * 1000000ULL));
    }
    ESP_LOGI(TAG, "period = %u s", (unsigned)s_period_s);
    return true;
}

uint16_t env_sim_get_period(void) { return s_period_s; }

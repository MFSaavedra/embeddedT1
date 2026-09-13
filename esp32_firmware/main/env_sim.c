#include "env_sim.h"
#include "app_config.h"
#include "uart_link.h"

#include <stdio.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"

static const char *TAG = "env_sim";

static esp_timer_handle_t s_timer;
static uint16_t           s_period_s = ENV_DEFAULT_PERIOD_S;
static bool               s_running;

bool env_sim_valid_period(unsigned seconds) { return seconds == 30 || seconds == 60; }

env_reading_t env_sim_read(void)
{
    env_reading_t r = { .temp_c = 0.0f, .hum_pct = 0 };
    /* TODO(FW4): random values with the ranges/resolution from app_config.h, e.g.
     *   r.temp_c  = ENV_TEMP_MIN_C + (esp_random() % 151) / 10.0f;   // 15.0 .. 30.0 step 0.1
     *   r.hum_pct = ENV_HUM_MIN_PCT + esp_random() % 21;             // 20 .. 40 step 1
     */
    return r;
}

/* esp_timer task context: a short uart_write_bytes() is fine here (it only copies into the
 * driver's TX ring buffer). */
static void on_period(void *arg)
{
    (void)arg;
    env_reading_t r = env_sim_read();
    /* TODO(FW4): format and send the $ENV frame (README "Protocol"), e.g.
     *   char payload[32];
     *   snprintf(payload, sizeof payload, "ENV,%.1f,%u", r.temp_c, (unsigned)r.hum_pct);
     *   uart_link_send_frame(payload);
     */
    (void)r;
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
    /* TODO(FW4, optional): send one reading right away so the GUI does not sit empty for
     * 30-60 s after connecting: on_period(NULL); */
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

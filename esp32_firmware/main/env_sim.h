/**
 * @file env_sim.h
 * @brief Synthetic temperature / relative-humidity sensor (spec 2.1.2).
 *
 * A periodic esp_timer (30 s or 60 s) draws a random reading and sends it as an $ENV frame.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    float   temp_c;    /* 15.0 .. 30.0, 0.1 resolution */
    uint8_t hum_pct;   /* 20 .. 40, 1 resolution */
} env_reading_t;

void          env_sim_init(void);
void          env_sim_start(void);
void          env_sim_stop(void);
bool          env_sim_set_period(uint16_t seconds);   /* 30 | 60; restarts the timer if running */
uint16_t      env_sim_get_period(void);
bool          env_sim_valid_period(unsigned seconds);
env_reading_t env_sim_read(void);                     /* draw one random reading */

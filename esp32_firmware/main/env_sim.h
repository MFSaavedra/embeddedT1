/**
 * @file env_sim.h
 * @brief Synthetic temperature / relative-humidity sensor (spec 2.1.2).
 *
 * A periodic esp_timer (30 s or 60 s) draws a random reading and sends it as an ENV frame.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

/** One reading of the environmental sensor. */
typedef struct {
    float   temp_c;    /**< Temperature in degrees C: 15.0 .. 30.0, 0.1 resolution */
    uint8_t hum_pct;   /**< Relative humidity in percent: 20 .. 40, 1 resolution */
} env_reading_t;

/** @brief Create the periodic timer without starting it. Call once, after uart_link_init(). */
void env_sim_init(void);

/**
 * @brief Start periodic readings at the current period.
 *
 * Sends one reading immediately so the GUI is not empty for a full period. No-op if already
 * running.
 */
void env_sim_start(void);

/** @brief Stop periodic readings. No-op if not running. */
void env_sim_stop(void);

/**
 * @brief Set the transmission period.
 *
 * If the simulator is running the timer is restarted, so the new period applies at once
 * (the next reading is sent one full period from now).
 *
 * @param seconds  30 or 60.
 *
 * @return true if applied; false if @p seconds is not allowed (period unchanged).
 */
bool env_sim_set_period(uint16_t seconds);

/**
 * @brief Current transmission period.
 * @return Period in seconds (30 or 60).
 */
uint16_t env_sim_get_period(void);

/**
 * @brief Check that @p seconds is an allowed period.
 * @param seconds  Raw value from an ENV command.
 * @return true if @p seconds is 30 or 60.
 */
bool env_sim_valid_period(unsigned seconds);

/**
 * @brief Draw one random reading, uniformly distributed over the spec ranges.
 * @return Reading with temp_c in 15.0 .. 30.0 (0.1 steps) and hum_pct in 20 .. 40 (1 steps).
 */
env_reading_t env_sim_read(void);

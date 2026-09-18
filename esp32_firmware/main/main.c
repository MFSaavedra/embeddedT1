/**
 * @file main.c
 * @brief Tarea 1 - CC5328 (Sistemas Embebidos y Sensores): ESP32 data-acquisition firmware.
 *
 * Emulates a tri-axial accelerometer and a temperature/humidity sensor and streams them to a
 * PyQt GUI over UART0 (USB-serial), accepting configuration commands in real time.
 *
 * Module map (one responsibility per file):
 * - uart_link.c  - UART0 driver, frame TX, line-oriented RX task
 * - protocol.c   - "$payload*XX" framing + XOR checksum (mirrored by gui_python/protocol.py)
 * - commands.c   - parses GUI commands (CFG / ENV / INIT) and applies them
 * - accel_sim.c  - 3-axis synthetic accelerometer, per-axis func/amp/fs, 1 kHz master tick
 * - env_sim.c    - random temperature/humidity every 30 s or 60 s
 * - app_config.h - spec defaults and compile-time constants
 */
#include "accel_sim.h"
#include "app_config.h"
#include "commands.h"
#include "env_sim.h"
#include "uart_link.h"

#include "esp_log.h"

/** Log tag of this module. */
static const char *TAG = "main";

/**
 * @brief Application entry point: bring up every module and start listening for commands.
 *
 * Streaming does NOT start here: it starts when the GUI sends INIT (commands_handle_line()
 * -> handle_init()). Returns after setup; the FreeRTOS tasks created by the modules keep
 * running.
 */
void app_main(void)
{
    uart_link_init();
    accel_sim_init();
    env_sim_init();
    uart_link_start_rx_task(commands_handle_line);

    ESP_LOGI(TAG, "Tarea1 DAQ firmware ready (link %d baud)", LINK_BAUD);
}

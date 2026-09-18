/**
 * @file commands.c
 * @brief Parses GUI commands (CFG / ENV / INIT), applies them and replies ACK / ERR.
 *
 * See commands.h for the command set and README.md "Protocolo" for the frame definitions.
 */
#include "commands.h"
#include "accel_sim.h"
#include "app_config.h"
#include "env_sim.h"
#include "protocol.h"
#include "uart_link.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_log.h"

/** Log tag of this module. */
static const char *TAG = "commands";

/** Maximum number of comma-separated fields a command may carry (CFG, the longest, uses 5). */
#define MAX_FIELDS 8

/**
 * @brief Send an acknowledgement frame: "ACK," followed by @p what.
 * @param[in] what  Name of the command being acknowledged ("CFG", "ENV").
 */
static void send_ack(const char *what)
{
    char payload[32];
    snprintf(payload, sizeof payload, "ACK,%s", what);
    uart_link_send_frame(payload);
}

/**
 * @brief Send an error frame: "ERR," followed by @p why.
 * @param[in] why  Short reason code: "BADFRAME", "EMPTY", "UNKNOWN" or "BADARG".
 */
static void send_err(const char *why)
{
    char payload[32];
    snprintf(payload, sizeof payload, "ERR,%s", why);
    uart_link_send_frame(payload);
}

/**
 * @brief Handle a CFG command: reconfigure one accelerometer axis.
 *
 *     CFG,<X|Y|Z>,<func>,<amp>,<fs>
 *
 * Replies ACK,CFG on success, or ERR,BADARG if the field count, the axis letter or any
 * value is outside the allowed set (accel_sim_set_axis() validates func / amp / fs; a
 * non-numeric field parses as 0 and is rejected the same way).
 *
 * @param[in] fields  Payload fields as split by proto_split(); fields[0] is "CFG".
 * @param     n       Number of entries in @p fields.
 */
static void handle_cfg(char *fields[], int n)
{
    if (n != 5 || fields[1][0] == '\0' || fields[1][1] != '\0') {
        send_err("BADARG");
        return;
    }
    axis_t axis;
    switch (fields[1][0]) {
    case 'X': axis = AXIS_X; break;
    case 'Y': axis = AXIS_Y; break;
    case 'Z': axis = AXIS_Z; break;
    default:  send_err("BADARG"); return;
    }

    axis_cfg_t cfg = {
        .func  = (wave_func_t)strtol(fields[2], NULL, 10),
        .amp_g = (uint8_t)strtol(fields[3], NULL, 10),
        .fs_hz = (uint16_t)strtol(fields[4], NULL, 10),
    };
    if (!accel_sim_set_axis(axis, &cfg)) {
        send_err("BADARG");
        return;
    }
    send_ack("CFG");
}

/**
 * @brief Handle an ENV command: set the transmission period of the environmental sensor.
 *
 *     ENV,<30|60>
 *
 * Replies ACK,ENV on success, or ERR,BADARG if the field count or the period is not allowed.
 *
 * @param[in] fields  Payload fields as split by proto_split(); fields[0] is "ENV".
 * @param     n       Number of entries in @p fields.
 */
static void handle_env(char *fields[], int n)
{
    if (n != 2) {
        send_err("BADARG");
        return;
    }
    uint16_t seconds = (uint16_t)strtol(fields[1], NULL, 10);
    if (!env_sim_set_period(seconds)) {
        send_err("BADARG");
        return;
    }
    send_ack("ENV");
}

/**
 * @brief Handle an INIT command: restore the spec defaults and (re)start streaming.
 *
 *     INIT
 *
 * Resets the three axes and the environmental period to the app_config.h defaults, starts
 * both simulators (no-op if already running) and replies ACK,INIT,FW_VERSION. Streaming
 * starts only here, never at boot.
 *
 * @param fields  Unused.
 * @param n       Unused.
 */
static void handle_init(char *fields[], int n)
{
    (void)fields;
    (void)n;
    accel_sim_reset_defaults();
    env_sim_set_period(ENV_DEFAULT_PERIOD_S);
    accel_sim_start();
    env_sim_start();

    char payload[32];
    snprintf(payload, sizeof payload, "ACK,INIT,%s", FW_VERSION);
    uart_link_send_frame(payload);
}

void commands_handle_line(const char *line)
{
    char payload[LINK_MAX_LINE];
    if (!proto_parse(line, payload, sizeof payload)) {
        /* Noise, an echo, or a bad checksum: report it but never crash or reset state. */
        ESP_LOGW(TAG, "rejected line: %s", line);
        send_err("BADFRAME");
        return;
    }

    char *fields[MAX_FIELDS];
    int n = proto_split(payload, fields, MAX_FIELDS);
    if (n == 0) {
        send_err("EMPTY");
        return;
    }

    if (strcmp(fields[0], "CFG") == 0) {
        handle_cfg(fields, n);
    } else if (strcmp(fields[0], "ENV") == 0) {
        handle_env(fields, n);
    } else if (strcmp(fields[0], "INIT") == 0) {
        handle_init(fields, n);
    } else {
        send_err("UNKNOWN");
    }
}

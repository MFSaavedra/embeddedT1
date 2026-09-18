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

#include <stdbool.h>
#include <stdint.h>
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
 * @brief Parse one numeric command field strictly.
 *
 * Unlike a bare strtol(), this rejects empty fields, trailing garbage ("10x") and values
 * outside [lo, hi], so a later narrowing cast can never wrap (e.g. 260 -> 4 as uint8_t).
 *
 * @param[in]  s    NUL-terminated field text.
 * @param      lo   Smallest accepted value.
 * @param      hi   Largest accepted value.
 * @param[out] out  Parsed value, only written on success.
 * @return true if @p s is a decimal integer within [lo, hi].
 */
static bool parse_field(const char *s, long lo, long hi, long *out)
{
    char *end = NULL;
    long v = strtol(s, &end, 10);
    if (end == s || *end != '\0' || v < lo || v > hi) {
        return false;
    }
    *out = v;
    return true;
}

/**
 * @brief Handle a CFG command: reconfigure one accelerometer axis.
 *
 *     CFG,<X|Y|Z>,<func>,<amp>,<fs>
 *
 * Replies ACK,CFG on success, or ERR,BADARG if the field count, the axis letter or any
 * value is not a well-formed integer in range (parse_field()) or outside the allowed set
 * (accel_sim_set_axis() validates func / amp / fs).
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

    long func, amp, fs;
    if (!parse_field(fields[2], 0, UINT8_MAX, &func) ||
        !parse_field(fields[3], 0, UINT8_MAX, &amp) ||
        !parse_field(fields[4], 0, UINT16_MAX, &fs)) {
        send_err("BADARG");
        return;
    }
    axis_cfg_t cfg = {
        .func  = (wave_func_t)func,
        .amp_g = (uint8_t)amp,
        .fs_hz = (uint16_t)fs,
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
    long seconds;
    if (!parse_field(fields[1], 0, UINT16_MAX, &seconds) || !env_sim_set_period((uint16_t)seconds)) {
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
 * Resets the three axes and the environmental period to the app_config.h defaults, replies
 * ACK,INIT,FW_VERSION and then (re)starts both simulators. Streaming starts only here, never
 * at boot. The environmental simulator is stopped first so that env_sim_start() emits a fresh
 * $ENV reading on every INIT, not just the first; the ACK is sent before any data so the GUI
 * clears its panels on the ACK and then receives the new values.
 *
 * @param fields  Unused.
 * @param n       Unused.
 */
static void handle_init(char *fields[], int n)
{
    (void)fields;
    (void)n;
    accel_sim_reset_defaults();
    env_sim_stop();
    env_sim_set_period(ENV_DEFAULT_PERIOD_S);

    char payload[32];
    snprintf(payload, sizeof payload, "ACK,INIT,%s", FW_VERSION);
    uart_link_send_frame(payload);

    accel_sim_start();
    env_sim_start();
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

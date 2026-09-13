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

static const char *TAG = "commands";

#define MAX_FIELDS 8

static void send_ack(const char *what)
{
    char payload[32];
    snprintf(payload, sizeof payload, "ACK,%s", what);
    uart_link_send_frame(payload);
}

static void send_err(const char *why)
{
    char payload[32];
    snprintf(payload, sizeof payload, "ERR,%s", why);
    uart_link_send_frame(payload);
}

/* $CFG,<axis>,<func>,<amp>,<fs> */
static void handle_cfg(char *fields[], int n)
{
    /* TODO(FW5): expect n == 5; map fields[1] ("X"/"Y"/"Z") to axis_t; parse fields[2..4]
     * with strtol; fill an axis_cfg_t; accel_sim_set_axis() validates the values and returns
     * false on a bad one -> send_err("BADARG"); otherwise send_ack("CFG"). */
    (void)fields;
    (void)n;
    send_err("NOTIMPL");
}

/* $ENV,<period_s> */
static void handle_env(char *fields[], int n)
{
    /* TODO(FW5): expect n == 2; env_sim_set_period(strtol(fields[1])) -> ACK,ENV / ERR,BADARG */
    (void)fields;
    (void)n;
    send_err("NOTIMPL");
}

/* $INIT */
static void handle_init(char *fields[], int n)
{
    /* TODO(FW5): accel_sim_reset_defaults(), env period back to default, (re)start both
     * simulators, then send_ack("INIT") - consider appending a firmware version/ID so the
     * GUI can show "ESP32 ready (fw 1.0)". */
    (void)fields;
    (void)n;
    send_err("NOTIMPL");
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
    /* send_ack() is only referenced from the TODO stubs above; this keeps -Wunused quiet
     * until FW5 is implemented. */
    (void)send_ack;
}

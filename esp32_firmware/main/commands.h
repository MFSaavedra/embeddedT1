/**
 * @file commands.h
 * @brief Interpretation of GUI -> ESP32 commands (spec 2.1.3).
 *
 * Command set (final definition in README.md "Protocolo"):
 *
 *     $CFG,<X|Y|Z>,<func 1..3>,<amp 4|8|16>,<fs 50|100|200|500|1000>*XX
 *     $ENV,<30|60>*XX
 *     $INIT*XX
 *     $BAUD,<115200|230400|460800|921600>*XX
 *
 * - CFG reconfigures one accelerometer axis (accel_sim_set_axis()).
 * - ENV sets the transmission period of the environmental sensor (env_sim_set_period()).
 * - INIT restores the spec defaults, (re)starts streaming and replies with the firmware version.
 * - BAUD changes the speed of the link itself, stopping the streaming that INIT restarts.
 *
 * Every command is answered with an ACK frame (`ACK,CFG`, `ACK,ENV`, `ACK,INIT,1.0`,
 * `ACK,BAUD,230400`) or an ERR frame with a reason code: BADFRAME, EMPTY, UNKNOWN or BADARG.
 */
#pragma once

/**
 * @brief Entry point for the UART RX task: validate one line and dispatch on its type.
 *
 * Rejects anything that is not a valid frame (ERR,BADFRAME), then routes CFG / ENV / INIT /
 * BAUD to their handlers; unknown types get ERR,UNKNOWN. Never crashes or changes state on
 * bad input, so noise on the shared console is harmless. A frame that passes the checksum
 * also confirms the current link speed (uart_link_confirm_baud()).
 *
 * @param[in] line  NUL-terminated line without CR/LF, as delivered by uart_link.
 *
 * @note Runs in the UART RX task context (see uart_link_start_rx_task()).
 */
void commands_handle_line(const char *line);

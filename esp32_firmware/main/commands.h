/**
 * @file commands.h
 * @brief Interpretation of GUI -> ESP32 commands (spec 2.1.3).
 *
 * Draft command set (finalise in README "Protocol"):
 *   $CFG,<X|Y|Z>,<func 1..3>,<amp 4|8|16>,<fs 50|100|200|500|1000>*XX
 *   $ENV,<30|60>*XX
 *   $INIT*XX                       -> defaults + (re)start streaming, replies $ACK,INIT,...
 * Every command is answered with $ACK,<cmd>*XX or $ERR,<reason>*XX.
 */
#pragma once

/** Entry point for the UART RX task: validates the frame and dispatches on its type. */
void commands_handle_line(const char *line);

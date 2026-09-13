/**
 * @file uart_link.h
 * @brief UART0 setup, frame transmission and line-oriented reception.
 */
#pragma once

#include <stddef.h>

/** Called from the RX task with each complete line (CR/LF stripped, NUL-terminated). */
typedef void (*uart_line_cb_t)(const char *line);

/** Install the UART driver on LINK_UART_NUM at LINK_BAUD and route stdout through it. */
void uart_link_init(void);

/** Wrap @p payload as "$payload*XX\n" and transmit it (thread-safe, one frame per call). */
void uart_link_send_frame(const char *payload);

/** Transmit raw bytes (used by send_frame; exposed for debugging). */
void uart_link_send_raw(const char *data, size_t len);

/** Start the background task that reads lines from the PC and hands them to @p cb. */
void uart_link_start_rx_task(uart_line_cb_t cb);

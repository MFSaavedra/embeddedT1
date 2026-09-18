/**
 * @file uart_link.h
 * @brief UART0 setup, frame transmission and line-oriented reception.
 *
 * Thin wrapper around the ESP-IDF UART driver: uart_link_init() configures LINK_UART_NUM,
 * uart_link_send_frame() wraps a payload with the protocol.h framing and writes it, and a
 * background task (uart_link_start_rx_task()) splits incoming bytes into lines for the
 * command layer.
 */
#pragma once

#include <stddef.h>

/**
 * @brief Callback invoked by the RX task for each complete line received from the PC.
 *
 * @param line  NUL-terminated line with CR/LF stripped. Only valid for the duration of the
 *              call; copy it if it must outlive the callback.
 */
typedef void (*uart_line_cb_t)(const char *line);

/**
 * @brief Install the UART driver on LINK_UART_NUM at LINK_BAUD and route stdout through it.
 *
 * Routing stdout / ESP_LOG through the same driver guarantees that a log line is never
 * spliced byte-by-byte into the middle of a data frame. Must be called once, before any
 * other function of this module.
 */
void uart_link_init(void);

/**
 * @brief Frame @p payload with proto_build() and transmit it.
 *
 * Thread-safe: the whole frame is handed to the driver in a single write, so frames from
 * different tasks are never interleaved. A frame that does not fit in LINK_MAX_FRAME is
 * logged and dropped.
 *
 * @param[in] payload  NUL-terminated payload without '$', '*' or checksum.
 */
void uart_link_send_frame(const char *payload);

/**
 * @brief Transmit raw bytes without framing.
 *
 * Used internally by uart_link_send_frame(); exposed for debugging only. Blocks until the
 * bytes have been copied into the driver's TX ring buffer.
 *
 * @param[in] data  Bytes to send.
 * @param     len   Number of bytes.
 */
void uart_link_send_raw(const char *data, size_t len);

/**
 * @brief Start the background task that reads lines from the PC and hands them to @p cb.
 *
 * @param cb  Called from the RX task context for every non-empty line. Lines that do not
 *            fit in LINK_MAX_LINE are discarded.
 */
void uart_link_start_rx_task(uart_line_cb_t cb);

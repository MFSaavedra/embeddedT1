/**
 * @file protocol.h
 * @brief Frame layer shared by both directions of the serial link.
 *
 * Frame format (ASCII, one frame per line):
 *
 *     $<payload>*<XX>\n
 *
 *   payload : comma-separated fields, the first one is the message type (e.g. "CFG,X,1,4,100")
 *   XX      : two upper-case hex digits = XOR of every payload byte (between '$' and '*')
 *
 * This file only knows about framing and checksums. Message types and their fields are
 * defined in README.md ("Protocol") and handled in commands.c / accel_sim.c / env_sim.c.
 * gui_python/protocol.py mirrors this exactly - keep both in sync.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/** XOR checksum of @p len bytes of @p payload. */
uint8_t proto_checksum(const char *payload, size_t len);

/**
 * Build "$payload*XX\n" into @p out.
 * @return number of bytes written (excluding the NUL), or -1 if @p out_size is too small.
 */
int proto_build(char *out, size_t out_size, const char *payload);

/**
 * Validate a received line (without CR/LF) and extract its payload.
 * @return true if the line is a well-formed frame with a matching checksum.
 */
bool proto_parse(const char *line, char *payload_out, size_t out_size);

/**
 * Split @p payload in place on ',' and store pointers to each field.
 * @return number of fields stored (at most @p max_fields).
 */
int proto_split(char *payload, char *fields[], int max_fields);

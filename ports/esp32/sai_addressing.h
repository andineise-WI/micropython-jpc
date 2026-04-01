/*
 * SAI CAN Auto-Addressing — Early Boot Module Discovery
 *
 * Runs before MicroPython VM to discover and address SAI modules
 * on the CAN bus via the SAI bootloader protocol (0x7FE/0x7FF).
 *
 * TWAI driver remains installed after addressing so machine.CAN
 * can take over without re-initialization.
 */

#ifndef SAI_ADDRESSING_H
#define SAI_ADDRESSING_H

#include <stdint.h>
#include <stdbool.h>

// Maximum number of SAI modules supported on one CAN bus.
#define SAI_MAX_NODES 16

// CAN protocol constants for SAI bootloader addressing.
#define SAI_BOOTLOADER_TX       0x7FE
#define SAI_BOOTLOADER_RX       0x7FF
#define SAI_APP_START_BROADCAST 0x77F

// Addressing command bytes (sent/received in data[0]).
#define SAI_CMD_BOOTUP          0x01
#define SAI_CMD_ASSIGN_ADDR     0x81
#define SAI_CMD_SWITCH_ON       0x82
#define SAI_CMD_APP_START       0x83
#define SAI_CMD_APP_START_BC    0x7F

// Timeout: silence period to declare addressing complete (ms).
#define SAI_SILENCE_TIMEOUT_MS  1000

// Timeout: maximum total addressing duration as safety net (ms).
#define SAI_TOTAL_TIMEOUT_MS    5000

// Result of the early addressing phase, filled by C code,
// read by Python via the sai module.
typedef struct {
    uint8_t count;                      // Number of discovered modules.
    uint8_t node_ids[SAI_MAX_NODES];    // Assigned node IDs (1-based).
    bool addressing_done;               // true once addressing has completed.
    bool twai_installed;                // true if TWAI driver is still running.
} sai_addressing_result_t;

// Global result, written by sai_early_addressing(), read by Python.
extern sai_addressing_result_t sai_addressing_result;

// Run early CAN addressing. Call from board startup, before MicroPython.
// Installs TWAI driver, performs addressing, leaves TWAI running.
void sai_early_addressing(void);

#endif // SAI_ADDRESSING_H

/*
 * JackPack ESP32 — Board Startup with Early CAN Addressing
 *
 * Runs standard board initialization (NVS, flash detection),
 * then immediately starts SAI CAN auto-addressing before
 * the MicroPython task is created.
 */

#include "sai_addressing.h"

// boardctrl_startup() is defined in ports/esp32/main.c.
extern void boardctrl_startup(void);

void jackpack_startup(void) {
    // Standard ESP32 initialization (NVS, flash size detection).
    boardctrl_startup();

    // Early CAN addressing — runs before MicroPython VM.
    // TWAI driver stays installed for Python handoff.
    sai_early_addressing();
}

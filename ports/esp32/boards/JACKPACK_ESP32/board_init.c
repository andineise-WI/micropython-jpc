/*
 * JackPack ESP32 — Board Startup with Early CAN Addressing
 *
 * Starts SAI CAN auto-addressing immediately at boot, before any other
 * board initialization, because SAI modules boot in parallel with the
 * ESP32 and then wait for the address-assignment request. Running this
 * first ensures no bootup messages are missed.
 */

#include "sai_addressing.h"

// boardctrl_startup() is defined in ports/esp32/main.c.
extern void boardctrl_startup(void);

void jackpack_startup(void) {
    // Early CAN addressing — runs immediately after reset, before
    // NVS/flash/partition init, so we catch SAI module bootup messages.
    // TWAI driver stays installed for Python handoff.
    sai_early_addressing();

    // Standard ESP32 initialization (NVS, flash size detection) afterwards.
    boardctrl_startup();
}

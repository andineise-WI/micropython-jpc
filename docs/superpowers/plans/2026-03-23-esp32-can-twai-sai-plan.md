# ESP32 CAN/TWAI + SAI Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `machine.CAN` on ESP32 via TWAI driver, plus frozen `sai` module for Weidmüller SAI Subbus I/O module management.

**Architecture:** Three-layer stack. Bottom: C port implementation (`ports/esp32/machine_can.c`) using ESP-IDF `driver/twai.h`, plugged into existing `extmod/machine_can.c` abstraction. Middle: build system and config changes. Top: frozen Python `sai.py` module for SAI bootloader addressing and CANopen I/O access.

**Tech Stack:** C (ESP-IDF TWAI driver), MicroPython extmod port interface, Python (frozen module), CAN 2.0B / CANopen CiA 301/401.

**Spec:** `docs/superpowers/specs/2026-03-23-esp32-can-twai-sai-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `ports/esp32/machine_can.c` | CREATE | TWAI port: 15 static functions implementing `machine_can_port.h` |
| `ports/esp32/mpconfigport.h` | MODIFY | Enable CAN, set timing limits, macros |
| `ports/esp32/esp32_common.cmake` | MODIFY | Add `machine_can.c` to source list |
| `ports/esp32/main.c` | MODIFY | Add `machine_can_deinit_all()` to soft-reset path |
| `ports/esp32/modules/sai.py` | CREATE | SAI bus management: addressing, CANopen, I/O mapping |

---

## Phase 1: C-Level TWAI Driver

### Task 1: Add CAN configuration to mpconfigport.h

**Files:**
- Modify: `ports/esp32/mpconfigport.h` (after UART config block, around line 165)

- [ ] **Step 1: Add CAN config defines**

Insert after `#define MICROPY_PY_MACHINE_UART_IRQ (1)` line:

```c
#ifndef MICROPY_PY_MACHINE_CAN
#define MICROPY_PY_MACHINE_CAN              (SOC_TWAI_SUPPORTED)
#endif
#define MICROPY_PY_MACHINE_CAN_INCLUDEFILE  "ports/esp32/machine_can.c"
#define MICROPY_HW_NUM_CAN                  (1)
#define MICROPY_HW_CAN_IS_RESERVED(can_id)  (false)
```

- [ ] **Step 2: Commit**

```bash
git add ports/esp32/mpconfigport.h
git commit -m "esp32/can: add MICROPY_PY_MACHINE_CAN config to mpconfigport.h"
```

---

### Task 2: Add machine_can.c to CMake build

**Files:**
- Modify: `ports/esp32/esp32_common.cmake` (in MICROPY_SOURCE_PORT list, around line 140)

- [ ] **Step 1: Add machine_can.c to source list**

In the `list(APPEND MICROPY_SOURCE_PORT` block, add `machine_can.c` after `machine_sdcard.c`:

```cmake
    machine_sdcard.c
    machine_can.c
    modespnow.c
```

- [ ] **Step 2: Commit**

```bash
git add ports/esp32/esp32_common.cmake
git commit -m "esp32/can: add machine_can.c to CMake source list"
```

---

### Task 3: Create ports/esp32/machine_can.c — core structure and init/deinit

**Files:**
- Create: `ports/esp32/machine_can.c`

- [ ] **Step 1: Create the file with includes, defines, and port struct**

```c
/*
 * This file is part of the MicroPython project, http://micropython.org/
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2026 MicroPython contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

// This file is never compiled standalone, it's included directly from
// extmod/machine_can.c via MICROPY_PY_MACHINE_CAN_INCLUDEFILE.

#include <string.h>
#include "extmod/machine_can_port.h"
#include "py/runtime.h"
#include "py/mperrno.h"
#include "py/mphal.h"

#include "driver/twai.h"
#include "esp_clk_tree.h"
#include "soc/soc_caps.h"

// TWAI timing limits (SJA1000-compatible controller)
#define CAN_BRP_MIN 2
#define CAN_BRP_MAX 128
#define CAN_TX_QUEUE_LEN 1
#define CAN_HW_MAX_FILTER 2

// Fixed pin configuration
#define CAN_TX_GPIO  GPIO_NUM_5
#define CAN_RX_GPIO  GPIO_NUM_4

struct machine_can_port {
    bool installed;
    twai_filter_config_t filter_config;
    uint32_t alert_flags;
};

// --- Helper: Map MicroPython mode to TWAI mode ---
static twai_mode_t can_port_twai_mode(machine_can_mode_t mode) {
    switch (mode) {
        case MP_CAN_MODE_NORMAL:
            return TWAI_MODE_NORMAL;
        case MP_CAN_MODE_LOOPBACK:
            return TWAI_MODE_NO_ACK;  // TWAI "no ack" is closest to loopback
        case MP_CAN_MODE_SILENT:
            return TWAI_MODE_LISTEN_ONLY;
        case MP_CAN_MODE_SILENT_LOOPBACK:
            return TWAI_MODE_LISTEN_ONLY;
        default:
            return TWAI_MODE_NORMAL;
    }
}

static int machine_can_port_f_clock(const machine_can_obj_t *self) {
    // TWAI uses APB clock (80 MHz)
    uint32_t freq;
    esp_clk_tree_src_get_freq_hz(SOC_MOD_CLK_APB, ESP_CLK_TREE_SRC_FREQ_PRECISION_APPROX, &freq);
    return (int)freq;
}

static bool machine_can_port_supports_mode(const machine_can_obj_t *self, machine_can_mode_t mode) {
    // TWAI doesn't have a true sleep mode
    return mode != MP_CAN_MODE_SLEEP && mode < MP_CAN_MODE_MAX;
}

static mp_uint_t machine_can_port_max_data_len(mp_uint_t flags) {
    return 8;  // Classic CAN only
}

static void machine_can_port_init(machine_can_obj_t *self) {
    if (!self->port) {
        self->port = m_new(struct machine_can_port, 1);
        memset(self->port, 0, sizeof(struct machine_can_port));
        // Default: accept all messages
        self->port->filter_config = (twai_filter_config_t)TWAI_FILTER_CONFIG_ACCEPT_ALL();
    }

    // If already installed, stop and uninstall first
    if (self->port->installed) {
        twai_stop();
        twai_driver_uninstall();
        self->port->installed = false;
    }

    // BRP must be even on original ESP32
    int brp = self->brp;
    #if CONFIG_IDF_TARGET_ESP32
    if (brp & 1) {
        brp = (brp + 1) & ~1;  // Round up to even
        if (brp > CAN_BRP_MAX) {
            brp = CAN_BRP_MAX;
        }
    }
    #endif

    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, can_port_twai_mode(self->mode));
    g_config.tx_queue_len = 5;  // Internal ESP-IDF TX queue
    g_config.rx_queue_len = 10; // Internal ESP-IDF RX queue

    twai_timing_config_t t_config = {
        .brp = brp,
        .tseg_1 = self->tseg1,
        .tseg_2 = self->tseg2,
        .sjw = self->sjw,
        .triple_sampling = false,
    };

    esp_err_t err = twai_driver_install(&g_config, &t_config, &self->port->filter_config);
    if (err != ESP_OK) {
        mp_raise_msg_varg(&mp_type_OSError, MP_ERROR_TEXT("TWAI install failed: %d"), err);
    }

    err = twai_start();
    if (err != ESP_OK) {
        twai_driver_uninstall();
        mp_raise_msg_varg(&mp_type_OSError, MP_ERROR_TEXT("TWAI start failed: %d"), err);
    }

    self->port->installed = true;
}

static void machine_can_port_deinit(machine_can_obj_t *self) {
    if (self->port && self->port->installed) {
        twai_stop();
        twai_driver_uninstall();
        self->port->installed = false;
    }
}

static mp_int_t machine_can_port_send(machine_can_obj_t *self, mp_uint_t id, const byte *data, size_t data_len, mp_uint_t flags) {
    twai_message_t msg = {0};

    msg.identifier = id;
    msg.data_length_code = data_len;
    msg.extd = (flags & CAN_MSG_FLAG_EXT_ID) ? 1 : 0;
    msg.rtr = (flags & CAN_MSG_FLAG_RTR) ? 1 : 0;

    if (!(flags & CAN_MSG_FLAG_RTR)) {
        memcpy(msg.data, data, data_len);
    }

    esp_err_t err = twai_transmit(&msg, 0);  // Non-blocking (timeout=0)
    if (err == ESP_OK) {
        return 0;  // Return buffer index 0 (single logical queue)
    }
    return -1;  // Queue full or error
}

static bool machine_can_port_cancel_send(machine_can_obj_t *self, mp_uint_t idx) {
    // TWAI only supports clearing entire TX queue
    return twai_clear_transmit_queue() == ESP_OK;
}

static bool machine_can_port_recv(machine_can_obj_t *self, void *data, size_t *dlen, mp_uint_t *id, mp_uint_t *flags, mp_uint_t *errors) {
    twai_message_t msg;

    esp_err_t err = twai_receive(&msg, 0);  // Non-blocking (timeout=0)
    if (err != ESP_OK) {
        return false;  // No message available
    }

    *id = msg.identifier;
    *dlen = msg.data_length_code;
    *flags = 0;
    if (msg.extd) {
        *flags |= CAN_MSG_FLAG_EXT_ID;
    }
    if (msg.rtr) {
        *flags |= CAN_MSG_FLAG_RTR;
    }

    if (!msg.rtr) {
        memcpy(data, msg.data, msg.data_length_code);
    }

    *errors = self->rx_error_flags;
    self->rx_error_flags = 0;

    return true;
}

static machine_can_state_t machine_can_port_get_state(machine_can_obj_t *self) {
    twai_status_info_t status;
    if (twai_get_status_info(&status) != ESP_OK) {
        return MP_CAN_STATE_STOPPED;
    }

    switch (status.state) {
        case TWAI_STATE_STOPPED:
            return MP_CAN_STATE_STOPPED;
        case TWAI_STATE_RUNNING:
            // Check error counters for warning/passive
            if (status.tx_error_counter >= 128 || status.rx_error_counter >= 128) {
                return MP_CAN_STATE_PASSIVE;
            } else if (status.tx_error_counter >= 96 || status.rx_error_counter >= 96) {
                return MP_CAN_STATE_WARNING;
            }
            return MP_CAN_STATE_ACTIVE;
        case TWAI_STATE_BUS_OFF:
            return MP_CAN_STATE_BUS_OFF;
        case TWAI_STATE_RECOVERING:
            return MP_CAN_STATE_BUS_OFF;
        default:
            return MP_CAN_STATE_STOPPED;
    }
}

static void machine_can_port_update_counters(machine_can_obj_t *self) {
    twai_status_info_t status;
    if (twai_get_status_info(&status) != ESP_OK) {
        return;
    }

    machine_can_counters_t *counters = &self->counters;
    counters->tec = status.tx_error_counter;
    counters->rec = status.rx_error_counter;
    counters->tx_pending = status.msgs_to_tx;
    counters->rx_pending = status.msgs_to_rx;
    // num_warning, num_passive, num_bus_off, rx_overruns are updated from alerts
}

static void machine_can_port_restart(machine_can_obj_t *self) {
    if (self->port && self->port->installed) {
        // Try bus recovery first (for bus-off state)
        twai_status_info_t status;
        if (twai_get_status_info(&status) == ESP_OK && status.state == TWAI_STATE_BUS_OFF) {
            twai_initiate_recovery();
            return;
        }
        // Otherwise full restart
        twai_stop();
        twai_start();
    }
}

static void machine_can_port_clear_filters(machine_can_obj_t *self) {
    if (self->port) {
        self->port->filter_config = (twai_filter_config_t)TWAI_FILTER_CONFIG_ACCEPT_ALL();
    }
}

static void machine_can_port_set_filter(machine_can_obj_t *self, int filter_idx, mp_uint_t can_id, mp_uint_t mask, mp_uint_t flags) {
    if (filter_idx >= CAN_HW_MAX_FILTER) {
        mp_raise_ValueError(MP_ERROR_TEXT("too many filters"));
    }

    // TWAI acceptance filter uses single 32-bit filter
    // For accept-all (mask=0), just keep the default
    if (mask == 0 && can_id == 0) {
        // Accept all — already set by clear_filters
        return;
    }

    // Build single acceptance filter
    // TWAI uses a single filter with acceptance_code and acceptance_mask
    // Bits set to 0 in mask = "must match", bits set to 1 = "don't care"
    if (flags & CAN_MSG_FLAG_EXT_ID) {
        // Extended ID: 29 bits in upper bits of 32-bit register
        self->port->filter_config.acceptance_code = can_id << 3;
        self->port->filter_config.acceptance_mask = ~(mask << 3);
        self->port->filter_config.single_filter = true;
    } else {
        // Standard ID: 11 bits in upper bits of 32-bit register
        self->port->filter_config.acceptance_code = can_id << 21;
        self->port->filter_config.acceptance_mask = ~(mask << 21);
        self->port->filter_config.single_filter = true;
    }

    // Filters are applied on next init/reinit
    // If driver is already running, we need to reinstall
    if (self->port->installed) {
        twai_stop();
        twai_driver_uninstall();
        self->port->installed = false;
        machine_can_port_init(self);
    }
}

static void machine_can_update_irqs(machine_can_obj_t *self) {
    if (!self->port || !self->port->installed) {
        return;
    }

    uint32_t alerts = 0;
    uint16_t triggers = self->mp_irq_trigger;

    if (triggers & MP_CAN_IRQ_RX) {
        alerts |= TWAI_ALERT_RX_DATA | TWAI_ALERT_RX_QUEUE_FULL;
    }
    if (triggers & MP_CAN_IRQ_TX) {
        alerts |= TWAI_ALERT_TX_SUCCESS;
    }
    if (triggers & MP_CAN_IRQ_TX_FAILED) {
        alerts |= TWAI_ALERT_TX_FAILED;
    }
    if (triggers & MP_CAN_IRQ_STATE) {
        alerts |= TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF |
                  TWAI_ALERT_ABOVE_ERR_WARN | TWAI_ALERT_RECOVERY_IN_PROGRESS;
    }

    twai_reconfigure_alerts(alerts, NULL);
}

static mp_uint_t machine_can_port_irq_flags(machine_can_obj_t *self) {
    mp_uint_t result = 0;
    uint32_t alerts = 0;

    if (twai_read_alerts(&alerts, 0) != ESP_OK) {
        return 0;
    }

    if (alerts & TWAI_ALERT_RX_DATA) {
        result |= MP_CAN_IRQ_RX;
    }
    if (alerts & TWAI_ALERT_TX_SUCCESS) {
        result |= MP_CAN_IRQ_TX;
    }
    if (alerts & TWAI_ALERT_TX_FAILED) {
        result |= MP_CAN_IRQ_TX_FAILED;
    }
    if (alerts & (TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF | TWAI_ALERT_ABOVE_ERR_WARN)) {
        result |= MP_CAN_IRQ_STATE;
    }

    // Update overrun counter
    if (alerts & TWAI_ALERT_RX_QUEUE_FULL) {
        self->rx_error_flags |= CAN_RECV_ERR_FULL;
        self->counters.rx_overruns++;
    }

    // Update state transition counters
    if (alerts & TWAI_ALERT_ABOVE_ERR_WARN) {
        self->counters.num_warning++;
    }
    if (alerts & TWAI_ALERT_ERR_PASS) {
        self->counters.num_passive++;
    }
    if (alerts & TWAI_ALERT_BUS_OFF) {
        self->counters.num_bus_off++;
    }

    return result;
}

static mp_obj_t machine_can_port_get_additional_timings(machine_can_obj_t *self, mp_obj_t optional_arg) {
    return mp_const_none;
}
```

- [ ] **Step 2: Commit**

```bash
git add ports/esp32/machine_can.c
git commit -m "esp32/can: add TWAI port implementation of machine.CAN"
```

---

### Task 4: Add CAN deinit to soft-reset path in main.c

**Files:**
- Modify: `ports/esp32/main.c` (soft_reset_exit section, around line 221)

- [ ] **Step 1: Add machine_can_deinit_all() call**

Insert after the `machine_pwm_deinit_all()` block (around line 222):

```c
    #if MICROPY_PY_MACHINE_CAN
    machine_can_deinit_all();
    #endif
```

Also add the include near the top of the file (after existing includes):

```c
#if MICROPY_PY_MACHINE_CAN
#include "extmod/machine_can.h"
#endif
```

- [ ] **Step 2: Commit**

```bash
git add ports/esp32/main.c
git commit -m "esp32/can: add CAN deinit to soft-reset path"
```

---

### Task 5: Build verification (loopback test)

- [ ] **Step 1: Build the ESP32 firmware**

```bash
cd ports/esp32
idf.py -D MICROPY_BOARD=ESP32_GENERIC build
```

Expected: Build completes without errors.

- [ ] **Step 2: Verify CAN is compiled in**

Check the build output for `machine_can` symbols:

```bash
grep -c "machine_can" build-ESP32_GENERIC/micropython.map
```

Expected: Multiple matches (confirming CAN code is linked).

- [ ] **Step 3: Commit build verification note**

No code changes needed — this is a verification step.

---

## Phase 2: SAI Bus Frozen Python Module

### Task 6: Create sai.py — SAIBus class with CAN init and module discovery

**Files:**
- Create: `ports/esp32/modules/sai.py`

- [ ] **Step 1: Create sai.py with SAIBus and SAIModule**

```python
"""SAI Subbus module management for Weidmüller/Heyfra SAI I/O modules.

Handles module discovery (bootloader addressing), CANopen NMT/SDO/PDO,
and provides a high-level I/O API.

Usage:
    from sai import SAIBus
    bus = SAIBus()
    bus.start_operational()
    # Read digital input from module 1, channel 3
    val = bus.modules[0].digital_read(3)
"""

import time
from machine import CAN

# CANopen & SAI protocol constants
_NMT_ID = 0x000
_SDO_TX_BASE = 0x600   # ESP32 → Module
_SDO_RX_BASE = 0x580   # Module → ESP32
_TPDO1_BASE = 0x180     # Module → ESP32
_TPDO2_BASE = 0x280
_RPDO1_BASE = 0x200     # ESP32 → Module
_HEARTBEAT_BASE = 0x700
_BOOTLOADER_TX = 0x7FE
_BOOTLOADER_RX = 0x7FF
_APP_START_BROADCAST = 0x77F

# NMT commands
_NMT_START = 0x01
_NMT_STOP = 0x02
_NMT_PRE_OPERATIONAL = 0x80
_NMT_RESET_NODE = 0x81
_NMT_RESET_COMM = 0x82

# SDO command specifiers
_SDO_READ_REQ = 0x40
_SDO_WRITE_1BYTE = 0x2F
_SDO_WRITE_2BYTE = 0x2B
_SDO_WRITE_4BYTE = 0x23

# Module types (from CANopen Device Type object 0x1000)
_MODULE_TYPES = {
    0x00020191: '8DI',
    0x00020192: '8DO',
    0x00020193: '8DIO',
    0x00020194: '4AI',
    0x00020195: '4AO',
    0x00020196: 'PT100',
    0x00020197: 'CNT',
}

# Timeout constants (seconds)
_BOOT_TIMEOUT = 1.0
_SDO_TIMEOUT = 0.5
_HEARTBEAT_TIMEOUT = 3.0
_CAN_SEND_DELAY = 0.01


class SAIBus:
    """Manages all SAI modules on the CAN bus."""

    def __init__(self, can_id=1, bitrate=250000, modules=None):
        """Initialize CAN bus and discover all SAI modules.

        Args:
            can_id: CAN controller ID (1-based)
            bitrate: CAN baudrate (default 250000)
            modules: Optional list of module type strings for manual config.
                     If None, auto-detect via SDO query after boot.
        """
        self._can = CAN(can_id, bitrate=bitrate)
        self._can.set_filters(None)  # Accept all
        self._modules = []
        self._manual_types = modules
        self._scan()

    def _send(self, can_id, data):
        """Send a CAN message and wait briefly."""
        self._can.send(id=can_id, data=bytes(data))
        time.sleep(_CAN_SEND_DELAY)

    def _recv(self, timeout_ms=100):
        """Receive a CAN message with timeout.

        Returns (id, data_bytes) or None.
        """
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            msg = self._can.recv()
            if msg is not None:
                msg_id = msg[0]
                data = bytes(msg[1])
                return (msg_id, data)
            time.sleep_ms(1)
        return None

    def _recv_id(self, expected_id, timeout_ms=1000):
        """Receive a message with specific CAN ID, within timeout."""
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            msg = self._recv(timeout_ms=50)
            if msg and msg[0] == expected_id:
                return msg
        return None

    def _scan(self):
        """Run SAI bootloader discovery and addressing."""
        self._modules = []
        node_id = 1

        # Wait for first module bootup
        msg = self._recv_id(_BOOTLOADER_RX, timeout_ms=3000)
        if msg is None or msg[1][0] != 0x01:
            print("SAI: No modules found")
            return

        while True:
            # Assign address
            print("SAI: Assigning node_id", node_id)
            self._send(_BOOTLOADER_TX, [0x81, node_id])

            # Wait for ACK
            msg = self._recv_id(_BOOTLOADER_RX, timeout_ms=1000)
            if msg is None or msg[1][0] != 0x81:
                print("SAI: Address ACK failed for node", node_id)
                break

            # Switch on next module
            self._send(_BOOTLOADER_TX, [0x82, node_id])

            # Wait for ACK
            msg = self._recv_id(_BOOTLOADER_RX, timeout_ms=1000)
            if msg is None or msg[1][0] != 0x82:
                print("SAI: Switch-on ACK failed for node", node_id)
                break

            # Module addressed successfully
            self._modules.append(SAIModule(self, node_id, None))
            node_id += 1

            # Wait for next module bootup (with timeout)
            msg = self._recv_id(_BOOTLOADER_RX, timeout_ms=int(_BOOT_TIMEOUT * 1000))
            if msg is None or msg[1][0] != 0x01:
                # No more modules
                break

        print("SAI: Found", len(self._modules), "modules")

        # Start application on all modules
        self._send(_APP_START_BROADCAST, [0x7F])
        for mod in self._modules:
            self._send(_BOOTLOADER_TX, [0x83, mod.node_id])
        self._send(_APP_START_BROADCAST, [0x7F])

        time.sleep(0.5)  # Wait for applications to start

        # Detect module types
        if self._manual_types:
            for i, mod in enumerate(self._modules):
                if i < len(self._manual_types):
                    mod._type = self._manual_types[i]
        else:
            for mod in self._modules:
                mod._detect_type()

    def scan(self):
        """Re-scan for modules. Returns list of SAIModule objects."""
        self._scan()
        return self._modules

    @property
    def modules(self):
        """List of discovered SAIModule objects."""
        return self._modules

    @property
    def can(self):
        """Underlying machine.CAN object."""
        return self._can

    def start_operational(self):
        """Send NMT Start to all nodes -> Operational state."""
        self._send(_NMT_ID, [_NMT_START, 0x00])
        print("SAI: All modules set to Operational")

    def stop(self):
        """Send NMT Stop to all nodes -> Pre-Operational state."""
        self._send(_NMT_ID, [_NMT_STOP, 0x00])

    def update(self):
        """Poll CAN bus, process incoming PDOs and heartbeats.

        Calls can.recv() in a loop until None (no more pending messages).
        Must be called regularly from the main loop.
        """
        while True:
            msg = self._can.recv()
            if msg is None:
                break

            msg_id = msg[0]
            data = bytes(msg[1])

            # Dispatch by COB-ID function code
            if msg_id >= _TPDO1_BASE and msg_id < _TPDO1_BASE + 0x80:
                node_id = msg_id - _TPDO1_BASE
                mod = self._get_module(node_id)
                if mod:
                    mod._process_tpdo1(data)

            elif msg_id >= _TPDO2_BASE and msg_id < _TPDO2_BASE + 0x80:
                node_id = msg_id - _TPDO2_BASE
                mod = self._get_module(node_id)
                if mod:
                    mod._process_tpdo2(data)

            elif msg_id >= _HEARTBEAT_BASE and msg_id < _HEARTBEAT_BASE + 0x80:
                node_id = msg_id - _HEARTBEAT_BASE
                mod = self._get_module(node_id)
                if mod:
                    mod._last_heartbeat = time.ticks_ms()

        # Send pending RPDO outputs
        for mod in self._modules:
            mod._send_outputs()

    def _get_module(self, node_id):
        """Find module by node_id."""
        for mod in self._modules:
            if mod.node_id == node_id:
                return mod
        return None


class SAIModule:
    """Represents a single SAI Subbus module."""

    def __init__(self, bus, node_id, module_type):
        self._bus = bus
        self._node_id = node_id
        self._type = module_type
        self._last_heartbeat = time.ticks_ms()
        # Cached I/O data
        self._di_byte = 0          # Digital inputs (from TPDO)
        self._do_byte = 0          # Digital outputs (for RPDO)
        self._do_changed = False
        self._ai = [0, 0, 0, 0]   # Analog inputs (from TPDO)
        self._ao = [0, 0, 0, 0]   # Analog outputs (for RPDO)
        self._ao_changed = False
        self._counters = [0, 0, 0, 0]  # Counter values

    @property
    def node_id(self):
        return self._node_id

    @property
    def module_type(self):
        return self._type

    @property
    def alive(self):
        """True if heartbeat received within timeout."""
        return time.ticks_diff(time.ticks_ms(), self._last_heartbeat) < _HEARTBEAT_TIMEOUT * 1000

    def _detect_type(self):
        """Read Device Type (0x1000) via SDO to determine module type."""
        try:
            data = self.sdo_read(0x1000, 0x00)
            if data and len(data) >= 4:
                dev_type = int.from_bytes(data[:4], 'little')
                self._type = _MODULE_TYPES.get(dev_type, 'UNKNOWN')
            else:
                self._type = 'UNKNOWN'
        except OSError:
            self._type = 'UNKNOWN'
        print("SAI: Node", self._node_id, "type:", self._type)

    # --- Digital I/O ---
    def digital_read(self, channel):
        """Read a single digital input (0-7)."""
        if channel < 0 or channel > 7:
            raise ValueError("channel must be 0-7")
        return bool(self._di_byte & (1 << channel))

    def digital_read_byte(self):
        """Read all 8 digital inputs as byte."""
        return self._di_byte

    def digital_write(self, channel, value):
        """Set a single digital output (0-7)."""
        if channel < 0 or channel > 7:
            raise ValueError("channel must be 0-7")
        if value:
            self._do_byte |= (1 << channel)
        else:
            self._do_byte &= ~(1 << channel)
        self._do_changed = True

    def digital_write_byte(self, value):
        """Set all 8 digital outputs as byte."""
        self._do_byte = value & 0xFF
        self._do_changed = True

    # --- Analog I/O ---
    def analog_read(self, channel):
        """Read analog input (0-3), returns raw 16-bit PDO value."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        return self._ai[channel]

    def analog_write(self, channel, value):
        """Write analog output (0-3), raw 16-bit PDO value."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        self._ao[channel] = value & 0xFFFF
        self._ao_changed = True

    # --- PT100 ---
    def temperature_read(self, channel):
        """Read temperature in °C (resolution 0.1K)."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        raw = self._ai[channel]
        # Value is in 1/10 K units, signed 16-bit
        if raw > 0x7FFF:
            raw -= 0x10000
        return raw / 10.0

    def resistance_read(self, channel):
        """Read raw resistance value."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        return self._ai[channel]

    # --- Counter ---
    def counter_read(self, channel):
        """Read counter value."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        return self._counters[channel]

    def counter_reset(self, channel):
        """Reset counter to 0 via SDO."""
        if channel < 0 or channel > 3:
            raise ValueError("channel must be 0-3")
        self.sdo_write(0x2102, channel + 1, bytes([0x01]))  # Control byte: reset

    # --- SDO Access ---
    def sdo_read(self, index, subindex):
        """Read SDO object. Returns bytes or raises OSError on timeout."""
        msg = [_SDO_READ_REQ,
               index & 0xFF, (index >> 8) & 0xFF,
               subindex,
               0, 0, 0, 0]
        self._bus._send(_SDO_TX_BASE + self._node_id, msg)

        # Wait for response
        resp = self._bus._recv_id(_SDO_RX_BASE + self._node_id,
                                   timeout_ms=int(_SDO_TIMEOUT * 1000))
        if resp is None:
            raise OSError("SDO timeout")

        data = resp[1]
        # Check for SDO abort
        if data[0] == 0x80:
            raise OSError("SDO abort: 0x{:08X}".format(
                int.from_bytes(data[4:8], 'little')))

        # Return data bytes (4 bytes payload)
        return bytes(data[4:8])

    def sdo_write(self, index, subindex, data):
        """Write SDO object."""
        if len(data) == 1:
            cmd = _SDO_WRITE_1BYTE
        elif len(data) == 2:
            cmd = _SDO_WRITE_2BYTE
        elif len(data) <= 4:
            cmd = _SDO_WRITE_4BYTE
        else:
            raise ValueError("SDO data max 4 bytes")

        msg = bytearray(8)
        msg[0] = cmd
        msg[1] = index & 0xFF
        msg[2] = (index >> 8) & 0xFF
        msg[3] = subindex
        for i in range(len(data)):
            msg[4 + i] = data[i]

        self._bus._send(_SDO_TX_BASE + self._node_id, msg)

        # Wait for confirmation
        resp = self._bus._recv_id(_SDO_RX_BASE + self._node_id,
                                   timeout_ms=int(_SDO_TIMEOUT * 1000))
        if resp is None:
            raise OSError("SDO timeout")

        data = resp[1]
        if data[0] == 0x80:
            raise OSError("SDO abort: 0x{:08X}".format(
                int.from_bytes(data[4:8], 'little')))

    # --- Internal: PDO processing ---
    def _process_tpdo1(self, data):
        """Process TPDO1 data from module."""
        t = self._type
        if t in ('8DI', '8DIO'):
            if len(data) >= 1:
                self._di_byte = data[0]
        elif t in ('4AI', 'PT100'):
            # 4 x 16-bit values
            for i in range(min(4, len(data) // 2)):
                self._ai[i] = data[2 * i] | (data[2 * i + 1] << 8)
        elif t == 'CNT':
            # Counter values in TPDO1
            for i in range(min(4, len(data) // 2)):
                self._counters[i] = data[2 * i] | (data[2 * i + 1] << 8)

    def _process_tpdo2(self, data):
        """Process TPDO2 data from module (status/diagnostics)."""
        # TPDO2 typically contains diagnostic data — store for future use
        pass

    def _send_outputs(self):
        """Send pending RPDO outputs if changed."""
        if self._do_changed and self._type in ('8DO', '8DIO'):
            self._bus._send(_RPDO1_BASE + self._node_id, [self._do_byte])
            self._do_changed = False

        if self._ao_changed and self._type == '4AO':
            data = bytearray(8)
            for i in range(4):
                data[2 * i] = self._ao[i] & 0xFF
                data[2 * i + 1] = (self._ao[i] >> 8) & 0xFF
            self._bus._send(_RPDO1_BASE + self._node_id, data)
            self._ao_changed = False
```

- [ ] **Step 2: Commit**

```bash
git add ports/esp32/modules/sai.py
git commit -m "esp32/sai: add frozen SAI Subbus management module"
```

---

### Task 7: Integration verification

- [ ] **Step 1: Rebuild firmware with frozen module**

```bash
cd ports/esp32
idf.py -D MICROPY_BOARD=ESP32_GENERIC build
```

Expected: Build succeeds, frozen module is included.

- [ ] **Step 2: Verify sai module is importable**

Flash to ESP32 and test in REPL:

```python
from machine import CAN
from sai import SAIBus
print("CAN and SAI modules available")
```

Expected: No import errors.

- [ ] **Step 3: Test CAN loopback (without SAI hardware)**

```python
from machine import CAN
can = CAN(1, bitrate=250000, mode=CAN.MODE_LOOPBACK)
can.send(id=0x123, data=b'\x01\x02\x03')
msg = can.recv()
print(msg)  # Should show [0x123, memoryview(b'\x01\x02\x03'), 0, 0]
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "esp32/can: integration verified — machine.CAN + SAI module complete"
```

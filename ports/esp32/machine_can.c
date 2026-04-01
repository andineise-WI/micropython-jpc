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

#if defined(MICROPY_BOARD_JACKPACK_SAI)
#include "sai_addressing.h"
#endif

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
            return TWAI_MODE_NO_ACK;
        case MP_CAN_MODE_SILENT:
            return TWAI_MODE_LISTEN_ONLY;
        case MP_CAN_MODE_SILENT_LOOPBACK:
            return TWAI_MODE_LISTEN_ONLY;
        default:
            return TWAI_MODE_NORMAL;
    }
}

static int machine_can_port_f_clock(const machine_can_obj_t *self) {
    uint32_t freq;
    esp_clk_tree_src_get_freq_hz(SOC_MOD_CLK_APB, ESP_CLK_TREE_SRC_FREQ_PRECISION_APPROX, &freq);
    return (int)freq;
}

static bool machine_can_port_supports_mode(const machine_can_obj_t *self, machine_can_mode_t mode) {
    return mode != MP_CAN_MODE_SLEEP && mode < MP_CAN_MODE_MAX;
}

static mp_uint_t machine_can_port_max_data_len(mp_uint_t flags) {
    return 8;
}

static void machine_can_port_init(machine_can_obj_t *self) {
    if (!self->port) {
        self->port = m_new(struct machine_can_port, 1);
        memset(self->port, 0, sizeof(struct machine_can_port));
        self->port->filter_config = (twai_filter_config_t)TWAI_FILTER_CONFIG_ACCEPT_ALL();
    }

    // If SAI early addressing left TWAI installed, take over without reinstalling.
    #if defined(MICROPY_BOARD_JACKPACK_SAI)
    if (sai_addressing_result.twai_installed && !self->port->installed) {
        self->port->installed = true;
        sai_addressing_result.twai_installed = false;  // Handoff complete.

        // Drain any leftover messages from the addressing phase.
        twai_message_t drain_msg;
        while (twai_receive(&drain_msg, 0) == ESP_OK) {
            // discard
        }
        return;
    }
    #endif

    // If already installed, stop and uninstall first
    if (self->port->installed) {
        twai_stop();
        twai_driver_uninstall();
        self->port->installed = false;
    }

    // BRP must be even on original ESP32 (SJA1000 limitation)
    int brp = self->brp;
    #if CONFIG_IDF_TARGET_ESP32
    if (brp & 1) {
        brp = (brp + 1) & ~1;
        if (brp > CAN_BRP_MAX) {
            brp = CAN_BRP_MAX;
        }
    }
    #endif

    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, can_port_twai_mode(self->mode));
    g_config.tx_queue_len = 5;
    g_config.rx_queue_len = 10;

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

    esp_err_t err = twai_transmit(&msg, 0);
    if (err == ESP_OK) {
        return 0;
    }
    return -1;
}

static bool machine_can_port_cancel_send(machine_can_obj_t *self, mp_uint_t idx) {
    return twai_clear_transmit_queue() == ESP_OK;
}

static bool machine_can_port_recv(machine_can_obj_t *self, void *data, size_t *dlen, mp_uint_t *id, mp_uint_t *flags, mp_uint_t *errors) {
    twai_message_t msg;

    esp_err_t err = twai_receive(&msg, 0);
    if (err != ESP_OK) {
        return false;
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
}

static void machine_can_port_restart(machine_can_obj_t *self) {
    if (self->port && self->port->installed) {
        twai_status_info_t status;
        if (twai_get_status_info(&status) == ESP_OK && status.state == TWAI_STATE_BUS_OFF) {
            twai_initiate_recovery();
            return;
        }
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

    // Accept-all case (mask=0, id=0)
    if (mask == 0 && can_id == 0) {
        return;
    }

    if (flags & CAN_MSG_FLAG_EXT_ID) {
        self->port->filter_config.acceptance_code = can_id << 3;
        self->port->filter_config.acceptance_mask = ~(mask << 3);
        self->port->filter_config.single_filter = true;
    } else {
        self->port->filter_config.acceptance_code = can_id << 21;
        self->port->filter_config.acceptance_mask = ~(mask << 21);
        self->port->filter_config.single_filter = true;
    }

    // Filters require driver reinstall to take effect
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

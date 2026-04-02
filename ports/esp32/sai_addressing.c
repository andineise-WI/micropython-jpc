/*
 * SAI CAN Auto-Addressing — Early Boot Module Discovery
 *
 * Implements the SAI bootloader addressing protocol in C so it runs
 * before the MicroPython VM, ensuring no bootup messages are missed.
 *
 * Protocol (from working Python reference):
 *   1. Wait for bootup message on 0x7FF with data[0]==0x01
 *   2. Assign address: send 0x7FE [0x81, node_id]
 *   3. Wait for ACK: 0x7FF with data[0]==0x81
 *   4. Switch-on: send 0x7FE [0x82, node_id]
 *   5. Wait for ACK: 0x7FF with data[0]==0x82
 *   6. Wait for next bootup or 1s silence → addressing done
 *   7. App-start broadcast: 0x77F [0x7F] + 0x7FE [0x83, nid] per module
 *
 * No NMT reset is sent. TWAI driver stays installed for Python handoff.
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/twai.h"
#include "esp_log.h"

#include "sai_addressing.h"

static const char *TAG = "SAI_ADDR";

// Global result — read by Python after boot.
sai_addressing_result_t sai_addressing_result = {
    .count = 0,
    .node_ids = {0},
    .addressing_done = false,
    .twai_installed = false,
    .last_state = 0,
    .elapsed_ms = 0,
    .error_count = 0,
};

// GPIO pins for CAN transceiver (ESP32-PICO-V3-02 JackPack hardware).
#define SAI_CAN_TX_GPIO  GPIO_NUM_5
#define SAI_CAN_RX_GPIO  GPIO_NUM_4

// --- Internal helpers ---

static esp_err_t sai_twai_init(void) {
    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(
        SAI_CAN_TX_GPIO, SAI_CAN_RX_GPIO, TWAI_MODE_NORMAL);
    g_config.tx_queue_len = 5;
    g_config.rx_queue_len = 10;

    // 250 kbps timing for 80 MHz APB clock.
    // BRP=16, TSEG1=15, TSEG2=4 → 250kbps, 80% sample point.
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_250KBITS();

    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    esp_err_t err = twai_driver_install(&g_config, &t_config, &f_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "TWAI install failed: %d", (int)err);
        return err;
    }

    err = twai_start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "TWAI start failed: %d", (int)err);
        twai_driver_uninstall();
        return err;
    }

    return ESP_OK;
}

// Send a 2-byte message on the bootloader TX ID (0x7FE).
static bool sai_send_cmd(uint8_t cmd, uint8_t node_id) {
    twai_message_t msg = {0};
    msg.identifier = SAI_BOOTLOADER_TX;
    msg.data_length_code = 2;
    msg.data[0] = cmd;
    msg.data[1] = node_id;

    esp_err_t err = twai_transmit(&msg, pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "TX failed cmd=0x%02X nid=%d err=%d", cmd, node_id, (int)err);
        return false;
    }
    return true;
}

// Send app-start broadcast on 0x77F.
static bool sai_send_app_start_broadcast(void) {
    twai_message_t msg = {0};
    msg.identifier = SAI_APP_START_BROADCAST;
    msg.data_length_code = 1;
    msg.data[0] = SAI_CMD_APP_START_BC;

    esp_err_t err = twai_transmit(&msg, pdMS_TO_TICKS(100));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "TX app-start broadcast failed: %d", (int)err);
        return false;
    }
    return true;
}

// Try to receive a message with timeout (ms). Returns true if received.
static bool sai_recv(twai_message_t *out_msg, uint32_t timeout_ms) {
    esp_err_t err = twai_receive(out_msg, pdMS_TO_TICKS(timeout_ms));
    return (err == ESP_OK);
}

// Wait for app-start response: 0x7FF [0x83, Addr, status].
static void sai_wait_app_start_ack(uint8_t node_id, uint16_t *errors) {
    twai_message_t rx_msg;
    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(150);

    while (xTaskGetTickCount() < deadline) {
        if (!sai_recv(&rx_msg, 20)) {
            continue;
        }

        if (rx_msg.identifier != SAI_BOOTLOADER_RX || rx_msg.data_length_code < 3) {
            continue;
        }

        if (rx_msg.data[0] == SAI_CMD_APP_START && rx_msg.data[1] == node_id) {
            if (rx_msg.data[2] == 0x00) {
                ESP_LOGI(TAG, "App-start ACK OK for #%d", node_id);
            } else {
                (*errors)++;
                ESP_LOGW(TAG, "App-start ACK error for #%d code=0x%02X", node_id, rx_msg.data[2]);
            }
            return;
        }
    }

    (*errors)++;
    ESP_LOGW(TAG, "No app-start ACK for #%d", node_id);
}

// --- Main addressing state machine ---

// State definitions matching the Python reference:
//   0 = waiting for bootup (0x01)
//   1 = send assign address (0x81)
//   2 = waiting for assign ACK (0x81)
//   3 = send switch-on (0x82)
//   4 = waiting for switch-on ACK (0x82)
//   5 = waiting for next bootup or silence timeout
//   6 = addressing complete, run app-start

void sai_early_addressing(void) {
    ESP_LOGI(TAG, "Starting early CAN addressing (GPIO TX=%d RX=%d)",
             SAI_CAN_TX_GPIO, SAI_CAN_RX_GPIO);

    // Initialize TWAI driver.
    if (sai_twai_init() != ESP_OK) {
        ESP_LOGE(TAG, "TWAI init failed, skipping addressing");
        sai_addressing_result.addressing_done = true;
        return;
    }
    sai_addressing_result.twai_installed = true;

    int state = 0;
    uint8_t module_cnt = 1;
    int assign_retries = 0;
    TickType_t start_tick = xTaskGetTickCount();
    TickType_t last_activity = start_tick;
    twai_message_t rx_msg;
    uint16_t errors = 0;

    ESP_LOGI(TAG, "Waiting for SAI module bootup messages...");

    while (true) {
        TickType_t now = xTaskGetTickCount();

        // Safety net: total timeout.
        if ((now - start_tick) > pdMS_TO_TICKS(SAI_TOTAL_TIMEOUT_MS)) {
            ESP_LOGW(TAG, "Total timeout (%d ms), ending addressing", SAI_TOTAL_TIMEOUT_MS);
            break;
        }

        // State 0: Wait up to SAI_INITIAL_WAIT_MS for first bootup.
        if (state == 0) {
            if (sai_recv(&rx_msg, 50)) {
                if (rx_msg.identifier == SAI_BOOTLOADER_RX &&
                    rx_msg.data_length_code >= 1 &&
                    rx_msg.data[0] == SAI_CMD_BOOTUP) {
                    ESP_LOGI(TAG, "Bootup from module #%d", module_cnt);
                    last_activity = xTaskGetTickCount();
                    state = 1;
                }
            } else {
                // No message — check if initial wait period has elapsed.
                if ((now - start_tick) > pdMS_TO_TICKS(SAI_INITIAL_WAIT_MS)) {
                    ESP_LOGI(TAG, "No bootup after %d ms, assigning address directly", SAI_INITIAL_WAIT_MS);
                    last_activity = xTaskGetTickCount();
                    state = 1;
                }
            }
            continue;
        }

        // State 1: Send assign address command.
        if (state == 1) {
            if (assign_retries >= SAI_MAX_ASSIGN_RETRIES) {
                ESP_LOGW(TAG, "No response after %d assign attempts for #%d, giving up",
                         SAI_MAX_ASSIGN_RETRIES, module_cnt);
                break;
            }
            ESP_LOGI(TAG, "-> Assign address #%d (attempt %d/%d)",
                     module_cnt, assign_retries + 1, SAI_MAX_ASSIGN_RETRIES);
            if (sai_send_cmd(SAI_CMD_ASSIGN_ADDR, module_cnt)) {
                last_activity = xTaskGetTickCount();
                assign_retries++;
                state = 2;
            } else {
                errors++;
                assign_retries++;
                vTaskDelay(pdMS_TO_TICKS(10));
            }
            continue;
        }

        // State 2: Wait for assign ACK (0x81).
        if (state == 2) {
            if (sai_recv(&rx_msg, 100)) {
                if (rx_msg.identifier == SAI_BOOTLOADER_RX &&
                    rx_msg.data_length_code >= 2) {
                    if (rx_msg.data[0] == SAI_CMD_ASSIGN_ADDR && rx_msg.data[1] == module_cnt) {
                        ESP_LOGI(TAG, "Address ACK for #%d", module_cnt);
                        last_activity = xTaskGetTickCount();
                        state = 3;
                        continue;
                    }
                    if (rx_msg.data[0] == SAI_CMD_ASSIGN_ADDR) {
                        ESP_LOGW(TAG, "Address ACK for wrong node: got=%d expected=%d",
                                 rx_msg.data[1], module_cnt);
                        continue;
                    }
                    // Late bootup while waiting for ACK → retry assign.
                    if (rx_msg.data[0] == SAI_CMD_BOOTUP) {
                        ESP_LOGI(TAG, "Late bootup for #%d, retrying assign", module_cnt);
                        last_activity = xTaskGetTickCount();
                        state = 1;
                        continue;
                    }
                }
            } else {
                // ACK timeout — retry assign.
                errors++;
                ESP_LOGW(TAG, "No ACK (assign) for #%d, retry %d/%d",
                         module_cnt, assign_retries, SAI_MAX_ASSIGN_RETRIES);
                state = 1;
            }
            continue;
        }

        // State 3: Send switch-on command.
        if (state == 3) {
            ESP_LOGI(TAG, "-> Switch-on #%d", module_cnt);
            if (sai_send_cmd(SAI_CMD_SWITCH_ON, module_cnt)) {
                last_activity = xTaskGetTickCount();
                state = 4;
            } else {
                errors++;
                vTaskDelay(pdMS_TO_TICKS(10));
            }
            continue;
        }

        // State 4: Wait for switch-on ACK (0x82).
        if (state == 4) {
            if (sai_recv(&rx_msg, 100)) {
                if (rx_msg.identifier == SAI_BOOTLOADER_RX &&
                    rx_msg.data_length_code >= 2 &&
                    rx_msg.data[0] == SAI_CMD_SWITCH_ON &&
                    rx_msg.data[1] == module_cnt) {
                    ESP_LOGI(TAG, "Switch-on ACK for #%d", module_cnt);

                    // Store this module.
                    if (sai_addressing_result.count < SAI_MAX_NODES) {
                        sai_addressing_result.node_ids[sai_addressing_result.count] = module_cnt;
                        sai_addressing_result.count++;
                    }
                    module_cnt++;
                    assign_retries = 0;
                    last_activity = xTaskGetTickCount();
                    state = 5;
                    continue;
                }
                if (rx_msg.identifier == SAI_BOOTLOADER_RX &&
                    rx_msg.data_length_code >= 2 &&
                    rx_msg.data[0] == SAI_CMD_SWITCH_ON) {
                    ESP_LOGW(TAG, "Switch-on ACK for wrong node: got=%d expected=%d",
                             rx_msg.data[1], module_cnt);
                }
            } else {
                // ACK timeout — go back to assign (module may have missed switch-on).
                errors++;
                ESP_LOGW(TAG, "No ACK (switch-on) for #%d, retrying assign", module_cnt);
                state = 1;
            }
            continue;
        }

        // State 5: Wait for next bootup or silence = done.
        if (state == 5) {
            if (sai_recv(&rx_msg, 50)) {
                if (rx_msg.identifier == SAI_BOOTLOADER_RX &&
                    rx_msg.data_length_code >= 1 &&
                    rx_msg.data[0] == SAI_CMD_BOOTUP) {
                    ESP_LOGI(TAG, "Bootup from module #%d", module_cnt);
                    last_activity = xTaskGetTickCount();
                    state = 1;
                    continue;
                }
                // Other messages: ignore, but refresh activity timer.
                last_activity = xTaskGetTickCount();
            }

            // Check silence timeout.
            now = xTaskGetTickCount();
            if ((now - last_activity) > pdMS_TO_TICKS(SAI_SILENCE_TIMEOUT_MS)) {
                ESP_LOGI(TAG, "Silence timeout, no more modules");
                break;
            }
            continue;
        }
    }

    // --- Phase 2: App-Start ---
    if (sai_addressing_result.count > 0) {
        ESP_LOGI(TAG, "App-start for %d module(s)...", sai_addressing_result.count);

        // First broadcast.
        sai_send_app_start_broadcast();
        vTaskDelay(pdMS_TO_TICKS(10));

        // Per-module app-start.
        for (int i = 0; i < sai_addressing_result.count; i++) {
            uint8_t node_id = sai_addressing_result.node_ids[i];
            sai_send_cmd(SAI_CMD_APP_START, node_id);
            sai_wait_app_start_ack(node_id, &errors);
            vTaskDelay(pdMS_TO_TICKS(10));
        }

        // Second broadcast.
        sai_send_app_start_broadcast();
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    // Drain RX queue so Python starts with empty buffers.
    while (sai_recv(&rx_msg, 0)) {
        // discard
    }

    sai_addressing_result.addressing_done = true;
    sai_addressing_result.last_state = state;
    sai_addressing_result.elapsed_ms = (xTaskGetTickCount() - start_tick) * portTICK_PERIOD_MS;
    sai_addressing_result.error_count = errors;

    ESP_LOGI(TAG, "Addressing complete: %d module(s), %lu ms, %d errors",
             sai_addressing_result.count,
             (unsigned long)sai_addressing_result.elapsed_ms,
             errors);
    for (int i = 0; i < sai_addressing_result.count; i++) {
        ESP_LOGI(TAG, "  Node %d", sai_addressing_result.node_ids[i]);
    }

    // TWAI stays installed — machine.CAN will take over.
}

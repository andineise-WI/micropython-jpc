/*
 * MicroPython module: sai
 *
 * Exposes the SAI early addressing results to Python.
 *
 * Usage:
 *   import sai
 *   nodes = sai.get_nodes()        # → [1, 2] or []
 *   done = sai.addressing_done()   # → True/False
 *   sai.node_count()               # → 2
 *   sai.last_state()               # → 5 (state machine end state)
 *   sai.elapsed_ms()               # → 1234 (addressing duration)
 *   sai.error_count()              # → 0 (TX failures + ACK timeouts)
 *   sai.twai_status()              # → dict with TWAI bus status
 */

#include "py/runtime.h"
#include "py/obj.h"
#include "driver/twai.h"
#include "sai_addressing.h"

// sai.get_nodes() → list of node IDs assigned during early addressing.
static mp_obj_t sai_get_nodes(void) {
    mp_obj_list_t *lst = MP_OBJ_TO_PTR(mp_obj_new_list(0, NULL));
    for (int i = 0; i < sai_addressing_result.count; i++) {
        mp_obj_list_append(MP_OBJ_FROM_PTR(lst),
                           MP_OBJ_NEW_SMALL_INT(sai_addressing_result.node_ids[i]));
    }
    return MP_OBJ_FROM_PTR(lst);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_get_nodes_obj, sai_get_nodes);

// sai.addressing_done() → True if early addressing has completed.
static mp_obj_t sai_addressing_done_fn(void) {
    return mp_obj_new_bool(sai_addressing_result.addressing_done);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_addressing_done_obj, sai_addressing_done_fn);

// sai.node_count() → number of modules found.
static mp_obj_t sai_node_count(void) {
    return MP_OBJ_NEW_SMALL_INT(sai_addressing_result.count);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_node_count_obj, sai_node_count);

// sai.last_state() → last state machine state (0-6).
static mp_obj_t sai_last_state(void) {
    return MP_OBJ_NEW_SMALL_INT(sai_addressing_result.last_state);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_last_state_obj, sai_last_state);

// sai.elapsed_ms() → total addressing duration in milliseconds.
static mp_obj_t sai_elapsed_ms(void) {
    return mp_obj_new_int(sai_addressing_result.elapsed_ms);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_elapsed_ms_obj, sai_elapsed_ms);

// sai.error_count() → number of TX failures + ACK timeouts.
static mp_obj_t sai_error_count(void) {
    return MP_OBJ_NEW_SMALL_INT(sai_addressing_result.error_count);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_error_count_obj, sai_error_count);

// sai.twai_installed() → True if TWAI driver is still running from C init.
static mp_obj_t sai_twai_installed_fn(void) {
    return mp_obj_new_bool(sai_addressing_result.twai_installed);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_twai_installed_obj, sai_twai_installed_fn);

// sai.twai_status() → dict with TWAI bus status info.
static mp_obj_t sai_twai_status(void) {
    twai_status_info_t status;
    esp_err_t err = twai_get_status_info(&status);
    if (err != ESP_OK) {
        mp_raise_msg(&mp_type_OSError, MP_ERROR_TEXT("TWAI not running"));
    }
    mp_obj_dict_t *d = MP_OBJ_TO_PTR(mp_obj_new_dict(8));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_OBJ_NEW_QSTR(MP_QSTR_state), MP_OBJ_NEW_SMALL_INT(status.state));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_tx_error), MP_OBJ_NEW_SMALL_INT(status.tx_error_counter));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_rx_error), MP_OBJ_NEW_SMALL_INT(status.rx_error_counter));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_msgs_to_tx), mp_obj_new_int(status.msgs_to_tx));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_msgs_to_rx), mp_obj_new_int(status.msgs_to_rx));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_tx_failed), mp_obj_new_int(status.tx_failed_count));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_arb_lost), mp_obj_new_int(status.arb_lost_count));
    mp_obj_dict_store(MP_OBJ_FROM_PTR(d),
        MP_ROM_QSTR(MP_QSTR_bus_error), mp_obj_new_int(status.bus_error_count));
    return MP_OBJ_FROM_PTR(d);
}
static MP_DEFINE_CONST_FUN_OBJ_0(sai_twai_status_obj, sai_twai_status);

// Module globals table.
static const mp_rom_map_elem_t sai_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),           MP_ROM_QSTR(MP_QSTR_sai) },
    { MP_ROM_QSTR(MP_QSTR_get_nodes),          MP_ROM_PTR(&sai_get_nodes_obj) },
    { MP_ROM_QSTR(MP_QSTR_addressing_done),    MP_ROM_PTR(&sai_addressing_done_obj) },
    { MP_ROM_QSTR(MP_QSTR_node_count),         MP_ROM_PTR(&sai_node_count_obj) },
    { MP_ROM_QSTR(MP_QSTR_last_state),         MP_ROM_PTR(&sai_last_state_obj) },
    { MP_ROM_QSTR(MP_QSTR_elapsed_ms),         MP_ROM_PTR(&sai_elapsed_ms_obj) },
    { MP_ROM_QSTR(MP_QSTR_error_count),        MP_ROM_PTR(&sai_error_count_obj) },
    { MP_ROM_QSTR(MP_QSTR_twai_installed),     MP_ROM_PTR(&sai_twai_installed_obj) },
    { MP_ROM_QSTR(MP_QSTR_twai_status),        MP_ROM_PTR(&sai_twai_status_obj) },
};
static MP_DEFINE_CONST_DICT(sai_module_globals, sai_module_globals_table);

const mp_obj_module_t mp_module_sai = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&sai_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sai, mp_module_sai);

/*
 * MicroPython module: sai
 *
 * Exposes the SAI early addressing results to Python.
 *
 * Usage:
 *   import sai
 *   nodes = sai.get_nodes()        # → [1, 2] or []
 *   done = sai.addressing_done()   # → True/False
 */

#include "py/runtime.h"
#include "py/obj.h"
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

// Module globals table.
static const mp_rom_map_elem_t sai_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),           MP_ROM_QSTR(MP_QSTR_sai) },
    { MP_ROM_QSTR(MP_QSTR_get_nodes),          MP_ROM_PTR(&sai_get_nodes_obj) },
    { MP_ROM_QSTR(MP_QSTR_addressing_done),    MP_ROM_PTR(&sai_addressing_done_obj) },
    { MP_ROM_QSTR(MP_QSTR_node_count),         MP_ROM_PTR(&sai_node_count_obj) },
};
static MP_DEFINE_CONST_DICT(sai_module_globals, sai_module_globals_table);

const mp_obj_module_t mp_module_sai = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&sai_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sai, mp_module_sai);

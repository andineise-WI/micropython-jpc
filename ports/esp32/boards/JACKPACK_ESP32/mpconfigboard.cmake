set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.flash_8MiB
    boards/sdkconfig.spiram
)

set(MICROPY_SOURCE_BOARD
    ${MICROPY_BOARD_DIR}/board_init.c
    ${MICROPY_BOARD_DIR}/../../sai_addressing.c
    ${MICROPY_BOARD_DIR}/../../modsai.c
)

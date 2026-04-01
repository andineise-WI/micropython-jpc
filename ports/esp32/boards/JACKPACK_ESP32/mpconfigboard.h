// JackPack Control ESP32 — SAI CANopen Controller
// Custom board with early CAN auto-addressing before MicroPython VM.

#define MICROPY_HW_BOARD_NAME               "JackPack ESP32"
#define MICROPY_HW_MCU_NAME                 "ESP32"

// Disable Bluetooth (not needed, CAN-only board).
#define MICROPY_PY_BLUETOOTH                (0)

// Flag for conditional SAI code in shared files (e.g. machine_can.c).
#define MICROPY_BOARD_JACKPACK_SAI          (1)

// Override startup to run SAI CAN addressing before MicroPython.
#define MICROPY_BOARD_STARTUP               jackpack_startup
void jackpack_startup(void);

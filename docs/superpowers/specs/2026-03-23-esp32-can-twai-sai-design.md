# ESP32 CAN/TWAI + SAI Subbus Module Design Spec

**Date**: 2026-03-23
**Status**: Draft
**Author**: AI-assisted design

## 1. Overview

Implement CAN/TWAI support for the ESP32 port of MicroPython, plus a frozen Python layer for Weidmüller/Heyfra SAI Subbus module management. The ESP32 acts as a PLC (SPS) programmable via Blockly, communicating with SAI I/O modules over CANopen.

### System Architecture

```
Blockly UI (Browser)
    │ generates
    ▼
Python Application Code
    │ uses
    ▼
┌─────────────────────────────────┐
│  SAI Bus Layer (Frozen Python)  │  ← sai.py: auto-addressing, CANopen, I/O mapping
│  - SAIBus                       │
│  - SAIModule (8DI/8DO/8DIO/     │
│    4AI/4AO/PT100/CNT)           │
└────────────┬────────────────────┘
             │ uses
             ▼
┌─────────────────────────────────┐
│  machine.CAN (extmod layer)     │  ← extmod/machine_can.c: generic API
└────────────┬────────────────────┘
             │ #include
             ▼
┌─────────────────────────────────┐
│  ESP32 TWAI Port (C)            │  ← ports/esp32/machine_can.c: ESP-IDF driver
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  ESP-IDF TWAI Driver            │  ← driver/twai.h
│  (SJA1000-compatible)           │
└────────────┬────────────────────┘
             │
             ▼
        CAN Bus (250 kbit/s)
             │
    ┌────────┼────────┬──────────┐
    ▼        ▼        ▼          ▼
  SAI      SAI      SAI        SAI
  8DI      8DO      4AI        PT100
  (Node 1) (Node 2) (Node 3)  (Node 4)
```

## 2. Scope

### In Scope (this spec)

1. **C-Level**: `ports/esp32/machine_can.c` — TWAI driver port implementing `machine_can_port.h` interface
2. **Config**: `mpconfigport.h` + `esp32_common.cmake` changes to enable `machine.CAN`
3. **Frozen Python**: `sai.py` module for SAI Subbus management — frozen into firmware via `ports/esp32/modules/`

### Out of Scope

- CAN-FD support (ESP32 TWAI is Classic CAN only)
- Multi-controller support (ESP32-C6/P4 have 2-3 controllers — future work)
- Blockly integration layer (separate project)
- Web server / Blockly runtime

## 3. Layer 1: C-Level TWAI Driver

### 3.1 Files

| File | Action | Purpose |
|------|--------|---------|
| `ports/esp32/machine_can.c` | NEW | TWAI port implementation |
| `ports/esp32/mpconfigport.h` | EDIT | Enable CAN, set timing limits |
| `ports/esp32/esp32_common.cmake` | EDIT | Add `machine_can.c` to sources |

### 3.2 Configuration (`mpconfigport.h`)

```c
#ifndef MICROPY_PY_MACHINE_CAN
#define MICROPY_PY_MACHINE_CAN              (SOC_TWAI_SUPPORTED)
#endif
#define MICROPY_PY_MACHINE_CAN_INCLUDEFILE  "ports/esp32/machine_can.c"
#define MICROPY_HW_NUM_CAN                  (1)
#define MICROPY_HW_CAN_IS_RESERVED(can_id)  (false)
```

### 3.3 Hardware Constants

| Constant | Value | Note |
|----------|-------|------|
| `CAN_BRP_MIN` | 2 | TWAI prescaler minimum |
| `CAN_BRP_MAX` | 128 | TWAI prescaler maximum |
| `CAN_TSEG1_MIN` | 1 | |
| `CAN_TSEG1_MAX` | 16 | |
| `CAN_TSEG2_MIN` | 1 | |
| `CAN_TSEG2_MAX` | 8 | |
| `CAN_SJW_MIN` | 1 | |
| `CAN_SJW_MAX` | 4 | |
| `CAN_TX_QUEUE_LEN` | 1 | Logical queue (ESP-IDF manages internal queue; send() always returns 0) |
| `CAN_HW_MAX_FILTER` | 2 | TWAI dual-filter mode provides 2 logical filters |
| `CAN_FILTERS_STD_EXT_SEPARATE` | 0 | Combined filter indices |
| `CAN_PORT_PRINT_FUNCTION` | 0 | Use default extmod print function |

### 3.4 Fixed Pin Configuration

| Signal | GPIO | Note |
|--------|------|------|
| TX | GPIO 5 | To CAN transceiver TXD |
| RX | GPIO 4 | From CAN transceiver RXD |

Pins are hardcoded in the port implementation. The CAN constructor ignores `tx`/`rx` keyword arguments (they exist in the old API but are not relevant for the standardized `machine.CAN`).

### 3.5 Port Function Implementations

| Port Function | ESP-IDF Implementation |
|---------------|----------------------|
| `machine_can_port_f_clock()` | Returns APB_CLK_FREQ (80 MHz) |
| `machine_can_port_supports_mode()` | All modes except SLEEP supported |
| `machine_can_port_max_data_len()` | Always returns 8 (Classic CAN only) |
| `machine_can_port_init()` | `twai_driver_install()` + `twai_start()`. BRP is rounded to nearest even value on original ESP32 (SJA1000 limitation). |
| `machine_can_port_deinit()` | `twai_stop()` + `twai_driver_uninstall()` |
| `machine_can_port_send()` | `twai_transmit()` with timeout=0 (non-blocking) |
| `machine_can_port_recv()` | `twai_receive()` with timeout=0 (non-blocking) |
| `machine_can_port_cancel_send()` | `twai_clear_transmit_queue()` (cancels **all** pending, returns true) |
| `machine_can_port_get_state()` | `twai_get_status_info()` → map state |
| `machine_can_port_update_counters()` | `twai_get_status_info()` → fill counters |
| `machine_can_port_restart()` | `twai_stop()` + `twai_start()` |
| `machine_can_port_clear_filters()` | Store accept-all config (applied on reinit) |
| `machine_can_port_set_filter()` | Store filter config (applied on next init/reinit) |
| `machine_can_update_irqs()` | `twai_reconfigure_alerts()` |
| `machine_can_port_irq_flags()` | `twai_read_alerts()` → map to MP flags |
| `machine_can_port_get_additional_timings()` | Returns `None` |

### 3.6 Port-Specific Data Structure

```c
struct machine_can_port {
    bool installed;           // Whether twai_driver_install() has been called
    twai_filter_config_t filter_config;  // Current acceptance filter
    uint32_t alert_flags;     // Cached alert flags from last read
};
```

### 3.7 Filter Strategy

ESP32 TWAI has only a single acceptance filter (single or dual mode). For the CANopen use case, accept-all is the only practical configuration since the ESP32 is the bus master receiving messages from all node IDs (NMT, SDO, PDO, Heartbeat, Bootloader).

- Default: Accept all standard and extended IDs
- `set_filters(None)` → accept all. The extmod layer calls `set_filter()` twice (idx=0 for std, idx=1 for ext). With `CAN_HW_MAX_FILTER=2` and dual-filter mode, both are stored. Since mask=0 for accept-all, a single hardware filter suffices.
- `set_filters([(id, mask, flags)])` → single filter with user-specified id/mask
- `set_filters([(id1, mask1, flags1), (id2, mask2, flags2)])` → dual filter mode
- Filter changes require TWAI reinit: `twai_stop()` → `twai_driver_uninstall()` → reinstall with new filter → `twai_start()`

### 3.8 State Mapping

| `twai_state_t` | `machine_can_state_t` |
|----------------|----------------------|
| `TWAI_STATE_STOPPED` | `MP_CAN_STATE_STOPPED` |
| `TWAI_STATE_RUNNING` | `MP_CAN_STATE_ACTIVE` |
| `TWAI_STATE_BUS_OFF` | `MP_CAN_STATE_BUS_OFF` |
| `TWAI_STATE_RECOVERING` | `MP_CAN_STATE_BUS_OFF` |

Warning/Passive states are detected via `twai_status_info_t.tx_error_counter` / `rx_error_counter` thresholds (>96 = warning, >=128 = passive per CAN 2.0B spec).

### 3.9 Alert → IRQ Mapping

| MicroPython IRQ | ESP-IDF Alert(s) |
|-----------------|-----------------|
| `MP_CAN_IRQ_RX` | `TWAI_ALERT_RX_DATA` |
| `MP_CAN_IRQ_TX` | `TWAI_ALERT_TX_SUCCESS` |
| `MP_CAN_IRQ_TX_FAILED` | `TWAI_ALERT_TX_FAILED` |
| `MP_CAN_IRQ_STATE` | `TWAI_ALERT_ERR_PASS`, `TWAI_ALERT_BUS_OFF`, `TWAI_ALERT_ABOVE_ERR_WARN`, `TWAI_ALERT_RECOVERY_IN_PROGRESS` |

Implementation: `twai_read_alerts()` is called from `machine_can_port_irq_flags()`. The extmod layer calls this when polling IRQs.

### 3.10 Soft Reset Integration

The ESP32 port must call `machine_can_deinit_all()` during soft reset to properly uninstall the TWAI driver. This requires adding a `#if MICROPY_PY_MACHINE_CAN` guarded call in `ports/esp32/main.c` at the soft-reset exit point, similar to how the STM32 port handles this.

### 3.11 BRP Even-Value Constraint

On the original ESP32 (SJA1000-based TWAI), the baud rate prescaler (BRP) must be an even number. The `extmod/machine_can.c` `calculate_brp()` may return odd values. The port's `machine_can_port_init()` must round BRP to the nearest even value on `CONFIG_IDF_TARGET_ESP32`. Other ESP32 variants (S2, S3, C3, C6) support odd BRP values and don't need this adjustment.

## 4. Layer 2: SAI Bus Module (Frozen Python)

### 4.1 Files

| File | Action | Purpose |
|------|--------|---------|
| `ports/esp32/modules/sai.py` | NEW | SAI Subbus management (frozen module) |

### 4.2 Boot Sequence

The SAI bus initialization is triggered explicitly by the application (or auto-started from `boot.py`):

```python
from machine import CAN
from sai import SAIBus

bus = SAIBus()          # Creates CAN(1, bitrate=250000), discovers & addresses modules
bus.start_operational() # NMT → Operational, enables PDO exchange
```

### 4.3 SAI Bootloader Protocol

Based on the existing `main.py` and documentation:

```
Phase 1: Discovery & Addressing (0x7FE/0x7FF)
  1. Wait for bootup message: RX 0x7FF [0x01]
  2. Assign address:          TX 0x7FE [0x81, node_id]
  3. Wait for ACK:            RX 0x7FF [0x81]
  4. Switch on next module:   TX 0x7FE [0x82, node_id]
  5. Wait for ACK:            RX 0x7FF [0x82]
  6. Repeat from step 1 if another module boots (1s timeout)

Phase 2: Start Application (per existing main.py / Weidmüller protocol)
  7. Broadcast start signal:  TX 0x77F [0x7F]
  8. For each module:         TX 0x7FE [0x83, node_id]
  9. Broadcast start confirm: TX 0x77F [0x7F]

Phase 3: NMT → Operational
 10. NMT Start All:           TX 0x000 [0x01, 0x00]
```

### 4.4 SAI Module Types

| Module | CANopen Profile | Process Data (TPDO) | Process Data (RPDO) | Node Type |
|--------|----------------|--------------------|--------------------|-----------|
| SAI-SB 8DI | CiA 401 | 1 byte (8 digital inputs) | — | Input |
| SAI-SB 8DO | CiA 401 | 1 byte (8 digital input readback) | 1 byte (8 digital outputs) | Output |
| SAI-SB 8DIO | CiA 401 | 1 byte (8 DI) | 1 byte (8 DO) | Mixed |
| SAI-SB 4AI | CiA 401 | 4×16 bit (analog inputs) | — | Input |
| SAI-SB 4AO | CiA 401 | — | 4×16 bit (analog outputs) | Output |
| SAI-SB 4PT100 | CiA 401 | 4×16 bit (temperature/resistance) | — | Input |
| SAI-SB CNT | CiA 401 | Counter values | Counter control | Mixed |

### 4.5 CANopen COB-ID Scheme

| Function | COB-ID | Direction |
|----------|--------|-----------|
| NMT | 0x000 | ESP32 → All |
| TPDO1 | 0x180 + node_id | Module → ESP32 |
| TPDO2 | 0x280 + node_id | Module → ESP32 |
| RPDO1 | 0x200 + node_id | ESP32 → Module |
| SDO TX | 0x600 + node_id | ESP32 → Module |
| SDO RX | 0x580 + node_id | Module → ESP32 |
| Heartbeat | 0x700 + node_id | Module → ESP32 |
| Bootloader TX | 0x7FE | ESP32 → Module |
| Bootloader RX | 0x7FF | Module → ESP32 |
| App Start Broadcast | 0x77F | ESP32 → All Modules |

### 4.6 Python API

```python
class SAIBus:
    """Manages all SAI modules on the CAN bus."""

    def __init__(self, can_id=1, bitrate=250000, tx_pin=5, rx_pin=4):
        """Initialize CAN bus and discover all SAI modules.
        Note: can_id is 1-based (machine.CAN uses 1-based identifiers)."""

    def scan(self) -> list:
        """Re-scan for modules. Returns list of SAIModule objects."""

    def start_operational(self):
        """Send NMT Start to all nodes → Operational state."""

    def stop(self):
        """Send NMT Stop to all nodes → Pre-Operational state."""

    @property
    def modules(self) -> list:
        """List of discovered SAIModule objects."""

    def update(self):
        """Poll CAN bus, process incoming PDOs and heartbeats.
        Calls can.recv() in a loop until None (no more pending messages).
        Must be called regularly from the Blockly main loop."""


class SAIModule:
    """Represents a single SAI Subbus module."""

    def __init__(self, bus, node_id, module_type):
        ...

    @property
    def node_id(self) -> int: ...

    @property
    def module_type(self) -> str: ...

    @property
    def alive(self) -> bool:
        """True if heartbeat received within timeout."""

    # --- Digital I/O (8DI, 8DO, 8DIO) ---
    def digital_read(self, channel: int) -> bool:
        """Read a single digital input (0-7)."""

    def digital_read_byte(self) -> int:
        """Read all 8 digital inputs as byte."""

    def digital_write(self, channel: int, value: bool):
        """Set a single digital output (0-7)."""

    def digital_write_byte(self, value: int):
        """Set all 8 digital outputs as byte."""

    # --- Analog I/O (4AI, 4AO) ---
    def analog_read(self, channel: int) -> int:
        """Read analog input (0-3), returns raw 16-bit PDO value.
        Interpretation depends on configured range (see SAI docs)."""

    def analog_write(self, channel: int, value: int):
        """Write analog output (0-3), raw 16-bit PDO value.
        Interpretation depends on configured range (see SAI docs)."""

    # --- PT100 ---
    def temperature_read(self, channel: int) -> float:
        """Read temperature in °C (resolution 0.1K)."""

    def resistance_read(self, channel: int) -> int:
        """Read raw resistance value."""

    # --- Counter (CNT) ---
    def counter_read(self, channel: int) -> int:
        """Read counter value."""

    def counter_reset(self, channel: int):
        """Reset counter to 0."""

    # --- SDO Access (generic) ---
    def sdo_read(self, index: int, subindex: int) -> bytes:
        """Read SDO object."""

    def sdo_write(self, index: int, subindex: int, data: bytes):
        """Write SDO object."""
```

### 4.7 Data Flow: PDO I/O Mapping

Process data is cached in-memory for fast Blockly access:

```
SAIModule._inputs = {}   # Cached TPDO data (updated from CAN RX)
SAIModule._outputs = {}  # Pending RPDO data (sent on next update)

bus.update():
  1. Receive all pending CAN messages
  2. For each TPDO → update corresponding module's _inputs cache
  3. For each module with changed _outputs → send RPDO
  4. Check heartbeats, update alive status
```

This means:
- `digital_read()` reads from cache (fast, no CAN traffic)
- `digital_write()` writes to cache, sent on next `bus.update()`
- `bus.update()` should be called regularly in the Blockly main loop

### 4.8 Module Type Detection

Module type is not auto-detected from CAN communication during bootloader phase. Options:
1. **Configuration-based**: User specifies module order in SAIBus constructor
2. **SDO query**: After operational, read Object 0x1000 (Device Type) from each node

**Design decision**: Use SDO query of Object 0x1000 after start_application. The Device Type value identifies each module. Fallback: manual configuration via constructor argument.

```python
bus = SAIBus()  # Auto-detect via SDO
# OR
bus = SAIBus(modules=['8DI', '8DO', '4AI', 'PT100'])  # Manual config
```

## 5. Error Handling

### CAN Level
- `twai_transmit()` timeout → `send()` returns `None`
- Bus-Off → `state()` returns `STATE_BUS_OFF`, IRQ triggered
- Counter tracking via `get_counters()`

### SAI Level
- Module not responding during boot → skipped, warning printed
- Heartbeat timeout → `module.alive = False`
- SDO timeout → raises `OSError`

## 6. Testing Strategy

### Unit-testable (without hardware)
- Timing parameter calculation (existing extmod tests)
- SAI protocol message encoding/decoding
- PDO cache logic

### Hardware-required
- CAN loopback mode test (TWAI supports loopback)
- Send/receive with real SAI modules
- Full boot sequence with module discovery

## 7. Implementation Order

1. **Phase 1**: `ports/esp32/machine_can.c` + config changes → `machine.CAN` works
2. **Phase 2**: `sai.py` frozen module → SAI boot sequence + I/O access
3. **Phase 3**: Integration test with real SAI hardware

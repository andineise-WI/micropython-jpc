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

        rdata = resp[1]
        if rdata[0] == 0x80:
            raise OSError("SDO abort: 0x{:08X}".format(
                int.from_bytes(rdata[4:8], 'little')))

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

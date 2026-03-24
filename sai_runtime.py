# sai_runtime.py — JackPack SAI CANopen Runtime Library
"""SAI CANopen runtime for ESP32: addressing, SDO, PDO, I/O map."""
import time

try:
    from machine import CAN
except ImportError:
    CAN = None  # Desktop testing

# Protocol constants
BOOTLOADER_TX = 0x7FE
BOOTLOADER_RX = 0x7FF
APP_START_BROADCAST = 0x77F
NMT_ID = 0x000

# Module profiles: (product_code, revision) -> config
MODULE_PROFILES = {
    (1, 0x00010006): {
        "name": "8DI", "io_type": "digital_in", "channels": 8,
        "writes": [(0x2000, 0x00, 0x00), (0x2007, 0x01, 0x55), (0x2007, 0x02, 0x55)],
    },
    (5, 0x0001000A): {
        "name": "8DO", "io_type": "digital_out", "channels": 8,
        "writes": [(0x2005, 0x00, 0x00), (0x2006, 0x00, 0x00)],
    },
    (2, 0x00010007): {
        "name": "8DIO", "io_type": "digital_io", "channels_in": 8, "channels_out": 8,
        "writes": [
            (0x2000, 0x00, 0x00), (0x2001, 0x00, 0x00), (0x2005, 0x00, 0x00),
            (0x2006, 0x00, 0x00), (0x2007, 0x01, 0x55), (0x2007, 0x02, 0x55),
        ],
    },
    (3, 0x00010008): {
        "name": "4AI", "io_type": "analog_in", "channels": 4,
        "writes": [(0x2002, 0x00, 0x05), (0x2004, 0x00, 0x00)],
    },
    (4, 0x00010009): {
        "name": "4AO", "io_type": "analog_out", "channels": 4,
        "writes": [(0x2003, 0x00, 0x00), (0x2005, 0x00, 0x00)],
    },
    (6, 0x0001000B): {
        "name": "CNT", "io_type": "counter", "channels": 2,
        "writes": [
            (0x2101, 0x00, 0x00), (0x2102, 0x01, 0x00), (0x2102, 0x02, 0x00),
            (0x2103, 0x01, 0x00), (0x2103, 0x02, 0x00), (0x2105, 0x00, 0x00),
        ],
    },
}

# I/O arrays (1-based: index 0 = None placeholder)
digital_in = [None]
digital_out = [None]
analog_in = [None]
analog_out = [None]
counter = [None]


def recv_any(can, timeout_ms=100):
    """Receive a CAN message with timeout. Returns (id, data) or None."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = can.recv()
        if msg is not None:
            return msg
        time.sleep_ms(1)
    return None


def send_nmt(can, command, node_id=0):
    """Send NMT command."""
    can.send(NMT_ID, bytes([command & 0xFF, node_id & 0xFF]))


def sdo_upload_u32(can, node_id, index, subindex, timeout_ms=500):
    """Read a 32-bit value via SDO expedited upload. Returns int or None."""
    req_id = 0x600 + node_id
    resp_id = 0x580 + node_id
    req = bytes([0x40, index & 0xFF, (index >> 8) & 0xFF, subindex, 0, 0, 0, 0])
    can.send(req_id, req)
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = can.recv()
        if msg is not None and msg[0] == resp_id:
            data = bytes(msg[1])
            if len(data) >= 8 and data[0] == 0x43:
                return data[4] | (data[5] << 8) | (data[6] << 16) | (data[7] << 24)
            return None
        time.sleep_ms(1)
    return None


def sdo_download_1byte(can, node_id, index, subindex, value, timeout_ms=500):
    """Write a 1-byte value via SDO expedited download. Returns True on ACK."""
    req_id = 0x600 + node_id
    resp_id = 0x580 + node_id
    req = bytes([0x2F, index & 0xFF, (index >> 8) & 0xFF, subindex, value & 0xFF, 0, 0, 0])
    can.send(req_id, req)
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = can.recv()
        if msg is not None and msg[0] == resp_id:
            data = bytes(msg[1])
            return len(data) >= 1 and data[0] == 0x60
        time.sleep_ms(1)
    return False

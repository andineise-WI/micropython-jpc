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


def run_addressing(can, timeout_s=1.0):
    """Phase 1+2: Auto-address SAI modules and start applications.
    
    Returns list of assigned node IDs [1, 2, ...].
    """
    print("[ADDR] Phase 1: NMT Reset...")
    send_nmt(can, 0x81, 0x00)
    time.sleep_ms(500)
    
    addr_step = 0
    module_count = 1
    modules = []
    last_activity = time.ticks_ms()
    timeout_ms = int(timeout_s * 1000)
    
    while True:
        msg = can.recv()
        if msg is not None:
            msg_id = msg[0]
            data = bytes(msg[1])
            
            if addr_step == 0:
                if msg_id == BOOTLOADER_RX and len(data) > 0 and data[0] == 0x01:
                    print("[ADDR] Bootup from module #{}".format(module_count))
                    addr_step = 1
            
            if addr_step == 1:
                can.send(BOOTLOADER_TX, bytes([0x81, module_count]))
                addr_step = 2
                continue
            
            if addr_step == 2:
                if msg_id == BOOTLOADER_RX and len(data) > 0 and data[0] == 0x81:
                    addr_step = 3
            
            if addr_step == 3:
                can.send(BOOTLOADER_TX, bytes([0x82, module_count]))
                addr_step = 4
                continue
            
            if addr_step == 4:
                if msg_id == BOOTLOADER_RX and len(data) > 0 and data[0] == 0x82:
                    modules.append(module_count)
                    module_count += 1
                    last_activity = time.ticks_ms()
                    addr_step = 5
            
            if addr_step == 5:
                if msg_id == BOOTLOADER_RX and len(data) > 0 and data[0] == 0x01:
                    addr_step = 1
                    can.send(BOOTLOADER_TX, bytes([0x81, module_count]))
                    addr_step = 2
                    continue
        else:
            time.sleep_ms(1)
        
        # Timeout: no more modules
        if addr_step == 5 and time.ticks_diff(time.ticks_ms(), last_activity) > timeout_ms:
            break
        if addr_step == 0 and time.ticks_diff(time.ticks_ms(), last_activity) > timeout_ms:
            break
    
    # Phase 2: App-Start
    if modules:
        print("[ADDR] Phase 2: Starting {} module(s)...".format(len(modules)))
        can.send(APP_START_BROADCAST, bytes([0x7F]))
        time.sleep_ms(10)
        for nid in modules:
            can.send(BOOTLOADER_TX, bytes([0x83, nid]))
            time.sleep_ms(10)
        can.send(APP_START_BROADCAST, bytes([0x7F]))
        time.sleep_ms(500)
    
    print("[ADDR] Complete: {} modules -> {}".format(len(modules), modules))
    return modules


def detect_modules(can, node_ids, heartbeat_timeout_ms=1000):
    """Phase 3+4: Listen for heartbeats, query identity via SDO.
    
    Returns list of dicts: [{"node_id": N, "profile": {...}, ...}, ...]
    """
    print("[DETECT] Phase 3: Listening for heartbeats...")
    alive_nodes = set()
    deadline = time.ticks_add(time.ticks_ms(), heartbeat_timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = can.recv()
        if msg is not None:
            msg_id = msg[0]
            for nid in node_ids:
                if msg_id == 0x700 + nid:
                    alive_nodes.add(nid)
        else:
            time.sleep_ms(1)
        if len(alive_nodes) == len(node_ids):
            break
    
    print("[DETECT] Alive: {} of {}".format(len(alive_nodes), len(node_ids)))
    
    print("[DETECT] Phase 4: Identity query...")
    detected = []
    for nid in sorted(node_ids):
        product_code = sdo_upload_u32(can, nid, 0x1018, 0x02) if nid in alive_nodes else None
        revision = sdo_upload_u32(can, nid, 0x1018, 0x03) if nid in alive_nodes else None
        
        profile = MODULE_PROFILES.get((product_code, revision))
        name = profile["name"] if profile else "UNKNOWN"
        print("[DETECT] Node {}: {}".format(nid, name))
        
        detected.append({
            "node_id": nid,
            "profile": profile,
            "product_code": product_code,
            "revision": revision,
        })
    
    return detected


def parametrize_modules(can, detected):
    """Phase 5: Apply SDO parameter writes per module profile. Send NMT Operational."""
    print("[PARAM] Phase 5: Parametrizing modules...")
    all_ok = True
    for mod in detected:
        profile = mod.get("profile")
        if profile is None:
            continue
        nid = mod["node_id"]
        print("[PARAM] Node {}: {}".format(nid, profile["name"]))
        for index, subindex, value in profile["writes"]:
            ok = sdo_download_1byte(can, nid, index, subindex, value)
            if not ok:
                print("[PARAM] WARN: Node {} write 0x{:04X}:0x{:02X} failed".format(nid, index, subindex))
                all_ok = False
    
    print("[PARAM] NMT Operational...")
    send_nmt(can, 0x01, 0x00)
    time.sleep_ms(100)
    return all_ok


def build_io_map(detected):
    """Phase 6: Build flat I/O arrays from detected modules, sorted by node ID.
    
    Populates module-level digital_in, digital_out, analog_in, analog_out, counter.
    Returns io_map dict mapping each array to list of (node_id, start_index, channels).
    """
    global digital_in, digital_out, analog_in, analog_out, counter
    
    io_map = {
        "digital_in": [],
        "digital_out": [],
        "analog_in": [],
        "analog_out": [],
        "counter": [],
    }
    
    di_count = 0
    do_count = 0
    ai_count = 0
    ao_count = 0
    cnt_count = 0
    
    for mod in sorted(detected, key=lambda m: m["node_id"]):
        profile = mod.get("profile")
        if profile is None:
            continue
        nid = mod["node_id"]
        io_type = profile.get("io_type", "")
        
        if io_type == "digital_in":
            ch = profile["channels"]
            io_map["digital_in"].append((nid, di_count + 1, ch))
            di_count += ch
        elif io_type == "digital_out":
            ch = profile["channels"]
            io_map["digital_out"].append((nid, do_count + 1, ch))
            do_count += ch
        elif io_type == "digital_io":
            ch_in = profile["channels_in"]
            ch_out = profile["channels_out"]
            io_map["digital_in"].append((nid, di_count + 1, ch_in))
            di_count += ch_in
            io_map["digital_out"].append((nid, do_count + 1, ch_out))
            do_count += ch_out
        elif io_type == "analog_in":
            ch = profile["channels"]
            io_map["analog_in"].append((nid, ai_count + 1, ch))
            ai_count += ch
        elif io_type == "analog_out":
            ch = profile["channels"]
            io_map["analog_out"].append((nid, ao_count + 1, ch))
            ao_count += ch
        elif io_type == "counter":
            ch = profile["channels"]
            io_map["counter"].append((nid, cnt_count + 1, ch))
            cnt_count += ch
    
    digital_in[:] = [None] + [False] * di_count
    digital_out[:] = [None] + [False] * do_count
    analog_in[:] = [None] + [0] * ai_count
    analog_out[:] = [None] + [0] * ao_count
    counter[:] = [None] + [0] * cnt_count
    
    print("[IO] Built: DI={} DO={} AI={} AO={} CNT={}".format(
        di_count, do_count, ai_count, ao_count, cnt_count))
    
    return io_map


def decode_pdo(msg_id, data, io_map):
    """Decode incoming PDO and update I/O arrays in-place."""
    nid = msg_id - 0x180
    
    for node_id, start, channels in io_map.get("digital_in", []):
        if node_id == nid and len(data) >= 1:
            byte_val = data[0]
            for bit in range(channels):
                digital_in[start + bit] = bool(byte_val & (1 << bit))
            return
    
    for node_id, start, channels in io_map.get("analog_in", []):
        if node_id == nid and len(data) >= channels * 2:
            for i in range(channels):
                val = data[i * 2] | (data[i * 2 + 1] << 8)
                analog_in[start + i] = val
            return
    
    for node_id, start, channels in io_map.get("counter", []):
        if node_id == nid and len(data) >= channels * 4:
            for i in range(channels):
                off = i * 4
                val = data[off] | (data[off+1] << 8) | (data[off+2] << 16) | (data[off+3] << 24)
                counter[start + i] = val
            return


def encode_output_pdos(io_map):
    """Encode output arrays into CAN PDO frames. Returns [(can_id, data), ...]."""
    frames = []
    
    for node_id, start, channels in io_map.get("digital_out", []):
        byte_val = 0
        for bit in range(channels):
            if digital_out[start + bit]:
                byte_val |= (1 << bit)
        frames.append((0x200 + node_id, bytes([byte_val])))
    
    for node_id, start, channels in io_map.get("analog_out", []):
        data = bytearray(channels * 2)
        for i in range(channels):
            val = analog_out[start + i] & 0xFFFF
            data[i * 2] = val & 0xFF
            data[i * 2 + 1] = (val >> 8) & 0xFF
        frames.append((0x200 + node_id, bytes(data)))
    
    return frames


def read_inputs(can, io_map):
    """Drain all pending CAN messages and decode PDOs into I/O arrays."""
    while True:
        msg = can.recv()
        if msg is None:
            break
        msg_id = msg[0]
        data = bytes(msg[1])
        if 0x181 <= msg_id <= 0x1FF:
            decode_pdo(msg_id, data, io_map)


def write_outputs(can, io_map):
    """Encode output arrays and send as CAN PDOs."""
    frames = encode_output_pdos(io_map)
    for can_id, data in frames:
        can.send(can_id, data)


def init_firmware(can, addressing_timeout_s=1.0, heartbeat_timeout_ms=1000):
    """Run complete 6-phase firmware init. Returns io_map."""
    modules = run_addressing(can, timeout_s=addressing_timeout_s)
    if not modules:
        print("[INIT] No modules found. Running with empty I/O map.")
        return build_io_map([])
    
    detected = detect_modules(can, modules, heartbeat_timeout_ms=heartbeat_timeout_ms)
    parametrize_modules(can, detected)
    io_map = build_io_map(detected)
    return io_map

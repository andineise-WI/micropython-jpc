# JackPack SAI CANopen Runtime — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete ESP32 MicroPython firmware (`main.py` + `sai_runtime.py`) that auto-addresses SAI CAN modules, identifies them, parametrizes them via SDO, builds a flat I/O map, and runs a user Blockly program (`user_program.py`) in a 10ms SPS scan loop.

**Architecture:** Two firmware files (`main.py` as entry point, `sai_runtime.py` as CANopen library) plus a user-replaceable `user_program.py`. The runtime module owns I/O arrays (`digital_in`, `digital_out`, `analog_in`, `analog_out`, `counter`) as module-level mutable lists with 1-based indexing. `main.py` orchestrates the 6-phase boot sequence then enters the SPS loop.

**Tech Stack:** MicroPython on ESP32-PICO-V3-02, `machine.CAN` for CAN bus (or `esp32.CAN` depending on firmware build), Python 3 + pytest for desktop tests with mocked CAN.

**Spec:** `docs/superpowers/specs/2026-03-24-jackpack-sai-runtime-design.md`

---

## File Structure

| File | Purpose | New/Modify |
|---|---|---|
| `sai_runtime.py` | CANopen library: CAN helpers, addressing, SDO, PDO, I/O arrays, MODULE_PROFILES | Create |
| `main.py` | Firmware entry point: 6-phase boot, SPS scan loop, user_program import | Create |
| `user_program.py` | Default empty Blockly program (setup/loop stubs) | Create |
| `test_sai_runtime.py` | Unit tests for sai_runtime (mocked CAN) | Create |
| `test_main_integration.py` | Integration tests for main boot + SPS loop | Create |

All files are created at workspace root for development/testing. The final deployment copies `main.py`, `sai_runtime.py`, and `user_program.py` onto the ESP32 filesystem.

---

## Task 1: CAN Helper Functions (sai_runtime.py core)

**Files:**
- Create: `sai_runtime.py`
- Create: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for `recv_any()`**

```python
# test_sai_runtime.py
import sys
import time as real_time

# MicroPython time shim for desktop testing
import time
if not hasattr(time, 'ticks_ms'):
    time.ticks_ms = lambda: int(time.time() * 1000)
    time.ticks_add = lambda t, d: t + d
    time.ticks_diff = lambda a, b: a - b
    time.sleep_ms = lambda ms: time.sleep(ms / 1000)

# Mock machine.CAN before importing sai_runtime
class MockCAN:
    NORMAL = 0
    def __init__(self, *args, **kwargs):
        self._queue = []
        self._sent = []
        self._drain_done = False
    def recv(self):
        if self._queue:
            return self._queue.pop(0)
        return None
    def drain(self):
        """Drain stale messages (no-op on mock since queue is test-controlled)."""
        self._drain_done = True
    def send(self, can_id, data):
        self._sent.append((can_id, bytes(data)))
    def set_filters(self, f):
        pass
    def state(self):
        return 1
    def deinit(self):
        pass

class MockMachine:
    CAN = MockCAN

sys.modules['machine'] = MockMachine()

import sai_runtime

def test_recv_any_returns_message():
    can = MockCAN()
    can._queue.append((0x7FF, b'\x01'))
    result = sai_runtime.recv_any(can, timeout_ms=100)
    assert result is not None
    assert result[0] == 0x7FF

def test_recv_any_returns_none_on_timeout():
    can = MockCAN()
    result = sai_runtime.recv_any(can, timeout_ms=50)
    assert result is None

if __name__ == '__main__':
    test_recv_any_returns_message()
    test_recv_any_returns_none_on_timeout()
    print("PASS: recv_any tests")
```

- [ ] **Step 2: Run test – expect FAIL (module not found)**

Run: `python test_sai_runtime.py`
Expected: `ModuleNotFoundError: No module named 'sai_runtime'`

- [ ] **Step 3: Create sai_runtime.py with recv_any and constants**

```python
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
```

- [ ] **Step 4: Run test – expect PASS**

Run: `python test_sai_runtime.py`
Expected: `PASS: recv_any tests`

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: sai_runtime core with recv_any, constants, MODULE_PROFILES, I/O arrays"
```

---

## Task 2: SDO Upload/Download Functions

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing tests for SDO functions**

Append to `test_sai_runtime.py`:

```python
def test_sdo_upload_u32():
    can = MockCAN()
    # SDO response: 0x43 = expedited upload, 4 bytes, value = 0x00010006
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x06, 0x00, 0x01, 0x00])))
    result = sai_runtime.sdo_upload_u32(can, 1, 0x1018, 0x02)
    assert result == 0x00010006
    # Verify request was sent
    assert len(can._sent) == 1
    assert can._sent[0][0] == 0x601  # 0x600 + node_id=1

def test_sdo_upload_u32_timeout():
    can = MockCAN()
    result = sai_runtime.sdo_upload_u32(can, 1, 0x1018, 0x02, timeout_ms=50)
    assert result is None

def test_sdo_download_1byte():
    can = MockCAN()
    # ACK response: 0x60
    can._queue.append((0x581, bytes([0x60, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00])))
    ok = sai_runtime.sdo_download_1byte(can, 1, 0x2000, 0x00, 0x00)
    assert ok is True

def test_sdo_download_1byte_timeout():
    can = MockCAN()
    ok = sai_runtime.sdo_download_1byte(can, 1, 0x2000, 0x00, 0x00, timeout_ms=50)
    assert ok is False
```

- [ ] **Step 2: Run tests – expect FAIL**

Run: `python test_sai_runtime.py`
Expected: `AttributeError: module 'sai_runtime' has no attribute 'sdo_upload_u32'`

- [ ] **Step 3: Implement SDO functions in sai_runtime.py**

Append to `sai_runtime.py`:

```python
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
            return None  # SDO error or unexpected command specifier
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
```

- [ ] **Step 4: Run tests – expect PASS**

Run: `python test_sai_runtime.py`
Expected: `PASS: SDO tests`

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: SDO upload/download functions for CANopen parametrization"
```

---

## Task 3: Auto-Addressing (Phase 1 + 2)

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for addressing**

Append to `test_sai_runtime.py`:

```python
def test_addressing_two_modules():
    """Simulate 2 modules responding to addressing sequence."""
    can = MockCAN()
    # Simulate: NMT Reset sent, then module 1 bootup, then module 2 bootup
    # Module 1 sequence: bootup -> addr ACK -> switch ACK
    can._queue.extend([
        (0x7FF, b'\x01'),       # Module 1 bootup
        (0x7FF, b'\x81'),       # Module 1 addr ACK
        (0x7FF, b'\x82'),       # Module 1 switch ACK
        (0x7FF, b'\x01'),       # Module 2 bootup
        (0x7FF, b'\x81'),       # Module 2 addr ACK
        (0x7FF, b'\x82'),       # Module 2 switch ACK
        # No more bootups -> timeout -> app start
    ])
    modules = sai_runtime.run_addressing(can, timeout_s=0.1)
    assert modules == [1, 2]
    # Verify app-start was sent
    sent_ids = [s[0] for s in can._sent]
    assert 0x000 in sent_ids       # NMT Reset
    assert 0x77F in sent_ids       # APP_START broadcast
    assert 0x7FE in sent_ids       # Address assignments

def test_addressing_no_modules():
    can = MockCAN()
    modules = sai_runtime.run_addressing(can, timeout_s=0.1)
    assert modules == []
```

- [ ] **Step 2: Run tests – expect FAIL**

Run: `python test_sai_runtime.py`
Expected: `AttributeError: module 'sai_runtime' has no attribute 'run_addressing'`

- [ ] **Step 3: Implement run_addressing() in sai_runtime.py**

```python
def send_nmt(can, command, node_id=0):
    """Send NMT command."""
    can.send(NMT_ID, bytes([command & 0xFF, node_id & 0xFF]))


def run_addressing(can, timeout_s=1.0):
    """Phase 1+2: Auto-address SAI modules and start applications.
    
    Returns list of assigned node IDs [1, 2, ...].
    """
    print("[ADDR] Phase 1: NMT Reset...")
    send_nmt(can, 0x81, 0x00)
    time.sleep_ms(500)
    
    # Drain stale messages (use drain method for test-friendliness)
    draining = True
    while draining:
        msg = can.recv()
        if msg is None:
            draining = False
    
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
        # Initial timeout: no modules at all
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
```

- [ ] **Step 4: Run tests – expect PASS**

Run: `python test_sai_runtime.py`
Expected: `PASS: addressing tests`

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: run_addressing for Phase 1+2 auto-addressing with app-start"
```

---

## Task 4: Module Detection + Identity Query (Phase 3 + 4)

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for detect_modules()**

```python
def test_detect_modules_8di_8do():
    """Detect 2 modules: node 1 = 8DI, node 2 = 8DO."""
    can = MockCAN()
    # Heartbeats
    can._queue.append((0x701, b'\x05'))  # Node 1 heartbeat
    can._queue.append((0x702, b'\x05'))  # Node 2 heartbeat
    # Identity responses for node 1 (8DI: product=0x01, rev=0x00010006)
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x01, 0x00, 0x00, 0x00])))
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x03, 0x06, 0x00, 0x01, 0x00])))
    # Identity responses for node 2 (8DO: product=0x05, rev=0x0001000A)
    can._queue.append((0x582, bytes([0x43, 0x18, 0x10, 0x02, 0x05, 0x00, 0x00, 0x00])))
    can._queue.append((0x582, bytes([0x43, 0x18, 0x10, 0x03, 0x0A, 0x00, 0x01, 0x00])))
    
    detected = sai_runtime.detect_modules(can, [1, 2], heartbeat_timeout_ms=50)
    assert len(detected) == 2
    assert detected[0]["node_id"] == 1
    assert detected[0]["profile"]["name"] == "8DI"
    assert detected[1]["node_id"] == 2
    assert detected[1]["profile"]["name"] == "8DO"
```

- [ ] **Step 2: Run tests – expect FAIL**

- [ ] **Step 3: Implement detect_modules()**

```python
def detect_modules(can, node_ids, heartbeat_timeout_ms=1000):
    """Phase 3+4: Listen for heartbeats, query identity via SDO.
    
    Returns list of dicts: [{"node_id": 1, "profile": {...}, "product_code": x, "revision": y}, ...]
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
        print("[DETECT] Node {}: {} (0x{:04X}, 0x{:08X})".format(
            nid, name,
            product_code if product_code is not None else 0,
            revision if revision is not None else 0))
        
        detected.append({
            "node_id": nid,
            "profile": profile,
            "product_code": product_code,
            "revision": revision,
        })
    
    return detected
```

- [ ] **Step 4: Run tests – expect PASS**

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: detect_modules for Phase 3+4 heartbeat + SDO identity"
```

---

## Task 5: SDO Parametrization (Phase 5)

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for parametrize_modules()**

```python
def test_parametrize_8di():
    can = MockCAN()
    detected = [{"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]}]
    # Queue ACK responses for each SDO write (3 writes for 8DI)
    for _ in range(3):
        can._queue.append((0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])))
    ok = sai_runtime.parametrize_modules(can, detected)
    assert ok is True
    assert len(can._sent) == 3  # 3 SDO download writes
```

- [ ] **Step 2: Run tests – expect FAIL**

- [ ] **Step 3: Implement parametrize_modules()**

```python
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
```

- [ ] **Step 4: Run tests – expect PASS**

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: parametrize_modules for Phase 5 SDO writes + NMT Operational"
```

---

## Task 6: I/O Map Builder (Phase 6)

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for build_io_map()**

```python
def test_build_io_map_mixed():
    """Build I/O map: Node 1=8DI, Node 2=8DO, Node 3=8DIO."""
    detected = [
        {"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 2, "profile": sai_runtime.MODULE_PROFILES[(5, 0x0001000A)]},
        {"node_id": 3, "profile": sai_runtime.MODULE_PROFILES[(2, 0x00010007)]},
    ]
    io_map = sai_runtime.build_io_map(detected)
    
    # digital_in: 8 (8DI node1) + 8 (8DIO node3 inputs) = 16 + [None] padding
    assert len(sai_runtime.digital_in) == 17  # [None] + 16 channels
    assert sai_runtime.digital_in[0] is None
    assert sai_runtime.digital_in[1] == False
    assert sai_runtime.digital_in[16] == False
    
    # digital_out: 8 (8DO node2) + 8 (8DIO node3 outputs) = 16
    assert len(sai_runtime.digital_out) == 17
    
    # io_map should contain node->channel mappings
    assert "digital_in" in io_map
    assert "digital_out" in io_map

def test_build_io_map_empty():
    detected = []
    io_map = sai_runtime.build_io_map(detected)
    assert len(sai_runtime.digital_in) == 1   # only [None]
    assert len(sai_runtime.digital_out) == 1
```

- [ ] **Step 2: Run tests – expect FAIL**

- [ ] **Step 3: Implement build_io_map()**

```python
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
    
    # Count channels per type (sorted by node_id)
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
    
    # Rebuild arrays with 1-based indexing (index 0 = None)
    digital_in[:] = [None] + [False] * di_count
    digital_out[:] = [None] + [False] * do_count
    analog_in[:] = [None] + [0] * ai_count
    analog_out[:] = [None] + [0] * ao_count
    counter[:] = [None] + [0] * cnt_count
    
    print("[IO] Built: DI={} DO={} AI={} AO={} CNT={}".format(
        di_count, do_count, ai_count, ao_count, cnt_count))
    
    return io_map
```

- [ ] **Step 4: Run tests – expect PASS**

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: build_io_map for Phase 6 dynamic I/O array construction"
```

---

## Task 7: PDO Read/Write Functions

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing tests for PDO decode/encode**

```python
def test_decode_pdo_digital_in():
    """Decode 8DI PDO: 1 byte bitfield -> 8 booleans in digital_in."""
    sai_runtime.digital_in[:] = [None] + [False] * 8
    io_map = {"digital_in": [(1, 1, 8)]}  # node 1, start=1, 8ch
    # PDO data: 0b10000011 = inputs 1,2,8 are True
    sai_runtime.decode_pdo(0x182, bytes([0x83]), io_map)
    assert sai_runtime.digital_in[1] == True
    assert sai_runtime.digital_in[2] == True
    assert sai_runtime.digital_in[3] == False
    assert sai_runtime.digital_in[8] == True

def test_encode_pdo_digital_out():
    """Encode 8DO output: 8 booleans -> 1 byte bitfield."""
    sai_runtime.digital_out[:] = [None] + [True, False, True, False, False, False, False, True]
    io_map = {"digital_out": [(1, 1, 8)]}
    frames = sai_runtime.encode_output_pdos(io_map)
    assert len(frames) == 1
    assert frames[0][0] == 0x201  # 0x201 + node 0 = node 1 (0x200 + nid)
    assert frames[0][1][0] == 0x85  # 0b10000101 = bits 1,3,8
```

- [ ] **Step 2: Run tests – expect FAIL**

- [ ] **Step 3: Implement decode_pdo() and encode_output_pdos()**

```python
import struct
```

> **Note:** `import struct` is NOT needed — manual byte manipulation is used for MicroPython compatibility.

```python
def decode_pdo(msg_id, data, io_map):
    """Decode incoming PDO and update I/O arrays in-place."""
    nid = msg_id - 0x180  # TPDO1: 0x181+nid, so nid = msg_id - 0x180
    
    # Find which I/O type this node belongs to
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
```

- [ ] **Step 4: Run tests – expect PASS**

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: PDO decode/encode for cyclic I/O communication"
```

---

## Task 8: SPS Scan Loop

**Files:**
- Modify: `sai_runtime.py`
- Modify: `test_sai_runtime.py`

- [ ] **Step 1: Write failing test for read_inputs() and write_outputs()**

```python
def test_read_inputs_decodes_pdo():
    """read_inputs drains CAN and decodes all pending PDOs."""
    can = MockCAN()
    sai_runtime.digital_in[:] = [None] + [False] * 8
    io_map = {"digital_in": [(1, 1, 8)], "digital_out": [], "analog_in": [], "analog_out": [], "counter": []}
    can._queue.append((0x181, bytes([0xFF])))  # all 8 bits on
    sai_runtime.read_inputs(can, io_map)
    assert sai_runtime.digital_in[1] == True
    assert sai_runtime.digital_in[8] == True

def test_write_outputs_sends_pdo():
    can = MockCAN()
    sai_runtime.digital_out[:] = [None] + [True] * 8
    io_map = {"digital_in": [], "digital_out": [(1, 1, 8)], "analog_in": [], "analog_out": [], "counter": []}
    sai_runtime.write_outputs(can, io_map)
    assert len(can._sent) == 1
    assert can._sent[0][0] == 0x201
    assert can._sent[0][1][0] == 0xFF
```

- [ ] **Step 2: Run tests – expect FAIL**

- [ ] **Step 3: Implement read_inputs() and write_outputs()**

```python
def read_inputs(can, io_map):
    """Drain all pending CAN messages and decode PDOs into I/O arrays."""
    while True:
        msg = can.recv()
        if msg is None:
            break
        msg_id = msg[0]
        data = bytes(msg[1])
        if 0x181 <= msg_id <= 0x1FF:  # TPDO1 range
            decode_pdo(msg_id, data, io_map)


def write_outputs(can, io_map):
    """Encode output arrays and send as CAN PDOs."""
    frames = encode_output_pdos(io_map)
    for can_id, data in frames:
        can.send(can_id, data)
```

- [ ] **Step 4: Run tests – expect PASS**

- [ ] **Step 5: Commit**

```bash
git add sai_runtime.py test_sai_runtime.py
git commit -m "feat: read_inputs/write_outputs for SPS scan cycle"
```

---

## Task 9: main.py — Firmware Entry Point

**Files:**
- Create: `main.py`
- Create: `user_program.py`
- Create: `test_main_integration.py`

- [ ] **Step 1: Write failing integration test**

```python
# test_main_integration.py
import sys

class MockCAN:
    NORMAL = 0
    def __init__(self, *args, **kwargs):
        self._queue = []
        self._sent = []
        self._initialized = True
    def recv(self):
        if self._queue:
            return self._queue.pop(0)
        return None
    def send(self, can_id, data):
        self._sent.append((can_id, bytes(data)))
    def set_filters(self, f):
        pass
    def state(self):
        return 1
    def deinit(self):
        self._initialized = False

class MockMachine:
    CAN = MockCAN

sys.modules['machine'] = MockMachine()

import sai_runtime

def test_full_boot_sequence():
    """Test that init_firmware() runs all 6 phases."""
    can = MockCAN()
    # Phase 1: One module bootup sequence
    can._queue.extend([
        (0x7FF, b'\x01'),  # bootup
        (0x7FF, b'\x81'),  # addr ACK
        (0x7FF, b'\x82'),  # switch ACK
    ])
    # Phase 3: Heartbeat
    can._queue.append((0x701, b'\x05'))
    # Phase 4: Identity (8DI)
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x01, 0x00, 0x00, 0x00])))
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x03, 0x06, 0x00, 0x01, 0x00])))
    # Phase 5: SDO ACKs (3 writes for 8DI)
    for _ in range(3):
        can._queue.append((0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])))
    
    io_map = sai_runtime.init_firmware(can, addressing_timeout_s=0.1, heartbeat_timeout_ms=50)
    
    assert io_map is not None
    assert len(sai_runtime.digital_in) == 9  # [None] + 8 DI channels
    assert sai_runtime.digital_in[0] is None
    assert sai_runtime.digital_in[1] == False

if __name__ == '__main__':
    test_full_boot_sequence()
    print("PASS: integration tests")
```

- [ ] **Step 2: Run test – expect FAIL**

Run: `python test_main_integration.py`
Expected: `AttributeError: module 'sai_runtime' has no attribute 'init_firmware'`

- [ ] **Step 3: Implement init_firmware() in sai_runtime.py**

```python
def init_firmware(can, addressing_timeout_s=1.0, heartbeat_timeout_ms=1000):
    """Run complete 6-phase firmware init. Returns io_map or None on total failure."""
    # Phase 1+2: Addressing
    modules = run_addressing(can, timeout_s=addressing_timeout_s)
    if not modules:
        print("[INIT] No modules found. Running with empty I/O map.")
        return build_io_map([])
    
    # Phase 3+4: Detection
    detected = detect_modules(can, modules, heartbeat_timeout_ms=heartbeat_timeout_ms)
    
    # Phase 5: Parametrization
    parametrize_modules(can, detected)
    
    # Phase 6: Build I/O map
    io_map = build_io_map(detected)
    return io_map
```

- [ ] **Step 4: Run test – expect PASS**

- [ ] **Step 5: Create main.py**

```python
# main.py — JackPack Control ESP32 Firmware Entry Point
"""Firmware: 6-phase boot + SPS scan loop with user_program.py."""
import time
import sai_runtime

try:
    from machine import CAN
except ImportError:
    CAN = None

def load_user_program():
    """Import user_program.py, return (setup_fn, loop_fn)."""
    try:
        import user_program
        setup_fn = getattr(user_program, 'setup', lambda: None)
        loop_fn = getattr(user_program, 'loop', lambda: None)
        print("[MAIN] user_program.py loaded")
        return setup_fn, loop_fn
    except ImportError:
        print("[MAIN] No user_program.py found — running empty")
        return lambda: None, lambda: None
    except Exception as e:
        print("[MAIN] Error loading user_program.py:", e)
        return lambda: None, lambda: None


def run():
    """Main firmware entry point."""
    print("=" * 50)
    print("JackPack Control — SAI CANopen Runtime")
    print("=" * 50)

    # Initialize CAN
    print("[MAIN] Initializing CAN at 250kbps...")
    can = CAN(1, bitrate=250000, tx=5, rx=4)
    can.set_filters(None)
    print("[MAIN] CAN state:", can.state())

    # Phase 1-6: Firmware init
    io_map = sai_runtime.init_firmware(can)
    
    # Load user program
    setup_fn, loop_fn = load_user_program()
    
    # Call setup()
    try:
        setup_fn()
    except Exception as e:
        print("[MAIN] USER SETUP ERROR:", e)
    
    # SPS scan loop
    print("[MAIN] Entering SPS scan loop (10ms cycle)...")
    while True:
        try:
            sai_runtime.read_inputs(can, io_map)
            loop_fn()
            sai_runtime.write_outputs(can, io_map)
        except Exception as e:
            print("[MAIN] USER LOOP ERROR:", e)
        time.sleep_ms(10)


# Auto-start
run()
```

- [ ] **Step 6: Create default user_program.py**

```python
# user_program.py — Default Blockly Program (replace via WebSerial)
"""Empty program stub. Replace with Blockly-generated code."""
from sai_runtime import digital_in, digital_out, analog_in, analog_out, counter


def setup():
    """Called once after firmware init completes."""
    pass


def loop():
    """Called every ~10ms by the SPS scan loop."""
    pass
```

- [ ] **Step 7: Run integration test – expect PASS**

Run: `python test_main_integration.py`
Expected: `PASS: integration tests`

- [ ] **Step 8: Commit**

```bash
git add main.py user_program.py test_main_integration.py sai_runtime.py
git commit -m "feat: main.py firmware entry point + user_program.py + SPS scan loop"
```

---

## Task 10: Full Test Suite + Cleanup

**Files:**
- Modify: `test_sai_runtime.py`
- Modify: `test_main_integration.py`

- [ ] **Step 1: Add edge case tests**

```python
# In test_sai_runtime.py:

def test_build_io_map_with_counter():
    """Counter module: 2 channels, 32-bit."""
    detected = [{"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(6, 0x0001000B)]}]
    sai_runtime.build_io_map(detected)
    assert len(sai_runtime.counter) == 3  # [None, 0, 0]

def test_build_io_map_with_analog():
    """4AI + 4AO."""
    detected = [
        {"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(3, 0x00010008)]},
        {"node_id": 2, "profile": sai_runtime.MODULE_PROFILES[(4, 0x00010009)]},
    ]
    sai_runtime.build_io_map(detected)
    assert len(sai_runtime.analog_in) == 5   # [None] + 4
    assert len(sai_runtime.analog_out) == 5  # [None] + 4

def test_decode_pdo_analog_in():
    """Decode 4AI PDO: 4x 16-bit little-endian."""
    sai_runtime.analog_in[:] = [None] + [0] * 4
    io_map = {"analog_in": [(1, 1, 4)], "digital_in": [], "counter": []}
    # Value: 1000, 2000, 3000, 4000
    data = bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F])
    sai_runtime.decode_pdo(0x181, data, io_map)
    assert sai_runtime.analog_in[1] == 1000
    assert sai_runtime.analog_in[4] == 4000

def test_decode_pdo_counter():
    """Decode CNT PDO: 2x 32-bit little-endian."""
    sai_runtime.counter[:] = [None] + [0] * 2
    io_map = {"counter": [(1, 1, 2)], "digital_in": [], "analog_in": []}
    # Values: 100000, 200000
    data = bytes([0xA0, 0x86, 0x01, 0x00, 0x40, 0x0D, 0x03, 0x00])
    sai_runtime.decode_pdo(0x181, data, io_map)
    assert sai_runtime.counter[1] == 100000
    assert sai_runtime.counter[2] == 200000

def test_unknown_module_skipped():
    """Unknown module gets profile=None, no crash."""
    detected = [{"node_id": 1, "profile": None, "product_code": 0xFF, "revision": 0xFF}]
    io_map = sai_runtime.build_io_map(detected)
    assert len(sai_runtime.digital_in) == 1  # only [None]

def test_encode_pdo_analog_out():
    """Encode 4AO output: 4x 16-bit little-endian."""
    sai_runtime.analog_out[:] = [None, 1000, 2000, 3000, 4000]
    io_map = {"analog_out": [(1, 1, 4)], "digital_out": []}
    frames = sai_runtime.encode_output_pdos(io_map)
    assert len(frames) == 1
    assert frames[0][0] == 0x201
    assert frames[0][1] == bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F])

def test_dio_integration():
    """DIO module: contributes to both digital_in[] and digital_out[].
    Scenario from spec: Node1=8DI, Node2=8DI, Node3=8DIO, Node4=8DO."""
    detected = [
        {"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 2, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 3, "profile": sai_runtime.MODULE_PROFILES[(2, 0x00010007)]},
        {"node_id": 4, "profile": sai_runtime.MODULE_PROFILES[(5, 0x0001000A)]},
    ]
    io_map = sai_runtime.build_io_map(detected)
    # digital_in: 8 (node1 8DI) + 8 (node2 8DI) + 8 (node3 8DIO inputs) = 24
    assert len(sai_runtime.digital_in) == 25  # [None] + 24
    # digital_out: 8 (node3 8DIO outputs) + 8 (node4 8DO) = 16
    assert len(sai_runtime.digital_out) == 17  # [None] + 16
    # Verify mappings
    assert io_map["digital_in"] == [(1, 1, 8), (2, 9, 8), (3, 17, 8)]
    assert io_map["digital_out"] == [(3, 1, 8), (4, 9, 8)]
```

- [ ] **Step 2: Run full test suite**

Run: `python test_sai_runtime.py && python test_main_integration.py`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add test_sai_runtime.py test_main_integration.py
git commit -m "test: complete test suite with edge cases for all module types"
```

---

## Summary

| Task | What it builds | Key functions |
|---|---|---|
| 1 | Core constants, I/O arrays, recv_any | `recv_any()` |
| 2 | SDO upload/download | `sdo_upload_u32()`, `sdo_download_1byte()` |
| 3 | Auto-addressing Phase 1+2 | `run_addressing()` |
| 4 | Module detection Phase 3+4 | `detect_modules()` |
| 5 | Parametrization Phase 5 | `parametrize_modules()` |
| 6 | I/O map builder Phase 6 | `build_io_map()` |
| 7 | PDO decode/encode | `decode_pdo()`, `encode_output_pdos()` |
| 8 | SPS cycle helpers | `read_inputs()`, `write_outputs()` |
| 9 | main.py + user_program.py | `init_firmware()`, `run()` |
| 10 | Edge case tests | Full coverage |

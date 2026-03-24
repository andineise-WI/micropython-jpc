# test_sai_runtime.py — Desktop tests for sai_runtime (mocked CAN)
import sys
import time

# MicroPython time shim for desktop testing
if not hasattr(time, 'ticks_ms'):
    time.ticks_ms = lambda: int(time.time() * 1000)
    time.ticks_add = lambda t, d: t + d
    time.ticks_diff = lambda a, b: a - b
    time.sleep_ms = lambda ms: time.sleep(ms / 1000)


class MockCAN:
    NORMAL = 0
    def __init__(self, *args, **kwargs):
        self._queue = []
        self._sent = []
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
        pass


class MockMachine:
    CAN = MockCAN

sys.modules['machine'] = MockMachine()

import sai_runtime


# === Task 1: recv_any ===

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


# === Task 2: SDO functions ===

def test_sdo_upload_u32():
    can = MockCAN()
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x06, 0x00, 0x01, 0x00])))
    result = sai_runtime.sdo_upload_u32(can, 1, 0x1018, 0x02)
    assert result == 0x00010006
    assert len(can._sent) == 1
    assert can._sent[0][0] == 0x601

def test_sdo_upload_u32_timeout():
    can = MockCAN()
    result = sai_runtime.sdo_upload_u32(can, 1, 0x1018, 0x02, timeout_ms=50)
    assert result is None

def test_sdo_download_1byte():
    can = MockCAN()
    can._queue.append((0x581, bytes([0x60, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00])))
    ok = sai_runtime.sdo_download_1byte(can, 1, 0x2000, 0x00, 0x00)
    assert ok is True

def test_sdo_download_1byte_timeout():
    can = MockCAN()
    ok = sai_runtime.sdo_download_1byte(can, 1, 0x2000, 0x00, 0x00, timeout_ms=50)
    assert ok is False


# === Task 3: Addressing ===

def test_addressing_two_modules():
    can = MockCAN()
    can._queue.extend([
        (0x7FF, b'\x01'),  # Module 1 bootup
        (0x7FF, b'\x81'),  # Module 1 addr ACK
        (0x7FF, b'\x82'),  # Module 1 switch ACK
        (0x7FF, b'\x01'),  # Module 2 bootup
        (0x7FF, b'\x81'),  # Module 2 addr ACK
        (0x7FF, b'\x82'),  # Module 2 switch ACK
    ])
    modules = sai_runtime.run_addressing(can, timeout_s=0.1)
    assert modules == [1, 2]
    sent_ids = [s[0] for s in can._sent]
    assert 0x000 in sent_ids
    assert 0x77F in sent_ids
    assert 0x7FE in sent_ids

def test_addressing_no_modules():
    can = MockCAN()
    modules = sai_runtime.run_addressing(can, timeout_s=0.1)
    assert modules == []


# === Task 4: Module Detection ===

def test_detect_modules_8di_8do():
    can = MockCAN()
    can._queue.append((0x701, b'\x05'))
    can._queue.append((0x702, b'\x05'))
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x01, 0x00, 0x00, 0x00])))
    can._queue.append((0x581, bytes([0x43, 0x18, 0x10, 0x03, 0x06, 0x00, 0x01, 0x00])))
    can._queue.append((0x582, bytes([0x43, 0x18, 0x10, 0x02, 0x05, 0x00, 0x00, 0x00])))
    can._queue.append((0x582, bytes([0x43, 0x18, 0x10, 0x03, 0x0A, 0x00, 0x01, 0x00])))
    detected = sai_runtime.detect_modules(can, [1, 2], heartbeat_timeout_ms=50)
    assert len(detected) == 2
    assert detected[0]["profile"]["name"] == "8DI"
    assert detected[1]["profile"]["name"] == "8DO"


# === Task 5: Parametrization ===

def test_parametrize_8di():
    can = MockCAN()
    detected = [{"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]}]
    for _ in range(3):
        can._queue.append((0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])))
    ok = sai_runtime.parametrize_modules(can, detected)
    assert ok is True
    # 3 SDO writes + 1 NMT = 4 sent messages
    sdo_writes = [s for s in can._sent if s[0] == 0x601]
    assert len(sdo_writes) == 3


# === Task 6: I/O Map Builder ===

def test_build_io_map_mixed():
    detected = [
        {"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 2, "profile": sai_runtime.MODULE_PROFILES[(5, 0x0001000A)]},
        {"node_id": 3, "profile": sai_runtime.MODULE_PROFILES[(2, 0x00010007)]},
    ]
    io_map = sai_runtime.build_io_map(detected)
    assert len(sai_runtime.digital_in) == 17   # [None] + 8(8DI) + 8(8DIO in)
    assert sai_runtime.digital_in[0] is None
    assert sai_runtime.digital_in[1] == False
    assert len(sai_runtime.digital_out) == 17  # [None] + 8(8DO) + 8(8DIO out)
    assert "digital_in" in io_map
    assert "digital_out" in io_map

def test_build_io_map_empty():
    detected = []
    io_map = sai_runtime.build_io_map(detected)
    assert len(sai_runtime.digital_in) == 1
    assert len(sai_runtime.digital_out) == 1


# === Task 7: PDO Decode/Encode ===

def test_decode_pdo_digital_in():
    sai_runtime.digital_in[:] = [None] + [False] * 8
    io_map = {"digital_in": [(2, 1, 8)], "analog_in": [], "counter": []}
    sai_runtime.decode_pdo(0x182, bytes([0x83]), io_map)
    assert sai_runtime.digital_in[1] == True
    assert sai_runtime.digital_in[2] == True
    assert sai_runtime.digital_in[3] == False
    assert sai_runtime.digital_in[8] == True

def test_encode_pdo_digital_out():
    sai_runtime.digital_out[:] = [None, True, False, True, False, False, False, False, True]
    io_map = {"digital_out": [(1, 1, 8)], "analog_out": []}
    frames = sai_runtime.encode_output_pdos(io_map)
    assert len(frames) == 1
    assert frames[0][0] == 0x201
    assert frames[0][1][0] == 0x85  # 0b10000101


# === Task 8: SPS Scan Helpers ===

def test_read_inputs_decodes_pdo():
    can = MockCAN()
    sai_runtime.digital_in[:] = [None] + [False] * 8
    io_map = {"digital_in": [(1, 1, 8)], "digital_out": [], "analog_in": [], "analog_out": [], "counter": []}
    can._queue.append((0x181, bytes([0xFF])))
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


# --- Task 10: Edge case tests ---

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
    # Values: 1000, 2000, 3000, 4000
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

def test_encode_pdo_analog_out():
    """Encode 4AO output: 4x 16-bit little-endian."""
    sai_runtime.analog_out[:] = [None, 1000, 2000, 3000, 4000]
    io_map = {"analog_out": [(1, 1, 4)], "digital_out": []}
    frames = sai_runtime.encode_output_pdos(io_map)
    assert len(frames) == 1
    assert frames[0][0] == 0x201
    assert frames[0][1] == bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F])

def test_unknown_module_skipped():
    """Unknown module gets profile=None, no crash."""
    detected = [{"node_id": 1, "profile": None, "product_code": 0xFF, "revision": 0xFF}]
    io_map = sai_runtime.build_io_map(detected)
    assert len(sai_runtime.digital_in) == 1  # only [None]

def test_dio_integration():
    """DIO module: contributes to both digital_in[] and digital_out[].
    Scenario: Node1=8DI, Node2=8DI, Node3=8DIO, Node4=8DO."""
    detected = [
        {"node_id": 1, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 2, "profile": sai_runtime.MODULE_PROFILES[(1, 0x00010006)]},
        {"node_id": 3, "profile": sai_runtime.MODULE_PROFILES[(2, 0x00010007)]},
        {"node_id": 4, "profile": sai_runtime.MODULE_PROFILES[(5, 0x0001000A)]},
    ]
    io_map = sai_runtime.build_io_map(detected)
    # digital_in: 8 (node1) + 8 (node2) + 8 (node3 DIO inputs) = 24
    assert len(sai_runtime.digital_in) == 25  # [None] + 24
    # digital_out: 8 (node3 DIO outputs) + 8 (node4) = 16
    assert len(sai_runtime.digital_out) == 17  # [None] + 16
    # Verify mappings
    assert io_map["digital_in"] == [(1, 1, 8), (2, 9, 8), (3, 17, 8)]
    assert io_map["digital_out"] == [(3, 1, 8), (4, 9, 8)]


passed = 0
failed = 0

def run_test(fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print("  PASS: {}".format(fn.__name__))
    except Exception as e:
        failed += 1
        print("  FAIL: {} — {}".format(fn.__name__, e))


if __name__ == '__main__':
    print("=== sai_runtime tests ===")
    run_test(test_recv_any_returns_message)
    run_test(test_recv_any_returns_none_on_timeout)
    run_test(test_sdo_upload_u32)
    run_test(test_sdo_upload_u32_timeout)
    run_test(test_sdo_download_1byte)
    run_test(test_sdo_download_1byte_timeout)
    run_test(test_addressing_two_modules)
    run_test(test_addressing_no_modules)
    run_test(test_detect_modules_8di_8do)
    run_test(test_parametrize_8di)
    run_test(test_build_io_map_mixed)
    run_test(test_build_io_map_empty)
    run_test(test_decode_pdo_digital_in)
    run_test(test_encode_pdo_digital_out)
    run_test(test_read_inputs_decodes_pdo)
    run_test(test_write_outputs_sends_pdo)
    run_test(test_build_io_map_with_counter)
    run_test(test_build_io_map_with_analog)
    run_test(test_decode_pdo_analog_in)
    run_test(test_decode_pdo_counter)
    run_test(test_encode_pdo_analog_out)
    run_test(test_unknown_module_skipped)
    run_test(test_dio_integration)
    print("\n{} passed, {} failed".format(passed, failed))
    if failed:
        sys.exit(1)

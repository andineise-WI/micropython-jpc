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
    print("\n{} passed, {} failed".format(passed, failed))
    if failed:
        sys.exit(1)

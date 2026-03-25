# test_main_integration.py — Integration tests for firmware boot + SPS loop
import sys
import time as _real_time

# MicroPython time shim for desktop testing
import time
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
        self._post_addressing = []
        self._addressing_done = False
    def recv(self):
        if self._queue:
            return self._queue.pop(0)
        return None
    def send(self, can_id, data):
        self._sent.append((can_id, bytes(data)))
        # After app-start broadcast, inject detect/param messages
        if can_id == 0x77F and not self._addressing_done:
            self._addressing_done = True
            self._queue.extend(self._post_addressing)
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


passed = 0
failed = 0

def run_test(fn):
    global passed, failed
    try:
        fn()
        print("  PASS:", fn.__name__)
        passed += 1
    except Exception as e:
        print("  FAIL:", fn.__name__, "->", e)
        failed += 1


def test_full_boot_sequence():
    """Test that init_firmware() runs all 6 phases with 1 8DI module."""
    can = MockCAN()
    # Phase 1: One module bootup sequence (consumed during addressing)
    can._queue.extend([
        (0x7FF, b'\x01'),  # bootup
        (0x7FF, b'\x81'),  # addr ACK
        (0x7FF, b'\x82'),  # switch ACK
    ])
    # Phase 3-5 messages: injected after APP_START broadcast
    can._post_addressing = [
        # Phase 3: Heartbeat
        (0x701, b'\x05'),
        # Phase 4: Identity (8DI: product=0x01, rev=0x00010006)
        (0x581, bytes([0x43, 0x18, 0x10, 0x02, 0x01, 0x00, 0x00, 0x00])),
        (0x581, bytes([0x43, 0x18, 0x10, 0x03, 0x06, 0x00, 0x01, 0x00])),
        # Phase 5: SDO ACKs (3 writes for 8DI)
        (0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
        (0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
        (0x581, bytes([0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ]

    io_map = sai_runtime.init_firmware(
        can,
        addressing_timeout_s=0.1,
        heartbeat_timeout_ms=50,
        addressing_start_delay_s=0,
    )

    assert io_map is not None
    assert len(sai_runtime.digital_in) == 9  # [None] + 8 DI channels
    assert sai_runtime.digital_in[0] is None
    assert sai_runtime.digital_in[1] == False


def test_boot_no_modules():
    """init_firmware with no modules produces empty I/O map."""
    can = MockCAN()
    io_map = sai_runtime.init_firmware(
        can,
        addressing_timeout_s=0.1,
        heartbeat_timeout_ms=50,
        addressing_start_delay_s=0,
    )
    assert io_map is not None
    assert len(sai_runtime.digital_in) == 1  # only [None]
    assert len(sai_runtime.digital_out) == 1


def test_sps_cycle_roundtrip():
    """Simulate one SPS cycle: read PDO input, run user logic, write PDO output."""
    can = MockCAN()
    sai_runtime.digital_in[:] = [None] + [False] * 8
    sai_runtime.digital_out[:] = [None] + [False] * 8
    io_map = {
        "digital_in": [(1, 1, 8)],
        "digital_out": [(2, 1, 8)],
        "analog_in": [],
        "analog_out": [],
        "counter": [],
    }
    # Simulate incoming PDO: all inputs ON
    can._queue.append((0x181, bytes([0xFF])))

    # Read inputs
    sai_runtime.read_inputs(can, io_map)
    assert sai_runtime.digital_in[1] == True
    assert sai_runtime.digital_in[8] == True

    # User logic: copy DI to DO
    for i in range(1, 9):
        sai_runtime.digital_out[i] = sai_runtime.digital_in[i]

    # Write outputs
    sai_runtime.write_outputs(can, io_map)
    assert len(can._sent) == 1
    assert can._sent[0][0] == 0x202  # 0x200 + node_id=2
    assert can._sent[0][1][0] == 0xFF


if __name__ == '__main__':
    print("=== integration tests ===")
    run_test(test_full_boot_sequence)
    run_test(test_boot_no_modules)
    run_test(test_sps_cycle_roundtrip)
    print()
    print("{} passed, {} failed".format(passed, failed))

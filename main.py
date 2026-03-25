# main.py — JackPack Control ESP32 Firmware Entry Point
"""Firmware: 6-phase boot + SPS scan loop with user_program.py."""
import time
import sai_runtime

try:
    from machine import CAN as MACHINE_CAN
except ImportError:
    MACHINE_CAN = None

try:
    from esp32 import CAN as ESP32_CAN
except ImportError:
    ESP32_CAN = None


class CANAdapter:
    """Wraps esp32.CAN to provide a unified send(id, data)/recv()->(id, data) API."""
    def __init__(self, raw_can):
        self._can = raw_can
    def send(self, can_id, data):
        # machine.CAN supports keyword args; esp32.CAN expects (data, id)
        try:
            self._can.send(id=can_id, data=bytes(data))
        except TypeError:
            self._can.send(list(data), can_id)
    def recv(self):
        if hasattr(self._can, "any") and not self._can.any():
            return None
        msg = self._can.recv()
        if msg is None:
            return None
        # machine.CAN returns (id, data), esp32.CAN returns tuple with payload at index 3
        if len(msg) >= 4:
            return (int(msg[0]), bytes(msg[3]))
        if len(msg) >= 2:
            return (int(msg[0]), bytes(msg[1]))
        return None
    def state(self):
        return self._can.state()


def _init_can():
    """Create CAN instance across both firmware variants."""
    if MACHINE_CAN is not None:
        # extmod machine_can.c: CAN index is 1-based and only bitrate is configured.
        raw_can = MACHINE_CAN(1, bitrate=250000)
        return CANAdapter(raw_can)

    if ESP32_CAN is not None:
        try:
            raw_can = ESP32_CAN(0, tx=5, rx=4, mode=ESP32_CAN.NORMAL, baudrate=250000)
            return CANAdapter(raw_can)
        except OSError:
            # TWAI driver still active from previous soft reboot; force hard reset.
            import machine as _machine
            print("[MAIN] CAN driver busy, hard reset...")
            _machine.reset()

    raise RuntimeError("No CAN implementation available")


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
    can = _init_can()
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

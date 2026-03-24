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
    can = CAN(1, bitrate=250000)
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

# user_program.py — Default Blockly Program (replace via WebSerial)
"""Simple demo program: blink DO1 of the first DO module."""
import time
from sai_runtime import digital_in, digital_out, analog_in, analog_out, counter


_blink_last_ms = 0
_blink_state = False


def setup():
    """Called once after firmware init completes."""
    global _blink_last_ms, _blink_state
    _blink_last_ms = time.ticks_ms()
    _blink_state = False
    if len(digital_out) > 1:
        digital_out[1] = False


def loop():
    """Called every ~10ms by the SPS scan loop."""
    global _blink_last_ms, _blink_state

    # Only blink if at least one digital output channel exists.
    if len(digital_out) <= 1:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _blink_last_ms) >= 500:
        _blink_last_ms = now
        _blink_state = not _blink_state
        digital_out[1] = _blink_state

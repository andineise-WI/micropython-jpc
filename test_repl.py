import serial, time

s = serial.Serial('COM5', 115200, timeout=3)
time.sleep(1)

# Send Ctrl-C to interrupt any running code, then enter REPL
s.write(b'\x03\x03\r\n')
time.sleep(1)
s.read(s.in_waiting)  # Clear buffer

# Test 1: sys.version
s.write(b'import sys; print("VER:", sys.version)\r\n')
time.sleep(1)
print(s.read(s.in_waiting).decode('utf-8', errors='replace'))

# Test 2: platform + memory
s.write(b'import gc; gc.collect(); print("FREE_MEM:", gc.mem_free())\r\n')
time.sleep(1)
print(s.read(s.in_waiting).decode('utf-8', errors='replace'))

# Test 3: CAN module
s.write(b'from machine import CAN; print("CAN_CLASS:", CAN)\r\n')
time.sleep(1)
print(s.read(s.in_waiting).decode('utf-8', errors='replace'))

# Test 4: sai module
s.write(b'import sai; print("SAI_MODULE:", sai)\r\n')
time.sleep(1)
print(s.read(s.in_waiting).decode('utf-8', errors='replace'))

s.close()

# ============================================================================
# SAI MODULE AUTO-ADDRESSING FOR MICROPYTHON FIRMWARE
# ============================================================================
#
# This script implements a 3-phase workflow for ESP32 SAI module management:
#
# [PHASE 1] ADDRESSING (Firmware - essential)
#   - Auto-discovers SAI modules on CAN bus
#   - Assigns unique node IDs (1, 2, 3, ...)
#   - Starts module applications
#   - Function: test_addressing()
#
# [PHASE 2] CANOPEN CONFIGURATION (Application - optional)
#   - Queries module identities (0x1018:2,3)
#   - Matches against known MODULE_PROFILES
#   - Applies role-specific SDO parameters
#   - Function: configure_canopen()
#
# [PHASE 3] CYCLIC OPERATION (Monitoring - optional)
#   - Observes heartbeats, PDOs, cyclic traffic
#   - Validates commissioning success
#   - Function: monitor_cyclic_traffic() / monitor_continuous()
#
# Flow:
#   1. debug_can_receive() - Check CAN bus connectivity
#   2. test_addressing() - Perform auto-addressing (returns module list)
#   3. configure_canopen() - Apply CANopen configuration [OPTIONAL]
#   4. monitor_cyclic_traffic() - Monitor cyclic operation [OPTIONAL]
#
# ============================================================================
"""SAI automatic addressing on ESP32 via bootloader (0x7FE/0x7FF).

Provides addressing-only firmware integration and modular configuration/monitoring.
"""
import time
from machine import CAN

# Protocol constants
BOOTLOADER_TX = 0x7FE
BOOTLOADER_RX = 0x7FF
APP_START_BROADCAST = 0x77F

# CANopen defaults
NMT_ID = 0x000

# Identity signatures from trace (0x1018:2, 0x1018:3)
# Key: (product_code, revision) - matches CANopen identity object subindices 2 and 3
# Values: module name, description, and SDO configuration writes (index, subindex, value)
MODULE_PROFILES = {
    # 8DI - 8 Digital Inputs
    (1, 0x00010006): {
        "name": "8DI",
        "description": "8 Digital Inputs",
        "writes": [
            (0x2000, 0x00, 0x00),  # desina configuration - enable default
            (0x2007, 0x01, 0x55),  # filter setting 1 - 5ms per input
            (0x2007, 0x02, 0x55),  # filter setting 2 - 5ms per input
        ],
    },
    
    # 8DO - 8 Digital Outputs
    (5, 0x0001000A): {
        "name": "8DO",
        "description": "8 Digital Outputs",
        "writes": [
            (0x2005, 0x00, 0x00),  # output failure behavior - default (no safe state)
            (0x2006, 0x00, 0x00),  # secure state configuration - all outputs off
        ],
    },
    
    # 8DIO - 8 Digital In/Outputs
    (2, 0x00010007): {
        "name": "8DIO",
        "description": "8 Digital In/Outputs",
        "writes": [
            (0x2000, 0x00, 0x00),  # input desina configuration - enable default
            (0x2001, 0x00, 0x00),  # output configuration - enable all
            (0x2005, 0x00, 0x00),  # output failure behavior - default
            (0x2006, 0x00, 0x00),  # secure state configuration - all off
            (0x2007, 0x01, 0x55),  # filter setting 1
            (0x2007, 0x02, 0x55),  # filter setting 2
        ],
    },
    
    # 4AI - 4 Analog Inputs (e.g., temperature or 0-10V / 4-20mA)
    (3, 0x00010008): {
        "name": "4AI",
        "description": "4 Analog Inputs",
        "writes": [
            (0x2002, 0x00, 0x05),  # cycle time configuration - 5ms
            (0x2004, 0x00, 0x00),  # analog input configuration - default ranges
        ],
    },
    
    # 4AO - 4 Analog Outputs
    (4, 0x00010009): {
        "name": "4AO",
        "description": "4 Analog Outputs",
        "writes": [
            (0x2003, 0x00, 0x00),  # output configuration - default
            (0x2005, 0x00, 0x00),  # output failure behavior - default
        ],
    },
    
    # Counter Module - 2 Counter Channels
    (6, 0x0001000B): {
        "name": "CNT",
        "description": "Counter Module",
        "writes": [
            (0x2101, 0x00, 0x00),  # programmable preset value - 0
            (0x2102, 0x01, 0x00),  # control byte channel 1 - default
            (0x2102, 0x02, 0x00),  # control byte channel 2 - default
            (0x2103, 0x01, 0x00),  # status byte channel 1 - default
            (0x2103, 0x02, 0x00),  # status byte channel 2 - default
            (0x2105, 0x00, 0x00),  # settings - default
        ],
    },
}

def recv_any(can, timeout_ms=100):
    """Receive any CAN message with timeout."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = can.recv()
        if msg is not None:
            return msg
        time.sleep_ms(1)
    return None

def monitor_all_messages(duration_s=30, bitrate=250000):
    """Monitor and display ALL incoming CAN messages on serial monitor.
    
    Displays every message with timestamp, CAN ID, and hex data.
    Press Ctrl+C to stop early.
    
    Args:
        duration_s: How long to listen (default 30 seconds)
        bitrate: CAN bitrate (default 250kbps)
    """
    print("=" * 70)
    print("CAN MESSAGE MONITOR - All Incoming Frames")
    print("=" * 70)
    print("Bitrate: {} bps, Duration: {} seconds".format(bitrate, duration_s))
    print("Press Ctrl+C to stop early")
    print("-" * 70)
    print("{:<10} {:<8} {:<8} {}".format("Time(ms)", "CAN ID", "DLC", "Data (hex)"))
    print("-" * 70)
    
    try:
        can = CAN(1, bitrate=bitrate)
        can.set_filters(None)  # Accept all messages
        
        # Drain any stale messages
        while can.recv() is not None:
            pass
        
        t_start = time.ticks_ms()
        msg_count = 0
        duration_ms = duration_s * 1000
        
        while time.ticks_diff(time.ticks_ms(), t_start) < duration_ms:
            msg = can.recv()
            if msg is not None:
                elapsed = time.ticks_diff(time.ticks_ms(), t_start)
                msg_id = msg[0]
                data = bytes(msg[1])
                dlc = len(data)
                hex_data = ' '.join('{:02X}'.format(b) for b in data)
                
                print("{:<10} 0x{:<6X} {:<8} {}".format(elapsed, msg_id, dlc, hex_data))
                msg_count += 1
            else:
                time.sleep_ms(1)
        
        can.deinit()
        print("-" * 70)
        print("Monitor stopped. Total messages received: {}".format(msg_count))
        print("=" * 70)
        
    except KeyboardInterrupt:
        can.deinit()
        print("\n*** Monitor interrupted by user ***")
        print("Total messages before interruption: {}".format(msg_count))
        print("=" * 70)

def monitor_continuous(bitrate=250000):
    """Monitor CAN messages continuously until Ctrl+C is pressed.
    
    Useful for REPL-based monitoring without a pre-defined timer.
    Every received message is displayed with timestamp and hex data.
    
    Args:
        bitrate: CAN bitrate (default 250kbps)
    
    Usage:
        >>> from test_sai_addressing import monitor_continuous
        >>> monitor_continuous()  # Ctrl+C to stop
    """
    print("=" * 70)
    print("CAN MESSAGE MONITOR - Continuous (Ctrl+C to stop)")
    print("=" * 70)
    print("Bitrate: {} bps".format(bitrate))
    print("-" * 70)
    print("{:<10} {:<8} {:<8} {}".format("Time(ms)", "CAN ID", "DLC", "Data (hex)"))
    print("-" * 70)
    
    try:
        can = CAN(1, bitrate=bitrate)
        can.set_filters(None)
        
        # Drain stale
        while can.recv() is not None:
            pass
        
        t_start = time.ticks_ms()
        msg_count = 0
        
        while True:
            msg = can.recv()
            if msg is not None:
                elapsed = time.ticks_diff(time.ticks_ms(), t_start)
                msg_id = msg[0]
                data = bytes(msg[1])
                dlc = len(data)
                hex_data = ' '.join('{:02X}'.format(b) for b in data)
                
                print("{:<10} 0x{:<6X} {:<8} {}".format(elapsed, msg_id, dlc, hex_data))
                msg_count += 1
            else:
                time.sleep_ms(1)
    
    except KeyboardInterrupt:
        can.deinit()
        print("\n" + "=" * 70)
        print("Monitor stopped by user after {} messages".format(msg_count))
        print("=" * 70)

def wait_sdo_response(can, resp_id, timeout_ms=500):
    """Wait for a matching SDO response frame."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        msg = recv_any(can, timeout_ms=50)
        if msg is None:
            continue
        msg_id = msg[0]
        data = bytes(msg[1])
        hex_data = ' '.join('{:02X}'.format(b) for b in data)
        print("  RX: ID=0x{:03X} DLC={} DATA=[{}]".format(msg_id, len(data), hex_data))
        if msg_id == resp_id and len(data) >= 4:
            return data
    return None

def sdo_upload(can, node_id, index, subindex):
    """Send SDO upload request and print response."""
    req_id = 0x600 + node_id
    resp_id = 0x580 + node_id
    req = bytes([0x40, index & 0xFF, (index >> 8) & 0xFF, subindex, 0, 0, 0, 0])
    print("  TX: ID=0x{:03X} SDO upload idx=0x{:04X} sub=0x{:02X}".format(req_id, index, subindex))
    can.send(req_id, req)
    return wait_sdo_response(can, resp_id)

def sdo_upload_u32(can, node_id, index, subindex):
    """Read a 32-bit value via SDO upload."""
    resp = sdo_upload(can, node_id, index, subindex)
    if resp is None or len(resp) < 8:
        return None
    if resp[0] != 0x43:
        return None
    return resp[4] | (resp[5] << 8) | (resp[6] << 16) | (resp[7] << 24)

def sdo_download_1byte(can, node_id, index, subindex, value):
    """Send SDO expedited 1-byte download and wait for ack."""
    req_id = 0x600 + node_id
    resp_id = 0x580 + node_id
    req = bytes([0x2F, index & 0xFF, (index >> 8) & 0xFF, subindex, value & 0xFF, 0, 0, 0])
    print("  TX: ID=0x{:03X} SDO write idx=0x{:04X} sub=0x{:02X} val=0x{:02X}".format(
        req_id, index, subindex, value & 0xFF))
    can.send(req_id, req)
    resp = wait_sdo_response(can, resp_id)
    return resp is not None and len(resp) >= 1 and resp[0] == 0x60

def send_nmt(can, command, node_id=0):
    """Send NMT command."""
    can.send(NMT_ID, bytes([command & 0xFF, node_id & 0xFF]))
    print("  TX: ID=0x000 NMT cmd=0x{:02X} node=0x{:02X}".format(command, node_id))

def configure_canopen(can, modules):
    """[PHASE 2] CANopen configuration - APPLICATION FUNCTION.
    
    Configures modules via CANopen protocol after successful addressing (PHASE 1).
    
    Actions:
        1. Read identity objects (0x1018:2 and 0x1018:3) from each module
        2. Match against known MODULE_PROFILES (8DI, 8DO, 4AI, 4AO, CNT, etc.)
        3. Apply role-specific SDO parameter writes
        4. Transition from PRE_OPERATIONAL → OPERATIONAL
    
    Args:
        can: Initialized CAN object (already initialized from PHASE 1)
        modules: List of node IDs from test_addressing() [1, 2, 3, ...]
    
    Requires:
        - Modules already addressed and in PRE_OPERATIONAL state
        - MODULE_PROFILES defined with SDO write instructions
    
    Next: monitor_cyclic_traffic() to verify success
    """
    if not modules:
        print("\n[6] No modules to configure")
        return

    print("\n[6] Reading identity objects (0x1018) ...")
    detected = []
    for nid in modules:
        print("    Querying node {} identity...".format(nid))
        ident2 = sdo_upload_u32(can, nid, 0x1018, 2)
        ident3 = sdo_upload_u32(can, nid, 0x1018, 3)
        ident4 = sdo_upload_u32(can, nid, 0x1018, 4)
        key = (ident2, ident3)
        profile = MODULE_PROFILES.get(key)
        
        if profile is not None:
            profile_name = "{} ({})".format(profile["name"], profile["description"])
            print("    -> Node {} matched: {}".format(nid, profile_name))
        else:
            profile_name = "UNKNOWN - 0x1018:2=0x{:08X}, 0x1018:3=0x{:08X}".format(
                ident2 if ident2 is not None else 0,
                ident3 if ident3 is not None else 0,
            )
            print("    -> Node {} UNKNOWN identity: {}".format(nid, profile_name))
        
        detected.append((nid, profile, ident2, ident3, ident4))

    print("\n[7] Enter NMT Pre-Operational ...")
    send_nmt(can, 0x80, 0x00)
    time.sleep_ms(100)

    print("\n[8] Applying module-specific CANopen parameters ...")
    for nid, profile, ident2, ident3, ident4 in detected:
        if profile is None:
            print("    Node {}: identity 0x{:08X}:0x{:08X} UNKNOWN - skipping SDO writes".format(
                nid, ident2 if ident2 is not None else 0, ident3 if ident3 is not None else 0))
            continue
        
        print("    Node {}: {} ({})".format(nid, profile["name"], profile["description"]))
        success_count = 0
        fail_count = 0
        
        for index, subindex, value in profile["writes"]:
            ok = sdo_download_1byte(can, nid, index, subindex, value)
            if ok:
                success_count += 1
            else:
                print("      ERROR writing idx=0x{:04X}:0x{:02X}=0x{:02X}".format(
                    index, subindex, value))
                fail_count += 1
        
        print("      -> {} success, {} failed".format(success_count, fail_count))

    print("\n[9] Start NMT Operational ...")
    send_nmt(can, 0x01, 0x00)
    time.sleep_ms(100)

def monitor_cyclic_traffic(can, duration_ms=5000):
    """[PHASE 3] Cyclic CANopen communication verification - MONITORING FUNCTION.
    
    Monitors cyclic CANopen traffic after successful addressing (PHASE 1) 
    and optional configuration (PHASE 2).
    
    Observes:
        - PDO messages (heartbeats, process data)
        - Module state transitions
        - Broadcast commands
    
    Expected messages:
            0x700+N: Heartbeat from node N
            0x281/0x282: PDO from nodes 1/2
            0x77F: Broadcast/APP_START signals
            0x601/0x581: SDO requests/responses (from PHASE 2)
    
        Args:
            can: Initialized CAN object (from PHASE 1 or 2)
            duration_ms: Monitoring duration in milliseconds (default 5s)
    
        Returns:
            Dictionary of observed message IDs and their counts
        """
    print("\n[10] Monitoring cyclic CANopen traffic ({} ms)...".format(duration_ms))
    print("      (0x7XX=heartbeat, 0x28X=PDO, 0x77F=broadcast)")
    t_start = time.ticks_ms()
    seen = {}
    msg_count = 0
    
    while time.ticks_diff(time.ticks_ms(), t_start) < duration_ms:
        msg = recv_any(can, timeout_ms=100)
        if msg is None:
            continue
        msg_id = msg[0]
        data = bytes(msg[1])
        hex_data = ' '.join('{:02X}'.format(b) for b in data)
        print("    RX: ID=0x{:03X} DLC={} DATA=[{}]".format(msg_id, len(data), hex_data))
        seen[msg_id] = seen.get(msg_id, 0) + 1
        msg_count += 1

    print("\n    Traffic summary ({} messages total):".format(msg_count))
    if seen:
        for mid in sorted(seen):
            # Decode message type
            if mid >= 0x700 and mid <= 0x7FF:
                msg_type = "Heartbeat from node {}".format(mid - 0x700)
            elif mid >= 0x281 and mid <= 0x2FF:
                msg_type = "PDO from node {}".format(mid - 0x280)
            elif mid == 0x77F:
                msg_type = "Broadcast/APP_START"
            elif mid >= 0x601 and mid <= 0x67F:
                msg_type = "SDO request to node {}".format(mid - 0x600)
            elif mid >= 0x581 and mid <= 0x5FF:
                msg_type = "SDO response from node {}".format(mid - 0x580)
            else:
                msg_type = "Other"
            print("      0x{:03X}: {} messages ({})".format(mid, seen[mid], msg_type))
    else:
        print("    *** NO CYCLIC TRAFFIC DETECTED ***")

def debug_can_receive(duration_s=10, bitrate=250000):
    """Debug function: check if any CAN bus signals are received.

    Listens on the CAN bus and prints every received message with
    timing info and a summary of all unique IDs seen.
    """
    print("=" * 50)
    print("CAN Bus Receive Debug")
    print("  Bitrate: {} bps".format(bitrate))
    print("  Duration: {} s".format(duration_s))
    print("=" * 50)

    can = CAN(1, bitrate=bitrate)
    can.set_filters(None)
    print("\nCAN initialized. State:", can.state())

    # Drain any stale messages
    drained = 0
    while can.recv() is not None:
        drained += 1
    if drained:
        print("Drained {} stale message(s)".format(drained))

    print("\nListening for CAN traffic...\n")

    count = 0
    ids_seen = {}
    first_msg_ms = None
    last_msg_ms = None
    t_start = time.ticks_ms()
    duration_ms = duration_s * 1000

    while time.ticks_diff(time.ticks_ms(), t_start) < duration_ms:
        msg = can.recv()
        if msg is not None:
            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, t_start)
            msg_id = msg[0]
            data = bytes(msg[1])
            hex_data = ' '.join('{:02X}'.format(b) for b in data)

            if first_msg_ms is None:
                first_msg_ms = elapsed
            last_msg_ms = elapsed

            ids_seen[msg_id] = ids_seen.get(msg_id, 0) + 1
            count += 1

            print("  [{:7d} ms] ID=0x{:03X} DLC={} DATA=[{}]".format(
                elapsed, msg_id, len(data), hex_data))
        else:
            time.sleep_ms(1)

    # Summary
    print("\n" + "-" * 50)
    print("SUMMARY:")
    print("  CAN state: {}".format(can.state()))
    print("  Total messages received: {}".format(count))

    if count > 0:
        span_ms = time.ticks_diff(last_msg_ms, first_msg_ms) if last_msg_ms != first_msg_ms else 1
        rate = count * 1000.0 / span_ms
        print("  First message at: {} ms".format(first_msg_ms))
        print("  Last message at:  {} ms".format(last_msg_ms))
        print("  Approx rate: {:.1f} msg/s".format(rate))
        print("  Unique IDs seen: {}".format(len(ids_seen)))
        for mid in sorted(ids_seen):
            print("    0x{:03X} : {} message(s)".format(mid, ids_seen[mid]))
    else:
        print("  *** NO MESSAGES RECEIVED ***")
        print("  Possible causes:")
        print("    - No devices on the bus")
        print("    - Wrong bitrate (tried {} bps)".format(bitrate))
        print("    - CAN wiring issue (TX=GPIO5, RX=GPIO4)")
        print("    - Missing bus termination (120 Ohm)")
        print("    - Transceiver not powered")

    print("-" * 50)
    can.deinit()
    return count


def test_addressing_debug():
    """Debug version: Show ALL received messages during addressing."""
    print("=" * 70)
    print("SAI Automatic Addressing - DEBUG MODE (Show ALL Messages)")
    print("=" * 70)

    # Initialize CAN
    print("\n[1] Initializing CAN at 250kbps...")
    can = CAN(1, bitrate=250000)
    can.set_filters(None)
    print("    ✓ CAN initialized")
    print("    ✓ CAN state: {}".format(can.state()))

    # Drain stale
    print("\n[1b] Draining any stale messages...")
    drained = 0
    while can.recv() is not None:
        drained += 1
    print("    Drained {} stale message(s)".format(drained))

    # Send NMT Reset
    print("\n[2] Sending NMT Reset to all nodes...")
    can.send(0x000, bytes([0x81, 0x00]))
    print("    ✓ NMT Reset sent (0x000: 0x81 0x00)")
    time.sleep(0.5)
    
    # Show what comes back after NMT Reset
    print("\n[2b] Looking for responses to NMT Reset (listening 2 seconds)...")
    t_start = time.ticks_ms()
    rx_count = 0
    all_ids = {}
    
    while time.ticks_diff(time.ticks_ms(), t_start) < 2000:
        msg = can.recv()
        if msg is not None:
            msg_id = msg[0]
            data = bytes(msg[1])
            hex_data = ' '.join('{:02X}'.format(b) for b in data)
            print("      RX: 0x{:03X} [{}]".format(msg_id, hex_data))
            all_ids[msg_id] = all_ids.get(msg_id, 0) + 1
            rx_count += 1
        else:
            time.sleep_ms(10)
    
    print("    Received {} message(s) in 2 seconds".format(rx_count))
    if all_ids:
        print("    Unique IDs:")
        for mid in sorted(all_ids):
            print("      0x{:03X}: {} times".format(mid, all_ids[mid]))
    else:
        print("    *** NO MESSAGES AT ALL ***")
    
    can.deinit()
    return all_ids
    """[PHASE 1] SAI automatic addressing - FIRMWARE FUNCTION.
    
    Auto-discovers and addresses SAI modules on CAN bus using bootloader protocol.
    This is the core firmware function for SAI module commissioning.
    
    Protocol:
        1. Send NMT Reset (0x000: 0x81 0x00)
        2. Wait for bootup announcements (0x7FF: 0x01)
        3. Assign addresses via handshake:
             - Send 0x7FE: [0x81, node_id] → Wait 0x7FF: 0x81 ACK
             - Send 0x7FE: [0x82, node_id] → Wait 0x7FF: 0x82 ACK
        4. Repeat for each module or timeout (1s)
        5. Start applications:
             - Send 0x77F: [0x7F] (broadcast)
             - Send 0x7FE: [0x83, node_id] for each module
             - Send 0x77F: [0x7F] (broadcast)
    
    Returns:
        list: Node IDs of successfully addressed modules [1, 2, 3, ...]
    
    Note:
        After this function returns, modules are in PRE_OPERATIONAL state.
        Next steps (optional): configure_canopen() → monitor_cyclic_traffic()
        """
    print("=" * 70)
    print("SAI Automatic Addressing")
    print("=" * 70)

    # Initialize CAN
    print("\n[1] Initializing CAN at 250kbps...")
    can = CAN(1, bitrate=250000)
    can.set_filters(None)
    print("    ✓ CAN initialized")
    print("    ✓ CAN state: {}".format(can.state()))

    # Send NMT Reset
    print("\n[2] Sending NMT Reset to all nodes...")
    can.send(0x000, bytes([0x81, 0x00]))
    print("    ✓ NMT Reset sent (0x000: 0x81 0x00)")
    time.sleep(0.5)
    
    # Drain stale
    while can.recv() is not None:
        pass

    # State machine: addressing loop (proven from main.py)
    print("\n[3] Auto-addressing state machine...")
    print("    Waiting for bootup announcements from modules...")
    
    addr_step = 0
    module_count = 1
    modules = []
    start_time = time.time()
    
    while True:
        msg = can.recv()
        if msg is not None:
            msg_id = msg[0]
            data = bytes(msg[1])
            hex_data = ' '.join('{:02X}'.format(b) for b in data)
            print("  RX: 0x{:03X} [{}] (step={})".format(msg_id, hex_data, addr_step))
            
            # Step 0: Wait for bootup
            if addr_step == 0:
                print("    [DEBUG] Checking bootup: msg_id=0x{:03X} (expect 0x7FF), len={}, data[0]={} (expect 0x01)".format(
                    msg_id, len(data), data[0] if len(data) > 0 else None))
                if msg_id == 0x7FF and len(data) > 0 and data[0] == 0x01:
                    print("    ✓ Bootup detected - module #{} entering addressing".format(module_count))
                    addr_step = 1
                    continue
                elif msg_id != 0x7FF:
                    print("    [DEBUG] Ignoring - wrong CAN ID (not 0x7FF)")
                elif len(data) == 0:
                    print("    [DEBUG] Ignoring - no data payload")
                elif data[0] != 0x01:
                    print("    [DEBUG] Ignoring - first byte is 0x{:02X}, not bootup (0x01)".format(data[0]))
            
            # Step 1: Send address
            if addr_step == 1:
                print("  TX: 0x7FE [0x81, {}] - assigning address".format(module_count))
                can.send(0x7FE, bytes([0x81, module_count]))
                addr_step = 2
                continue
            
            # Step 2: Wait for address ACK
            if addr_step == 2:
                if msg_id == 0x7FF and len(data) > 0 and data[0] == 0x81:
                    print("    ✓ Address ACK received")
                    addr_step = 3
                    continue
            
            # Step 3: Send switch-on
            if addr_step == 3:
                print("  TX: 0x7FE [0x82, {}] - switching on".format(module_count))
                can.send(0x7FE, bytes([0x82, module_count]))
                addr_step = 4
                continue
            
            # Step 4: Wait for switch-on ACK
            if addr_step == 4:
                if msg_id == 0x7FF and len(data) > 0 and data[0] == 0x82:
                    print("    ✓ Switch-on ACK received - module #{} addressed OK".format(module_count))
                    modules.append(module_count)
                    module_count += 1
                    start_time = time.time()
                    addr_step = 5
                    continue
            
            # Step 5: Wait for next bootup or timeout
            if addr_step == 5:
                if msg_id == 0x7FF and len(data) > 0 and data[0] == 0x01:
                    print("    ✓ Next module bootup detected")
                    addr_step = 0  # Loop back to address next
                    continue
        
        else:
            time.sleep_ms(10)
        
        # Timeout check in step 5 (no messages for 1 second)
        if addr_step == 5:
            elapsed = time.time() - start_time
            if elapsed >= 1.0:
                print("    [timeout] No bootup for 1.0s - proceeding to app start (step 6)")
                addr_step = 6
        
        # Step 6: Send app start broadcasts
        if addr_step == 6:
            print("\n[4] Starting applications on {} module(s)...".format(len(modules)))
            print("  TX: 0x77F [0x7F] (broadcast)")
            can.send(0x77F, bytes([0x7F]))
            time.sleep(0.01)
            
            for nid in modules:
                print("  TX: 0x7FE [0x83, {}] (start app for module {})".format(nid, nid))
                can.send(0x7FE, bytes([0x83, nid]))
                time.sleep(0.01)
            
            print("  TX: 0x77F [0x7F] (broadcast)")
            can.send(0x77F, bytes([0x7F]))
            time.sleep(0.5)
            addr_step = 7
            break  # Exit state machine

    print("\n" + "=" * 70)
    print("ADDRESSING COMPLETE")
    print("  Modules found: {}".format(len(modules)))
    print("  Node IDs: {}".format(modules))
    print("=" * 70)

    can.deinit()
    return modules

# ============================================================================
# MAIN EXECUTION - 3-PHASE WORKFLOW
# ============================================================================

# Select workflow mode
# Options: "addressing_only" (production), "debug_can_first" (diagnostic), 
#          "debug_addressing_only" (show all messages during addressing), "full_workflow" (dev)
WORKFLOW_MODE = "debug_addressing_only"

if WORKFLOW_MODE == "addressing_only":
    # PHASE 1 ONLY: Firmware addressing (production mode)
    print("\n" + "=" * 70)
    print("WORKFLOW: Addressing Only (Firmware Mode)")
    print("=" * 70)
    
    modules = test_addressing()
    print("\n■ PHASE 1 COMPLETE: Addressing finished")
    print("  Modules ready with node IDs: {}".format(modules))
    print("  (Modules are in PRE_OPERATIONAL state)")

elif WORKFLOW_MODE == "debug_can_first":
    # Debug-only: Monitor CAN traffic without addressing
    print("\n" + "=" * 70)
    print("WORKFLOW: CAN Bus Diagnostics Only")
    print("=" * 70)
    
    rx_count = debug_can_receive(duration_s=10)
    if rx_count > 0:
        print("\nCAN traffic OK - ready for addressing. Launch with WORKFLOW_MODE='addressing_only'")
    else:
        print("\nNo CAN traffic detected - check hardware/wiring/termination")

elif WORKFLOW_MODE == "debug_addressing_only":
    # Debug-only: Show all CAN messages during addressing attempt
    print("\n" + "=" * 70)
    print("WORKFLOW: Debug Addressing (Show ALL messages)")
    print("=" * 70)
    
    all_ids = test_addressing_debug()
    print("\n■ DEBUG COMPLETE")
    if not all_ids:
        print("  ⚠ NO MESSAGES RECEIVED AFTER NMT RESET!")
        print("  This suggests:")
        print("    1. Modules not powered or connected")
        print("    2. Wrong bitrate (try 250kbps vs 1Mbps)")
        print("    3. Modules don't respond to NMT Reset")
        print("  Try: WORKFLOW_MODE='debug_can_first' to see initial messages")

elif WORKFLOW_MODE == "addressing_only":
    # PHASE 1 + 2 + 3: Full commissioning (development/test mode)
    print("\n" + "=" * 70)
    print("WORKFLOW: Full Commissioning")
    print("=" * 70)
    
    # PHASE 1: Addressing
    print("\n--- PHASE 1: Auto-Addressing ---")
    modules = test_addressing()
    print("\n■ PHASE 1 COMPLETE: {} modules addressed".format(len(modules)))
    
    # PHASE 2: CANopen Configuration
    if modules:
        print("\n--- PHASE 2: CANopen Configuration ---")
        can = CAN(1, bitrate=250000)
        can.set_filters(None)
        configure_canopen(can, modules)
        print("\n■ PHASE 2 COMPLETE: Modules configured")
        
        # PHASE 3: Cyclic Monitoring
        print("\n--- PHASE 3: Cyclic Operation Monitoring ---")
        monitor_cyclic_traffic(can, duration_ms=5000)
        print("\n■ PHASE 3 COMPLETE: Cyclic traffic verified")
        can.deinit()

else:
    print("Unknown WORKFLOW_MODE: {}".format(WORKFLOW_MODE))

#!/usr/bin/env python3
import subprocess
import sys
import time
import select

def scan_bluetooth_devices():
    """Scan for Bluetooth devices and print them"""
    # First, turn on power if not already
    subprocess.run(['bluetoothctl', 'power', 'on'], capture_output=True)

    process = subprocess.Popen(
        ['bluetoothctl'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Start scan
    process.stdin.write('scan on\n')
    process.stdin.flush()

    print("SCAN_STARTED", flush=True)

    seen_devices = set()

    try:
        # Read output for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            # Use select to check if there's data available
            ready = select.select([process.stdout], [], [], 0.5)
            if not ready[0]:
                continue

            line = process.stdout.readline()
            if not line:
                break

            # Debug: print raw line
            # print(f"DEBUG: {line.strip()}", flush=True)

            # Look for [NEW] Device lines or [CHG] Device lines
            if ('NEW' in line or 'CHG' in line) and 'Device' in line:
                parts = line.split('Device ', 1)
                if len(parts) > 1:
                    device_info = parts[1].strip()
                    # Format: MAC NAME
                    device_parts = device_info.split(' ', 1)
                    if len(device_parts) > 0:
                        mac = device_parts[0]
                        name = device_parts[1] if len(device_parts) > 1 else mac

                        # Validate MAC address format
                        if ':' in mac and len(mac) >= 17:
                            if mac not in seen_devices:
                                seen_devices.add(mac)
                                print(f"FOUND|{mac}|{name}", flush=True)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"ERROR|{str(e)}", flush=True)
    finally:
        # Stop scan
        try:
            process.stdin.write('scan off\n')
            process.stdin.write('quit\n')
            process.stdin.flush()
        except:
            pass
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()

        print(f"SCAN_FINISHED|{len(seen_devices)}", flush=True)

if __name__ == '__main__':
    scan_bluetooth_devices()

import os
import re
import subprocess

def kill_port_8000():
    # Run netstat
    output = subprocess.check_output("netstat -ano | findstr :8000", shell=True).decode()
    print("Netstat output:\n", output)
    
    pids = set()
    for line in output.splitlines():
        # Line format: TCP 127.0.0.1:8000 0.0.0.0:0 LISTENING 1234
        parts = line.strip().split()
        if len(parts) >= 5 and "LISTENING" in parts:
            pid = parts[-1]
            pids.add(pid)
            
    print(f"Found PIDs: {pids}")
    
    for pid in pids:
        if pid == "0": continue
        try:
            print(f"Killing PID {pid}")
            subprocess.run(["taskkill", "/F", "/PID", pid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Error killing {pid}: {e}")

if __name__ == "__main__":
    kill_port_8000()

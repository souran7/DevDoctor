"""Cross-platform port scanning, process inspection, and process termination utilities."""

from __future__ import annotations

import csv
import io
import os
import re
import signal
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from devdoctor.utils.platform_info import is_windows


@dataclass
class PortListenerInfo:
    """Information about a process listening on a network port."""
    port: int
    pid: int
    process_name: str
    command_line: Optional[str] = None


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a port is currently occupied or listening."""
    # First, test connecting to host:port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        result = s.connect_ex((host, port))
        if result == 0:
            return True

    # Check 0.0.0.0
    if host == "127.0.0.1":
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("0.0.0.0", port)) == 0:
                return True

    # Also test binding: if bind fails with EADDRINUSE, it is in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            s.bind((host, port))
        return False
    except OSError:
        return True


def get_process_name_by_pid(pid: int) -> str:
    """Look up the process name for a given PID."""
    if pid <= 0:
        return "unknown"

    if is_windows():
        try:
            cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            reader = csv.reader(io.StringIO(out.strip()))
            for row in reader:
                if row and len(row) > 0 and row[0].strip():
                    return row[0].strip()
        except Exception:
            pass
        return "unknown"

    # Unix-like (macOS / Linux)
    try:
        out = subprocess.check_output(["ps", "-p", str(pid), "-o", "comm="], text=True, stderr=subprocess.DEVNULL)
        return out.strip() or "unknown"
    except Exception:
        return "unknown"


def get_port_listener_info(port: int) -> Optional[PortListenerInfo]:
    """Identify the PID and process name listening on a specific port."""
    if not is_port_in_use(port):
        return None

    if is_windows():
        try:
            out = subprocess.check_output("netstat -ano -p tcp", shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                line = line.strip()
                if not line or "LISTENING" not in line:
                    continue
                parts = re.split(r"\s+", line)
                if len(parts) >= 5:
                    local_addr = parts[1]
                    state = parts[3]
                    pid_str = parts[4]
                    if state == "LISTENING":
                        port_match = re.search(r":(\d+)$", local_addr)
                        if port_match and int(port_match.group(1)) == port:
                            try:
                                pid = int(pid_str)
                                proc_name = get_process_name_by_pid(pid)
                                return PortListenerInfo(port=port, pid=pid, process_name=proc_name)
                            except ValueError:
                                pass
        except Exception:
            pass

    else:
        # macOS / Linux: use lsof or ss
        try:
            out = subprocess.check_output(["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-Fp,c"], text=True, stderr=subprocess.DEVNULL)
            pid = 0
            proc_name = "unknown"
            for line in out.splitlines():
                if line.startswith("p"):
                    pid = int(line[1:])
                elif line.startswith("c"):
                    proc_name = line[1:]
            if pid > 0:
                return PortListenerInfo(port=port, pid=pid, process_name=proc_name)
        except Exception:
            pass

        try:
            # Fallback to ss on Linux
            out = subprocess.check_output(["ss", "-lptn", f"sport = :{port}"], text=True, stderr=subprocess.DEVNULL)
            pid_match = re.search(r'pid=(\d+)', out)
            proc_match = re.search(r'"([^"]+)"', out)
            if pid_match:
                pid = int(pid_match.group(1))
                proc_name = proc_match.group(1) if proc_match else get_process_name_by_pid(pid)
                return PortListenerInfo(port=port, pid=pid, process_name=proc_name)
        except Exception:
            pass

    return PortListenerInfo(port=port, pid=0, process_name="unknown")


def kill_process_by_pid(pid: int, force: bool = True) -> bool:
    """Terminate a process by its PID."""
    if pid <= 0:
        return False

    if is_windows():
        try:
            flag = "/F" if force else ""
            cmd = f"taskkill /PID {pid} {flag} /T"
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    # Unix
    try:
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
        return True
    except Exception:
        return False


def free_port(port: int) -> bool:
    """Find the process listening on port and terminate it."""
    info = get_port_listener_info(port)
    if not info or info.pid <= 0:
        return False
    return kill_process_by_pid(info.pid, force=True)

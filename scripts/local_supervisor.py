import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(r"C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team")
PYTHON_EXE = Path(r"C:\Users\Playdata\miniconda3\envs\hpm_test_1\python.exe")
LOG_DIR = ROOT / ".runtime_logs"
PYDEPS = ROOT / ".runtime_pydeps" / "hpm_test_1"

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


SERVICES = {
    "test-flow": {
        "port": 8500,
        "cwd": ROOT / "test_flow",
        "cmd": [str(PYTHON_EXE), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8500"],
        "log": LOG_DIR / "test-flow.log",
    },
    "backend": {
        "port": 8000,
        "cwd": ROOT / "backend" / "hpm",
        "cmd": [str(PYTHON_EXE), "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        "log": LOG_DIR / "backend.log",
    },
}


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def make_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PYDEPS};{env.get('PYTHONPATH', '')}"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def append_supervisor_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "supervisor.log").open("a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def start_service(name: str, spec: dict) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with spec["log"].open("a", encoding="utf-8") as log:
        log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] supervisor starting {name} on {spec['port']}\n")
        log.flush()
        return subprocess.Popen(
            spec["cmd"],
            cwd=str(spec["cwd"]),
            env=make_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )


def main() -> int:
    append_supervisor_log("started")
    processes: dict[str, subprocess.Popen] = {}

    while True:
        for name, spec in SERVICES.items():
            proc = processes.get(name)
            if is_port_open(spec["port"]):
                continue
            if proc is not None and proc.poll() is None:
                continue
            processes[name] = start_service(name, spec)
            append_supervisor_log(f"started {name} pid={processes[name].pid}")
        time.sleep(5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        append_supervisor_log(f"fatal: {type(exc).__name__}: {exc}")
        raise


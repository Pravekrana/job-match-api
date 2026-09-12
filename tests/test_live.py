"""Exercise the shipped demo over real HTTP against a Uvicorn subprocess."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def test_live_demo(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'live.db'}"}
    with (tmp_path / "server.log").open("w+") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
            cwd=root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    log.seek(0)
                    raise AssertionError(f"Uvicorn exited early: {log.read()}")
                try:
                    with urlopen(base_url + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise AssertionError("Uvicorn did not become healthy within 20 seconds")
            demo = subprocess.run(
                [sys.executable, "demo.py", "--base-url", base_url],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=20,
            )
            assert demo.returncode == 0, demo.stderr
            assert '"overallScore": 95.5' in demo.stdout
            assert '"overallScore": 90.0' in demo.stdout
            assert '"overallScore": 100.0' in demo.stdout
            assert '"title": "Rust Engineer (excluded)"' not in demo.stdout
            assert "Reverse recommendations:" in demo.stdout
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

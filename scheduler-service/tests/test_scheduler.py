import shutil
import subprocess
from pathlib import Path
import pytest
from app.worker import run_task


def test_tasks():
    assert run_task("sum", {"numbers": [2, 3, 5]}) == 10
    assert run_task("uppercase", {"text": "hello"}) == "HELLO"
    with pytest.raises(ValueError):
        run_task("sum", {"numbers": "invalid"})


def test_cpp_backoff(tmp_path):
    if not shutil.which("g++"):
        return
    source = Path(__file__).resolve().parents[1] / "cpp/backoff.cpp"
    exe = tmp_path / "backoff"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
    for attempt, expected in [(1, 1), (2, 2), (3, 4), (20, 300)]:
        result = subprocess.run([str(exe), str(attempt)], capture_output=True, text=True, check=True)
        assert int(result.stdout.strip()) == expected

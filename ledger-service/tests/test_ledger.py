import shutil
import subprocess
from pathlib import Path

from app.main import AccountIn, TransferIn


def test_validation_models():
    assert AccountIn(owner="A", opening_balance=100).opening_balance == 100
    assert TransferIn(from_id=1, to_id=2, amount=1, idempotency_key="abcdefgh").amount == 1


def test_cpp_journal(tmp_path):
    if not shutil.which("g++"):
        return
    source = Path(__file__).resolve().parents[1] / "cpp/journal.cpp"
    exe = tmp_path / "journal"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
    assert subprocess.run([str(exe)], input="2\n-25\n25\n", text=True).returncode == 0
    assert subprocess.run([str(exe)], input="2\n-25\n24\n", text=True).returncode == 1

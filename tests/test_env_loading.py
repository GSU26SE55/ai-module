"""Nạp .env ở CẢ HAI entrypoint — REST và gRPC.

Trước đây không chỗ nào gọi `load_dotenv()` và không lệnh chạy nào truyền
`--env-file`, nên `DEEPSEEK_API_KEY` trong .env chưa bao giờ tới được process:
`chain.is_available()` luôn False → mọi request `enrich=true` âm thầm rơi về
rule-based, và cả tầng RAG/SOP (13 file knowledge, 64 chunk) chưa từng chạy.
Không lỗi nào được raise — response vẫn 200, chỉ khác `llm_provider: "none"`.

⚠️ File này CỐ Ý không `import main`. Import nó sẽ chạy `load_dotenv()` và bơm
key thật vào `os.environ` của cả process pytest — đã đo: làm đỏ 2 test khác
trong `test_grpc_server.py` khi chạy full suite (chúng xanh khi chạy riêng).
Kiểm bằng đọc source + subprocess riêng để không rò trạng thái sang test khác.
"""

import pathlib
import subprocess
import sys

MAIN = pathlib.Path("main.py").read_text(encoding="utf-8")
GRPC = pathlib.Path("src/grpc_server.py").read_text(encoding="utf-8")


def test_rest_entrypoint_loads_dotenv():
    assert "load_dotenv(" in MAIN


def test_grpc_entrypoint_loads_dotenv():
    """gRPC chạy bằng `python -m src.grpc_server`, KHÔNG qua uvicorn nên không có
    cờ `--env-file`. Sửa mỗi main.py thì REST có key còn gRPC — đường BE dùng
    thật — vẫn không."""
    i = GRPC.index("def serve()")
    assert "load_dotenv(" in GRPC[i : i + 800]


def test_both_entrypoints_do_not_override_real_env():
    """override=False là CỐ Ý: biến môi trường thật (docker `env_file`, secrets của
    orchestrator) phải thắng file .env nằm trên đĩa. Đảo lại thì deploy production
    có thể bị .env lập trình viên bỏ quên trong image ghi đè."""
    for src in (MAIN, GRPC):
        i = src.index("load_dotenv(")
        assert "override=False" in src[i : i + 40]


def test_dotenv_is_pinned_not_a_transitive_dependency():
    """Trước đây gói này chỉ có mặt gián tiếp qua uvicorn[standard] — container
    không chắc có, mà thiếu nó thì import entrypoint sẽ vỡ ngay."""
    req = pathlib.Path("requirements.txt").read_text(encoding="utf-8")
    assert "python-dotenv==" in req


def test_importing_main_actually_populates_os_environ():
    """Kiểm CHỨC NĂNG chứ không chỉ text — chạy trong subprocess riêng để key thật
    không rò sang các test khác."""
    code = (
        "import os,sys; sys.path.insert(0,'.');"
        "before = os.getenv('DEEPSEEK_API_KEY') is not None;"
        "import main;"
        "after = os.getenv('DEEPSEEK_API_KEY') is not None;"
        "print(f'{before}|{after}')"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=180
    ).stdout.strip().splitlines()[-1]
    before, after = out.split("|")
    if not pathlib.Path(".env").exists():
        import pytest

        pytest.skip("máy này không có .env")
    assert before == "False", "biến đã có sẵn — phép đo không nói lên điều gì"
    assert after == "True", "import main không nạp được .env"

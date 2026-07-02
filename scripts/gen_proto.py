"""
Generate Python gRPC stubs from protos/ai_service.proto into src/grpc_gen/.

Cross-platform (Windows dev machine + Kaggle/Linux) — uses the bundled
grpc_tools.protoc module, no system protoc install needed.

Usage:
    python scripts/gen_proto.py

Generated files (committed to Git so CI/teammates don't need to regenerate):
    src/grpc_gen/ai_service_pb2.py
    src/grpc_gen/ai_service_pb2_grpc.py
    src/grpc_gen/ai_service_pb2.pyi
"""

import re
import sys
from pathlib import Path

from grpc_tools import protoc

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "protos"
OUT_DIR = ROOT / "src" / "grpc_gen"
PROTO_FILE = PROTO_DIR / "ai_service.proto"


def generate() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    init_py = OUT_DIR / "__init__.py"
    if not init_py.exists():
        init_py.write_text(
            '"""Generated gRPC stubs — do not edit. Regenerate: python scripts/gen_proto.py"""\n',
            encoding="utf-8",
        )

    args = [
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        f"--pyi_out={OUT_DIR}",
        str(PROTO_FILE),
    ]
    exit_code = protoc.main(args)
    if exit_code != 0:
        sys.exit(f"protoc failed with exit code {exit_code}")

    fix_grpc_imports(OUT_DIR / "ai_service_pb2_grpc.py")
    print(f"Generated stubs in {OUT_DIR.relative_to(ROOT)}/")


def fix_grpc_imports(grpc_stub: Path) -> None:
    """protoc emits `import ai_service_pb2 ...` (top-level absolute import),
    which breaks when the stub lives in the src.grpc_gen package. Rewrite it
    to an absolute import from the package."""
    content = grpc_stub.read_text(encoding="utf-8")
    fixed = re.sub(
        r"^import ai_service_pb2 as",
        "from src.grpc_gen import ai_service_pb2 as",
        content,
        flags=re.MULTILINE,
    )
    grpc_stub.write_text(fixed, encoding="utf-8")


if __name__ == "__main__":
    generate()

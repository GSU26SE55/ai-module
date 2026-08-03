"""End-to-end full-case suite: hành vi + tốc độ, qua gRPC wire thật.

Khác với 2 script đã có:
  - scripts/benchmark_grpc.py  — chỉ đo tốc độ, payload 4 cột ngẫu nhiên, KHÔNG có
    pack_config nên chưa bao giờ chạm đường chemistry/LFP.
  - scripts/grpc_client_demo.py — demo 4 RPC, không assert gì.

Script này chạy một ma trận kịch bản THẬT (single-cell NMC / pack LFP, khoẻ / suy
giảm), kiểm tra kết quả có đúng như mong đợi không, chạy cả các ca lỗi, rồi đo độ
trễ tách riêng cho từng bộ artifact.

Server dựng IN-PROCESS trên port ngẫu nhiên (giống benchmark_grpc.py) nên không đụng
port 50051 đang chạy và không để sót tiến trình.

Dùng:
    python scripts/e2e_full_test.py                 # đầy đủ
    python scripts/e2e_full_test.py --skip-latency  # chỉ kiểm hành vi (nhanh)
    python scripts/e2e_full_test.py -n 100          # nhiều vòng đo hơn
    python scripts/e2e_full_test.py --sla 100       # ngưỡng p95 (ms)

Exit code 0 = tất cả pass. Khác 0 = có mục FAIL (dùng được trong CI).
"""

import argparse
import os
import statistics
import sys
import time
from concurrent import futures

import grpc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import model_loader
from src.core.config import WINDOW_SIZE
from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc
from src.grpc_server import AiServiceServicer

NOMINAL_AH = 2.0  # dung lượng cell NASA — mốc quy đổi C-rate


# ---------------------------------------------------------------------------
# Sinh payload NHẤT QUÁN VẬT LÝ
# ---------------------------------------------------------------------------
def window(
    v_start: float,
    v_end: float,
    current: float,
    temp: float = 30.0,
    dt: float = 3.0,
    cycle: int = 100,
    soc_start: float = 85.0,
    capacity_ah: float = NOMINAL_AH,
    n_cols: int = 6,
) -> list[list[float]]:
    """Một window 30 bước, SOC tự suy ra từ dòng × thời gian nên không mâu thuẫn.

    Payload mâu thuẫn (vd SOC tụt 60 điểm trong 87 giây) là dữ liệu model chưa bao
    giờ thấy — kết quả sẽ vô nghĩa và ta lại tưởng model sai.
    """
    n = WINDOW_SIZE
    t = np.arange(n) * dt
    # C-rate quy đổi giống hệt inference: current × 2.0 / capacity_ah
    i_equiv = current * NOMINAL_AH / capacity_ah
    ah_drawn = abs(i_equiv) * (t / 3600.0)
    soc = soc_start - ah_drawn / NOMINAL_AH * 100.0
    volts = np.linspace(v_start, v_end, n)
    rows = []
    for k in range(n):
        row = [float(volts[k]), float(current), float(temp), float(t[k])]
        if n_cols >= 6:
            row += [float(cycle), float(max(0.0, soc[k]))]
        rows.append(row[:n_cols])
    return rows


def to_proto(rows) -> list:
    return [pb.Reading(values=r) for r in rows]


LFP_PACK = pb.PackConfig(n_series=4, chemistry="LFP", capacity_ah=2.5)
NMC_PACK = pb.PackConfig(n_series=4, chemistry="NMC", capacity_ah=2.5)

# ---------------------------------------------------------------------------
# Ma trận kịch bản hành vi
#   (ten, rows, pack_config, kiem_tra(response) -> str|None  [None = pass])
# ---------------------------------------------------------------------------


def _expect(cond, msg):
    return None if cond else msg


def behaviour_cases():
    # --- single-cell NMC (không pack_config) ---
    cell_healthy = window(4.05, 3.85, -2.0, cycle=20, soc_start=95.0)
    cell_eol = window(3.30, 2.85, -2.0, cycle=190, soc_start=40.0)

    # --- pack LFP 4S: điện áp PACK (~4× per-cell), dòng pack, capacity thật ---
    # 3.30 V/cell nam trong vung model bao hoa o 100% (raw ~102, bi clip). Chon
    # 3.20 va 3.05 V/cell de hai kich ban tach nhau that su — neu khong, test
    # "khoe" vs "mon" deu ra 100.00% va khong kiem duoc gi.
    lfp_healthy = window(12.80, 12.68, -5.0, cycle=300, soc_start=90.0, capacity_ah=2.5)
    lfp_worn = window(12.20, 12.08, -5.0, cycle=900, soc_start=80.0, capacity_ah=2.5)

    return [
        (
            "cell NMC khoe (khong pack_config)",
            cell_healthy, None,
            lambda r: _expect(r.metadata.model_version == "1.6",
                              f"phai dung model NASA, nhan {r.metadata.model_version}")
            or _expect(r.metadata.n_series == 1, "n_series phai = 1"),
        ),
        (
            "cell NMC suy giam",
            cell_eol, None,
            lambda r: _expect(r.prediction.soh_percent < 95.0,
                              f"SOH phai thap hon ca khoe, nhan {r.prediction.soh_percent:.2f}"),
        ),
        (
            "pack LFP 4S khoe",
            lfp_healthy, LFP_PACK,
            lambda r: _expect(r.metadata.model_version == "2.0-lfp",
                              f"phai dung model LFP, nhan {r.metadata.model_version}")
            or _expect(r.metadata.chemistry == "LFP", "metadata.chemistry phai la LFP")
            or _expect(r.metadata.n_series == 4, "n_series phai = 4")
            # feature_summary la gia tri PER-CELL sau khi chia n_series
            or _expect(2.0 <= r.evidence.feature_summary["voltage"].mean <= 4.5,
                       "feature_summary.voltage phai la per-cell trong [2.0, 4.5]"),
        ),
        (
            "pack LFP 4S da dung nhieu",
            lfp_worn, LFP_PACK,
            lambda r: _expect(r.metadata.model_version == "2.0-lfp", "phai dung model LFP")
            or _expect(r.prediction.soh_percent < 99.0,
                       f"pack mon phai duoi 99%, nhan {r.prediction.soh_percent:.2f} "
                       "(dau hieu model bao hoa hoac input ngoai phan bo)"),
        ),
        (
            "pack 4S NHUNG khai NMC -> dung artifact NASA",
            lfp_healthy, NMC_PACK,
            lambda r: _expect(r.metadata.model_version == "1.6",
                              f"chemistry=NMC phai dung NASA, nhan {r.metadata.model_version}"),
        ),
    ]


def error_cases():
    good = window(13.30, 13.16, -5.0, capacity_ah=2.5)
    short = good[:20]
    nan_rows = [r[:] for r in good]
    nan_rows[3][0] = float("nan")
    return [
        ("window != 30 buoc", short, LFP_PACK, grpc.StatusCode.INVALID_ARGUMENT),
        ("dien ap pack nhung THIEU pack_config", good, None, grpc.StatusCode.INVALID_ARGUMENT),
        ("gia tri NaN", nan_rows, LFP_PACK, grpc.StatusCode.INVALID_ARGUMENT),
        # LFP + payload 4 cot: guard soc_mode. Hien tai map thanh INTERNAL —
        # xem docs/be-huong-dan-tich-hop.md muc 7c (lech contract da biet).
        ("LFP + payload 4 cot (thieu soc that)",
         window(13.30, 13.16, -5.0, capacity_ah=2.5, n_cols=4), LFP_PACK, None),
    ]


# ---------------------------------------------------------------------------
def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p / 100))]


def measure(fn, n, warmup=10):
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(n):
        s = time.perf_counter()
        fn()
        out.append((time.perf_counter() - s) * 1000)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=30, help="so vong do latency (mac dinh 30)")
    ap.add_argument("--sla", type=float, default=100.0, help="nguong p95 ms (mac dinh 100)")
    ap.add_argument("--skip-latency", action="store_true")
    args = ap.parse_args()

    print("Nap artifact...")
    model_loader.load_models()
    lfp_ok = model_loader.lfp_soh_model is not None
    print(f"  NASA: OK | LFP: {'OK' if lfp_ok else 'KHONG CO'}\n")

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_AiServiceServicer_to_server(AiServiceServicer(), server)
    port = server.add_insecure_port("localhost:0")
    server.start()
    stub = pb_grpc.AiServiceStub(grpc.insecure_channel(f"localhost:{port}"))

    failures = []

    # ---- 0. Health -------------------------------------------------------
    print("=" * 78)
    print("0. HEALTH")
    print("=" * 78)
    h = stub.Health(pb.HealthRequest())
    print(f"  status={h.status} model={h.model_version} "
          f"lfp_loaded={h.lfp_loaded} lfp_version={h.lfp_model_version}")
    if h.status != "ok":
        failures.append("Health khong tra status=ok")
    if lfp_ok and not h.lfp_loaded:
        failures.append("Health.lfp_loaded=false trong khi artifact LFP da nap")

    # ---- 1. Hành vi ------------------------------------------------------
    print()
    print("=" * 78)
    print("1. HANH VI — Predict")
    print("=" * 78)
    for name, rows, pack, check in behaviour_cases():
        req = pb.PredictRequest(battery_id="T", readings=to_proto(rows))
        if pack:
            req.pack_config.CopyFrom(pack)
        try:
            r = stub.Predict(req)
        except grpc.RpcError as e:
            failures.append(f"{name}: RPC loi {e.code().name} — {e.details()[:70]}")
            print(f"  [FAIL] {name:<42} RPC loi {e.code().name}")
            continue
        err = check(r)
        tag = "OK  " if err is None else "FAIL"
        if err:
            failures.append(f"{name}: {err}")
        print(f"  [{tag}] {name:<42} SOH={r.prediction.soh_percent:6.2f}% "
              f"{r.prediction.health_stage:<20} model={r.metadata.model_version}")
        if err:
            print(f"         -> {err}")

    # ---- 1b. Khao sat do nhay (BAO CAO, khong hard-fail) ------------------
    # Day la tinh chat cua MODEL, khong phai loi phuc vu. Hard-fail o day se lam
    # suite do khi model duoc retrain, trong khi viec cua suite la bat loi SERVING.
    print()
    print("=" * 78)
    print("1b. KHAO SAT DO NHAY (bao cao — khong tinh FAIL)")
    print("=" * 78)
    print("  Quet dien ap, SOC di kem NHAT QUAN (xa sau -> ap thap + SOC thap):")
    for label, pack in (("LFP ", LFP_PACK),
                        ("NASA", pb.PackConfig(n_series=4, capacity_ah=2.5))):
        sohs = []
        # Quet RONG hon: model LFP bao hoa o 100% khi V/cell >= 3.25 (13.0 V pack),
        # nen dai hep chi nam trong vung do se cho spread ~0 va bao FAIL gia.
        for vp, soc in ((13.4, 95.0), (12.8, 75.0), (12.4, 55.0), (11.8, 35.0), (11.2, 15.0)):
            rows = window(vp, vp - 0.12, -5.0, cycle=800, soc_start=soc, capacity_ah=2.5)
            req = pb.PredictRequest(battery_id="S", readings=to_proto(rows))
            req.pack_config.CopyFrom(pack)
            sohs.append(stub.Predict(req).prediction.soh_percent)
        spread = max(sohs) - min(sohs)
        print(f"    {label} " + " -> ".join(f"{v:5.1f}%" for v in sohs)
              + f"   (spread {spread:.1f} diem)")
        if spread < 1.0:
            failures.append(f"do nhay {label.strip()}: spread {spread:.2f} diem "
                            "— model gan nhu tra hang so, kiem tra artifact")

    print("\n  Giu nguyen dien ap+SOC, chi doi cycle_count (LFP):")
    row = []
    for cyc in (50, 500, 1400, 2200):
        rows = window(12.2, 12.08, -5.0, cycle=cyc, soc_start=80.0, capacity_ah=2.5)
        req = pb.PredictRequest(battery_id="S", readings=to_proto(rows))
        req.pack_config.CopyFrom(LFP_PACK)
        row.append((cyc, stub.Predict(req).prediction.soh_percent))
    print("    " + "  ".join(f"cycle {c}={v:.1f}%" for c, v in row))
    if row[-1][1] > row[len(row) // 2][1] + 1.0:
        print("    LUU Y: SOH TANG lai o cycle rat cao — trong Severson, cell con song o")
        print("           cycle 2000+ la cell BEN, nen model hoc duoc tuong quan gia")
        print("           'cycle cao => cell tot'. Khong phai loi serving, nhung nen biet.")

    # ---- 2. Prescribe dùng cùng artifact ---------------------------------
    print()
    print("=" * 78)
    print("2. HANH VI — Prescribe (duong BE nen dung)")
    print("=" * 78)
    lfp_rows = window(13.30, 13.16, -5.0, cycle=300, soc_start=90.0, capacity_ah=2.5)
    p_lfp = pb.PrescribeRequest(battery_id="T", readings=to_proto(lfp_rows), enrich=False)
    p_lfp.pack_config.CopyFrom(LFP_PACK)
    p_nasa = pb.PrescribeRequest(battery_id="T2", readings=to_proto(lfp_rows), enrich=False)
    p_nasa.pack_config.CopyFrom(pb.PackConfig(n_series=4))  # khong khai chemistry

    r_lfp, r_nasa = stub.Prescribe(p_lfp), stub.Prescribe(p_nasa)
    print(f"  chemistry=LFP    SOH={r_lfp.prediction.soh_percent:6.2f}%  "
          f"action={r_lfp.action_code:<22} steps={len(r_lfp.action_steps)}")
    print(f"  khong chemistry  SOH={r_nasa.prediction.soh_percent:6.2f}%  "
          f"action={r_nasa.action_code:<22} steps={len(r_nasa.action_steps)}")
    diff = abs(r_lfp.prediction.soh_percent - r_nasa.prediction.soh_percent)
    if diff < 1e-6:
        failures.append("Prescribe: chemistry khong tao khac biet -> pack_config bi drop")
        print("  [FAIL] hai ket qua giong het -> pack_config KHONG toi run_inference")
    else:
        print(f"  [OK  ] lech {diff:.2f} diem -> pack_config DA toi run_inference")
    if not r_lfp.action_code:
        failures.append("Prescribe: action_code rong")
    if r_lfp.blocked:
        failures.append("Prescribe enrich=false khong duoc blocked")

    # ---- 3. Ca lỗi -------------------------------------------------------
    print()
    print("=" * 78)
    print("3. CA LOI — phai bi tu choi")
    print("=" * 78)
    for name, rows, pack, want in error_cases():
        req = pb.PredictRequest(battery_id="T", readings=to_proto(rows))
        if pack:
            req.pack_config.CopyFrom(pack)
        try:
            stub.Predict(req)
            failures.append(f"{name}: KHONG bi tu choi")
            print(f"  [FAIL] {name:<42} khong bi tu choi")
        except grpc.RpcError as e:
            ok = want is None or e.code() == want
            if not ok:
                failures.append(f"{name}: mong {want.name}, nhan {e.code().name}")
            print(f"  [{'OK  ' if ok else 'FAIL'}] {name:<42} {e.code().name}")

    # ---- 4. Tốc độ -------------------------------------------------------
    if not args.skip_latency:
        print()
        print("=" * 78)
        print(f"4. TOC DO — n={args.n}/muc, nguong p95 < {args.sla:.0f}ms")
        print("=" * 78)
        cell = window(4.05, 3.85, -2.0, cycle=20, soc_start=95.0)
        nasa_pred = pb.PredictRequest(battery_id="T", readings=to_proto(cell))
        lfp_pred = pb.PredictRequest(battery_id="T", readings=to_proto(lfp_rows))
        lfp_pred.pack_config.CopyFrom(LFP_PACK)

        # Prescribe co cache idempotency (GH-84): dung lai y het request se tra
        # cache trong ~0.6ms va con so do VO NGHIA. Doi battery_id moi lan de do
        # duong tinh that.
        counter = {"n": 0}

        def fresh_prescribe(base):
            def _go():
                counter["n"] += 1
                req = pb.PrescribeRequest()
                req.CopyFrom(base)
                req.battery_id = f"BENCH-{counter['n']}"
                return stub.Prescribe(req)
            return _go

        # Baseline goi HAM TRUC TIEP — tach phan model ra khoi phan transport.
        # Do duoc: pipeline p95 ~25-33ms, nhung qua gRPC in-process p95 vot len
        # ~70-176ms. Chenh lech do la tang phuc vu, KHONG phai model.
        from src.services.inference import run_inference as _direct
        cell_rows = window(4.05, 3.85, -2.0, cycle=20, soc_start=95.0)
        lfp_rows_d = window(12.80, 12.68, -5.0, cycle=300, soc_start=90.0, capacity_ah=2.5)

        jobs = [
            ("direct    NASA", lambda: _direct(cell_rows)),
            ("direct    LFP ", lambda: _direct(lfp_rows_d, n_series=4,
                                               chemistry="LFP", capacity_ah=2.5)),
            ("Predict   NASA", lambda: stub.Predict(nasa_pred)),
            ("Predict   LFP ", lambda: stub.Predict(lfp_pred)),
            ("Prescribe NASA", fresh_prescribe(p_nasa)),
            ("Prescribe LFP ", fresh_prescribe(p_lfp)),
        ]
        print("  'direct' = goi ham truc tiep (chi model). Con lai = qua gRPC in-process,")
        print("  co canh tranh GIL giua client va server trong CUNG tien trinh nen doi")
        print("  thuc te tren may deploy (2 tien trinh rieng) se KHAC — xem ghi chu cuoi.")
        print()
        print(f"  {'muc':<16}{'avg':>9}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}   SLA")
        print("  " + "-" * 72)
        for label, fn in jobs:
            xs = measure(fn, args.n)
            p95 = pct(xs, 95)
            ok = p95 < args.sla
            # 'direct' chi la baseline tham chieu — khong tinh FAIL vi no khong phai
            # con so ma BE thuc su gap.
            if not ok and not label.startswith("direct"):
                failures.append(f"latency {label.strip()}: p95={p95:.1f}ms >= {args.sla:.0f}ms")
            print(f"  {label:<16}{statistics.mean(xs):8.1f}ms{pct(xs,50):8.1f}ms"
                  f"{p95:8.1f}ms{pct(xs,99):8.1f}ms{max(xs):8.1f}ms   "
                  f"{'PASS' if ok else 'FAIL'}")

        # Cache: gọi lại y hệt phải nhanh hơn hẳn
        print()
        print("  LUU Y ve con so gRPC: server chay IN-PROCESS cung client nen 2 ben")
        print("  tranh GIL — day la gioi han cua cach do nay (benchmark_grpc.py cung vay).")
        print("  Truoc khi ket luan vuot SLA, do lai voi server chay TIEN TRINH RIENG:")
        print("     python -m src.grpc_server            # terminal 1")
        print("     python scripts/benchmark_grpc.py --real-weights   # terminal 2")

        again = stub.Prescribe(p_lfp)
        print(f"\n  Prescribe goi lai y het -> cached={again.cached} "
              f"({'dung' if again.cached else 'KHONG cache — kiem tra TTL'})")

    server.stop(0)

    print()
    print("=" * 78)
    if failures:
        print(f"KET QUA: {len(failures)} MUC FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("KET QUA: TAT CA PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

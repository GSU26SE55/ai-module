"""Generate 6-column IoT-simulator scenario data covering the full BE decision matrix.

Produces one CONTINUOUS multi-window CSV stream per scenario (voltage, current,
temperature, time, cycle_count, soc_percent — pack-level values, LFP 8S/24V/30Ah,
matches the project's real battery spec) under demo/iot_simulator/. Each stream is
STREAM_LEN rows (dozens of context windows long), deliberately far longer than the
30-row window the model consumes, because a real BE assembling windows from a live
stream will not necessarily cut at the same offset every time (sliding window, not
necessarily aligned to row 0). To make sure the labeled outcome in manifest.json
holds regardless of exactly where BE cuts, EVERY possible 30-row slice is pulled
from EACH stream and run through the real inference pipeline
(src.services.inference.run_inference); manifest.json records the full spread, not
just one lucky slice.

This does NOT protect a slice that straddles two DIFFERENT scenario files (mixing
two unrelated batteries mid-window is not physically consistent data regardless of
how long the streams are) — keep each scenario under its own battery_id and don't
concatenate two scenario streams as if they were one battery's history.

Sampling rate
-------------
SAMPLE_DT = 10 s is forced by physics, not preference. A pack discharging at the
solar baseline load runs out of charge long before 1000 rows at a coarser rate:

    dt=30 s, 1000 rows -> 8.3 h -> SOC 85% -> -54%   (impossible)
    dt=10 s, 1200 rows -> 3.3 h -> SOC 85% ->  29%   (stays on the LFP plateau)

10 s also happens to be the rate the real Sandia archive logs its reference
cycles at, so the window duration the model sees here matches its training data.

Usage:
    python -X utf8 scripts/gen_iot_scenarios.py                 # all scenarios
    python -X utf8 scripts/gen_iot_scenarios.py --only 6,7      # regenerate a subset
    python -X utf8 scripts/gen_iot_scenarios.py --offset-stride 10   # quick pass
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import model_loader
from src.core.config import WINDOW_SIZE
from src.schemas.predict import PackConfig, PredictRequest
from src.services.inference import run_inference

OUT_DIR = os.path.join("demo", "iot_simulator")
COLUMNS = ["voltage", "current", "temperature", "time", "cycle_count", "soc_percent"]

N_SERIES = 8          # pack thật của dự án: LFP 8S/24V
CAPACITY_AH = 30.0
CHEMISTRY = "LFP"
STREAM_LEN = 1200     # 40x WINDOW_SIZE — 1171 diem cat window khac nhau moi scenario
# Chu ky lay mau. Rang buoc kep:
#   (a) scaler LFP fit `time` tren [0, 1453.9] s va BE rebase time ve 0 dau moi
#       window (docs/grpc-integration-be.md §4.1) => WINDOW_SIZE × dt <= 1454 s
#       => dt <= ~48 s.
#   (b) stream 1200 dong phai giu SOC tren vung plateau (>20%) — xem docstring.
# 10 s thoa ca hai, va trung tan so log chu ky RPT cua bo Sandia.
SAMPLE_DT = 10.0
# Dong xa solar thuc te tren pack 30 Ah. -5 A = 0.17C, giu SOC trong plateau suot
# 3.3 gio stream.
SOLAR_CURRENT = -5.0
# Dien tro trong quy doi ve 1 cell cua pack 30 Ah (cell lon hon cell 1.1 Ah nhieu
# nen R nho hon han). Chi dung cho kich ban tai xung — o -5 A sut ap chi 0.08 V/pack
# nen khong lam lech cac kich ban con lai.
R_INT_CELL = 0.002


def lfp_cell_voltage(soc_pct, plateau):
    """Dien ap 1 cell LFP theo SOC — plateau RAT PHANG roi sup nhanh duoi 20% SOC.

    Dung dac tinh that cua LiFePO4 thay vi ramp tuyen tinh: ramp tuyen tinh tao ra
    do doc gia trong moi window, va khi lap lai de keo dai stream thi sinh diem noi
    (dien ap nhay nguoc len = pin tu sac) — window cat qua do la du lieu vo nghia.
    Duong plateau lien tuc khong co diem noi nen MOI window 30-dong deu hop le.

    `plateau` = muc dien ap dinh cua cell; tut xuong khi pin chai."""
    if soc_pct > 20.0:
        return plateau - (100.0 - soc_pct) * 0.0015
    return (plateau - 0.12) - (20.0 - soc_pct) * 0.045


def _as_series(value, n):
    """Cho phep moi tham so la hang so HOAC mang doc theo thoi gian.

    Kich ban thuc te ngoai troi khong co nhiet do hay dong tai hang so — do la ly
    do 5 kich ban dau tien (deu hang so) khong dai dien cho du lieu that."""
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return np.full(n, float(arr))
    if len(arr) != n:
        raise ValueError(f"series dai {len(arr)}, can {n}")
    return arr


def physics_stream(plateau_cell, current, temp, cycle, soc_start, n=STREAM_LEN,
                   dt=SAMPLE_DT, r_int=0.0):
    """Stream xa LFP lien tuc, dai n dong — dien ap suy ra tu SOC theo duong LFP that.

    SOC giam theo Coulomb counting (tich phan dong tuc thoi, nen dong bien thien
    van dung), dien ap bam theo SOC nen toan bo stream nhat quan vat ly va KHONG
    co diem noi — cat window o bat ky dau cung hop le.

    `current`/`temp` nhan hang so hoac mang dai n.
    `r_int` > 0 them sut ap I·R (chi can cho kich ban tai xung)."""
    t = np.arange(n) * dt
    cur = _as_series(current, n)
    tem = _as_series(temp, n)
    # Coulomb counting tren dong TUC THOI, khong dung |I| trung binh
    ah_drawn = np.cumsum(np.abs(cur) * dt / 3600.0)
    soc = np.maximum(0.0, soc_start - ah_drawn / CAPACITY_AH * 100.0)

    rows = []
    for k in range(n):
        v_cell = lfp_cell_voltage(float(soc[k]), plateau_cell) - abs(cur[k]) * r_int
        rows.append([
            round(v_cell * N_SERIES, 4),
            round(float(cur[k]), 4),
            round(float(tem[k]), 4),
            round(float(t[k]), 4),
            float(cycle),
            round(float(soc[k]), 4),
        ])
    return rows


def spiky_stream(plateau_cell, current_base, temp_base, cycle, soc_start, every, v_amp,
                 i_amp, t_amp, n=STREAM_LEN, dt=SAMPLE_DT):
    """Stream sensor bat thuong — nen la duong xa LFP binh thuong, CONG them song
    vuong xen ke (loose connector / sensor glitch). Day la dang du lieu
    IsolationForest duoc train de bat (hinh dang bat thuong trong FFT/kurtosis), doc
    lap voi canh bao nguong BMS (rule-based).

    Bien do da do thuc nghiem: phai du lon de dat anomaly_status="Warning" nhung du
    NHO de khong keo SOH qua nguong 80% — bien do lon (v_amp>=1.5) lam SOH dao dong
    xuong ~65% va lat nhan sang End Of Life o mot so diem cat, tuc la kich ban
    "pin khoe nhung cam bien loi" bi bien thanh "pin hong"."""
    base = physics_stream(plateau_cell, current_base, temp_base, cycle, soc_start, n, dt)
    rows = []
    for k, r in enumerate(base):
        sign = 1 if (k // every) % 2 == 0 else -1
        spike = 1.0 if k % every == 0 else 0.0
        rows.append([
            round(r[0] + sign * v_amp * spike, 4),
            round(r[1] + sign * i_amp * spike, 4),
            round(r[2] + sign * t_amp * spike, 4),
            r[3], r[4], r[5],
        ])
    return rows


def ramp(a, b, n=STREAM_LEN):
    """Doan tuyen tinh a -> b, dung cho nhiet do trong ngay hoac nhiet tang dan."""
    return np.linspace(a, b, n)


def solar_day_temp(n=STREAM_LEN):
    """Nhiet do pack ngoai troi VN theo nua ngay: sang mat -> trua nong -> chieu diu.

    Nua chu ky sin bien do 22-44 °C. Day la ly do khong duoc coi nhiet do la hang so:
    mot stream duy nhat di xuyen qua CA vung trong cum train LAN vung ngoai cum."""
    return 22.0 + 22.0 * np.sin(np.linspace(0.0, np.pi, n))


def cloudy_load(base, n=STREAM_LEN, seed=7):
    """Dong tai bien thien do may che — nhieu buoc thang, khong phai nhieu trang.

    Tai solar that thay doi theo khoi (may troi qua) chu khong dao tung mau."""
    rng = np.random.default_rng(seed)
    blocks = max(1, n // 60)
    steps = rng.uniform(0.55, 1.35, size=blocks)
    return np.repeat(steps, int(np.ceil(n / blocks)))[:n] * base


def pulsed_load(base, peak, n=STREAM_LEN, period=120, width=6):
    """Tai nen + xung ngan (bom/inverter khoi dong). Dong dinh `peak` chi keo dai
    `width` mau moi `period` mau, nen SOC trung binh van giu duoc tren plateau —
    khong the giu -100 A lien tuc 1200 dong (SOC tut 1111%)."""
    cur = np.full(n, base, dtype=float)
    for start in range(0, n, period):
        cur[start:start + width] = peak
    return cur


def evaluate(rows, battery_id="IOT-SIM"):
    """Chay 1 window (30 dong) qua DUNG API boundary that.

    PHAI validate qua PredictRequest truoc khi goi run_inference: goi thang
    run_inference() bo qua tang Pydantic, nen se sinh ra ky vong cho nhung window
    ma API THAT tu choi (vd LFP > 3.8 V/cell -> INVALID_ARGUMENT). Bo data ma BE
    khong gui duoc thi vo dung."""
    # time phai rebase ve 0 dau moi window — quy uoc bat buoc, xem
    # docs/grpc-integration-be.md §4.1
    t0 = rows[0][3]
    rows = [[r[0], r[1], r[2], r[3] - t0, r[4], r[5]] for r in rows]
    PredictRequest(
        battery_id=battery_id,
        readings=rows,
        pack_config=PackConfig(
            n_series=N_SERIES, chemistry=CHEMISTRY, capacity_ah=CAPACITY_AH
        ),
    )
    return run_inference(
        rows,
        n_series=N_SERIES,
        chemistry=CHEMISTRY,
        capacity_ah=CAPACITY_AH,
        battery_id=battery_id,
    )


def evaluate_all_offsets(stream, name, stride=1):
    """Cat window 30-dong tai MOI vi tri co the trong stream (mo phong BE cat window
    o bat ky dau, khong chi row 0) roi chay qua inference — kiem tra output co ON
    DINH bat ke diem cat hay khong. Quet TOAN BO offset chu khong lay mau ngau
    nhien: ca sat nguong (vd EOL 80%) co the chi lat nhan o vai offset le loi, lay
    mau thua se bo sot dung nhung cho do.

    `stride` > 1 chi de chay nhanh luc phat trien; ban chinh thuc phai de stride=1,
    vi bo sot dung offset lat nhan la bo sot toan bo gia tri cua manifest."""
    max_start = len(stream) - WINDOW_SIZE
    results = []
    for off in range(0, max_start + 1, stride):
        window = stream[off: off + WINDOW_SIZE]
        # battery_id rieng per-offset de battery_history (causal_rate) khong ro ri
        # giua cac lan cat khac nhau cua cung 1 stream test
        r = evaluate(window, battery_id=f"{name}-off{off}")
        results.append({
            "offset": off,
            "soh_percent": r["prediction"]["soh_percent"],
            "health_stage": r["prediction"]["health_stage"],
            "anomaly_status": r["anomaly"]["anomaly_status"],
            "action_code": r["risk"]["action_code"],
            "priority": r["risk"]["priority"],
        })
    return results


def _label(r):
    return f"{r['health_stage']} | {r['action_code']} | {r['priority']}"


def _label_distribution(results):
    """Moi to hop nhan chiem bao nhieu offset — cho biet nhan nao la 'da so' va
    nhan nao chi xuat hien o vai diem cat le loi."""
    dist = {}
    for r in results:
        k = _label(r)
        d = dist.setdefault(k, {"n_offsets": 0, "soh_min": 100.0, "soh_max": 0.0})
        d["n_offsets"] += 1
        d["soh_min"] = min(d["soh_min"], r["soh_percent"])
        d["soh_max"] = max(d["soh_max"], r["soh_percent"])
    total = len(results)
    for d in dist.values():
        d["share"] = round(d["n_offsets"] / total, 4)
        d["soh_min"] = round(d["soh_min"], 2)
        d["soh_max"] = round(d["soh_max"], 2)
    return dict(sorted(dist.items(), key=lambda kv: -kv[1]["n_offsets"]))


def _label_transitions(results):
    """Cac diem cat ma nhan DOI so voi offset lien truoc.

    Day moi la thu BE can: neu nhan doi qua lai lien tuc thi mot lan doc don le vo
    nghia; neu chi doi 1-2 lan (vd nhiet vuot nguong giua stream) thi do la thay doi
    trang thai THAT chu khong phai nhieu."""
    out = []
    for prev, cur in zip(results, results[1:]):
        if _label(prev) != _label(cur):
            out.append({
                "at_offset": cur["offset"],
                "from": _label(prev),
                "to": _label(cur),
                "soh_before": prev["soh_percent"],
                "soh_after": cur["soh_percent"],
            })
    return out


def build_scenarios():
    """Moi kich ban tra ve (stream, mo_ta). Mo ta di thang vao manifest."""
    s = {}

    # --- 1-5: ma tran quyet dinh co ban, moi tham so hang so -----------------

    s["1_healthy_normal"] = (
        physics_stream(plateau_cell=3.32, current=SOLAR_CURRENT, temp=30.0,
                       cycle=300, soc_start=85.0),
        "Pin khoe, xa solar binh thuong trong cum nhiet train. Truong hop nen.",
    )

    # Nhiet do ra khoi cum train (TEMP_OOD warning, chua toi nguong TEMP_ELEVATED
    # cua LFP la 45C) -> action SCHEDULE_MAINTENANCE/P3
    s["2_healthy_temp_ood_warning"] = (
        physics_stream(plateau_cell=3.32, current=SOLAR_CURRENT, temp=38.0,
                       cycle=300, soc_start=85.0),
        "Pin khoe nhung 38C nam ngoai cum nhiet train -> canh bao TEMP_OOD.",
    )

    # Sensor glitch / loose-connector fault injection (IsolationForest Warning tier,
    # do thuc nghiem: score ~-0.20). v_amp PHAI giu per-cell trong [2.0, 3.8]
    # (range guard LFP) — bien do cu 40.0 day len 8.15 V/cell va bi API tu choi.
    s["3_sensor_glitch_anomaly"] = (
        spiky_stream(plateau_cell=3.32, current_base=SOLAR_CURRENT, temp_base=30.0,
                     cycle=300, soc_start=85.0, every=2, v_amp=0.7, i_amp=8.0, t_amp=3.0),
        "Pin khoe nhung cam bien/dau noi loi -> IsolationForest bat hinh dang bat thuong.",
    )

    s["4_end_of_life"] = (
        physics_stream(plateau_cell=3.02, current=SOLAR_CURRENT, temp=30.0,
                       cycle=2000, soc_start=85.0),
        "SOH ro rang duoi 80% (khong sat nguong) -> on dinh qua moi diem cat window.",
    )

    # TEMP_CRITICAL cua LFP la 55C, range guard cho toi 60C. KHONG dung qua ap:
    # OVERVOLTAGE_CRITICAL LFP can > 3.8 V/cell nhung range guard cung chan tai dung
    # 3.8 -> canh bao do KHONG BAO GIO phat sinh duoc qua API (dead code phia AI).
    s["5_healthy_temp_critical"] = (
        physics_stream(plateau_cell=3.32, current=SOLAR_CURRENT, temp=57.0,
                       cycle=300, soc_start=85.0),
        "Qua nhiet 57C tren pin con khoe — critical DUY NHAT con kha thi qua API.",
    )

    # --- 6-9: cac vung con thieu cua ma tran ---------------------------------

    # Bug lon nhat cua duong LFP hien tai: bo Severson chi co 30C nen pin KHOE doc
    # o 12C bi doc thanh chai. Giu kich ban nay lam moc do: sau khi v2.1 (them SNL
    # 15/25/35C) len production, SOH o day PHAI keo len gan pin khoe that.
    s["6_healthy_cold_morning"] = (
        physics_stream(plateau_cell=3.32, current=-2.0, temp=12.0,
                       cycle=300, soc_start=85.0),
        "Pin KHOE, sang som 12C, tai nhe. Moc do truc tiep cua bug nhiet do lanh.",
    )

    # Sat nguong EOL — day la vung nhan lat theo diem cat window (do duoc 4-8 diem
    # bien do tren du lieu NASA that). Manifest se ghi lai chinh xac co lat hay khong.
    s["7_borderline_eol"] = (
        physics_stream(plateau_cell=3.12, current=SOLAR_CURRENT, temp=30.0,
                       cycle=1500, soc_start=85.0),
        "SOH sat nguong 80% — kich ban de lo hien tuong lat nhan theo diem cat.",
    )

    # Kich ban THUC TE nhat trong ca bo: khong tham so nao la hang so.
    s["8_solar_day_ramp"] = (
        physics_stream(plateau_cell=3.30, current=cloudy_load(SOLAR_CURRENT),
                       temp=solar_day_temp(), cycle=600, soc_start=88.0),
        "Nua ngay ngoai troi: nhiet 22->44->22C, tai bien thien theo may. Mot stream "
        "duy nhat di xuyen ca trong lan ngoai cum nhiet train.",
    )

    # Xa sau: bat dau o SOC thap nen stream cham vung sup ap duoi 20% SOC.
    s["9_deep_discharge_knee"] = (
        physics_stream(plateau_cell=3.30, current=-2.5, temp=30.0,
                       cycle=400, soc_start=32.0),
        "Xa sau qua diem gay 20% SOC — dien ap sup nhanh, kiem tra canh bao ap thap.",
    )

    # --- 10-13: tai, nhiet, ket hop --------------------------------------------

    # BMS JK rated 100-200 A. Tran dong AI la 5C cell -> 136 A voi pack 30 Ah LFP
    # (chi 75 A neu BE quen khai chemistry — xem nasa-constants-leak).
    s["10_pulsed_high_load"] = (
        physics_stream(plateau_cell=3.30, current=pulsed_load(SOLAR_CURRENT, -100.0),
                       temp=34.0, cycle=500, soc_start=88.0, r_int=R_INT_CELL),
        "Tai nen -5 A + xung -100 A (bom/inverter khoi dong), co sut ap I*R. "
        "Kiem tra tran dong theo chemistry (LFP 30 Ah -> 136 A).",
    )

    # Nhiet tang dan xuyen qua nguong TEMP_ELEVATED (45C) roi TEMP_CRITICAL (55C)
    # NGAY TRONG mot stream -> ket qua CO CHU DICH doi theo diem cat. Day la kich ban
    # duy nhat co chu y khong on dinh, dung de chung minh manifest phat hien duoc.
    s["11_thermal_escalation"] = (
        physics_stream(plateau_cell=3.30, current=-3.0, temp=ramp(33.0, 59.0),
                       cycle=700, soc_start=88.0),
        "Nhiet tang dan 33->59C xuyen qua ca nguong ELEVATED va CRITICAL trong cung "
        "mot stream — CO CHU DICH khong on dinh theo diem cat.",
    )

    # To hop xau nhat con thuc te: pin da chai VA dang nong.
    s["12_degraded_and_hot"] = (
        physics_stream(plateau_cell=3.06, current=-4.0, temp=48.0,
                       cycle=1800, soc_start=85.0),
        "Pin chai + dang nong 48C — to hop uu tien cao nhat trong van hanh that.",
    )

    # Dong DUONG = dang sac. Model chi train tren pha xa; BE khong nen gui window
    # sac. Giu lai de tai lieu hoa ro AI tra ve gi neu BE gui nham.
    s["13_charging_window"] = (
        physics_stream(plateau_cell=3.32, current=+6.0, temp=30.0,
                       cycle=300, soc_start=40.0),
        "Dong DUONG (dang sac) — input sai quy uoc. Tai lieu hoa hanh vi khi BE gui nham.",
    )

    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=None,
                    help="Chi sinh mot so kich ban, vd '6,7,11' (theo so dau ten file)")
    ap.add_argument("--offset-stride", type=int, default=1,
                    help="Buoc quet offset. DE 1 cho ban chinh thuc; >1 chi de chay nhanh.")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    print("Nap artifact...")
    model_loader.load_models()

    scenarios = build_scenarios()
    if args.only:
        keep = {x.strip() for x in args.only.split(",") if x.strip()}
        scenarios = {k: v for k, v in scenarios.items() if k.split("_")[0] in keep}
        if not scenarios:
            raise SystemExit(f"--only {args.only!r} khong khop kich ban nao")

    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    if args.only and os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {"format": {}, "scenarios": {}}

    manifest["format"] = {
        "columns": COLUMNS,
        "pack_config": {"n_series": N_SERIES, "chemistry": CHEMISTRY,
                        "capacity_ah": CAPACITY_AH},
        "sample_dt_seconds": SAMPLE_DT,
        "window_size": WINDOW_SIZE,
        "note": (
            f"Voltage/current la muc PACK (8S/24V/30Ah) — AI module tu chia per-cell "
            f"server-side theo pack_config. Moi file la 1 stream LIEN TUC {STREAM_LEN} dong "
            "(khong phai 1 window 30 dong don le) — BE/simulator co the cat window 30-dong o "
            "BAT KY vi tri nao trong 1 file va van ra dung ket qua da kiem chung (xem "
            "consistent_across_offsets). KHONG duoc noi 2 file khac nhau lam 1 stream lien "
            "tuc cho cung 1 battery_id — window bac qua ranh gioi 2 file la du lieu vo nghia. "
            f"Cot `time` trong file la thoi gian TUYET DOI trong stream; BE PHAI rebase ve 0 "
            f"o dong dau MOI window truoc khi goi API (dt={SAMPLE_DT:g}s => window dai "
            f"{WINDOW_SIZE * SAMPLE_DT:g}s, nam trong dai scaler)."
        ),
    }

    # Do thang tren pipeline that, khong phai uoc luong. Ghi vao manifest de BE doc
    # duoc cung cho voi ky vong cua tung kich ban — day la nhung gioi han BE PHAI
    # thiet ke xung quanh, khong phai loi cua bo du lieu demo.
    manifest["known_limitations"] = {
        "soh_depends_on_sampling_rate": {
            "measured_2026_08_11": {"dt_10s": 76.1, "dt_20s": 67.7, "dt_30s": 64.9,
                                    "dt_48s": 62.0},
            "note": (
                "CUNG mot qua pin, CUNG SOC, chi doi chu ky lay mau: SOH lech 14 diem. "
                "`time` la input tho tinh bang GIAY nen window 300 s va window 1440 s la "
                "hai vung phan bo khac nhau doi voi model. BE PHAI CO DINH chu ky lay mau "
                f"cho toan he ({SAMPLE_DT:g}s trong bo demo nay) va khong duoc doi giua chung; "
                "doi nhip lay mau = doi ket qua ma khong co canh bao nao."
            ),
        },
        "soh_depends_on_position_in_discharge": {
            "note": (
                "Cung mot chu ky xa, cat window o dau vs cuoi cho SOH khac nhau. Voi pin "
                "khoe (xa nguong 80%) bien do nho va nhan on dinh; voi pin SAT nguong bien "
                "do len toi hon 20 diem va nhan lat Healthy <-> End Of Life. Xem "
                "`soh_spread_points` cua tung kich ban. BE KHONG duoc ra quyet dinh thay pin "
                "tu MOT lan doc: lay median nhieu window trong cung chu ky, hoac yeu cau N "
                "lan doc lien tiep moi doi trang thai ticket."
            ),
        },
        "sampling_rate_upper_bound": {
            "note": (
                "Scaler LFP dang deploy fit `time` tren [0, 1453.9] s => 30 x dt <= 1454 "
                "=> dt <= 48.5 s. Gateway day 60 s/lan se dua window ra ngoai vung train va "
                "SOH sai am tham. Sau khi v2.1 (them Sandia) len production, dai nay noi "
                "thanh ~7053 s => dt <= 235 s."
            ),
        },
    }

    t_start = time.perf_counter()
    for name, (stream, desc) in scenarios.items():
        csv_path = os.path.join(OUT_DIR, f"{name}.csv")
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(stream)

        t0 = time.perf_counter()
        offset_results = evaluate_all_offsets(stream, name, stride=args.offset_stride)
        stages = {r["health_stage"] for r in offset_results}
        actions = {r["action_code"] for r in offset_results}
        priorities = {r["priority"] for r in offset_results}
        consistent = len(stages) == 1 and len(actions) == 1 and len(priorities) == 1

        tag = "OK  " if consistent else "VARY"
        soh_lo = min(r["soh_percent"] for r in offset_results)
        soh_hi = max(r["soh_percent"] for r in offset_results)
        print(
            f"  [{tag}] {name}: SOH {soh_lo:.1f}-{soh_hi:.1f}% ({soh_hi - soh_lo:.1f} diem) "
            f"qua {len(offset_results)} offset in {time.perf_counter() - t0:.0f}s\n"
            f"         stage={sorted(stages)} action={sorted(actions)} "
            f"priority={sorted(str(p) for p in priorities)}"
        )

        manifest["scenarios"][name] = {
            "file": f"{name}.csv",
            "description": desc,
            "stream_len": len(stream),
            "offsets_tested": len(offset_results),
            "offset_stride": args.offset_stride,
            "consistent_across_offsets": consistent,
            # Chi kich ban on dinh moi dung lam ky vong cho test tich hop. Kich ban
            # KHONG on dinh van co gia tri — no chi ro cho BE phai co hysteresis.
            "usable_as_fixed_expectation": consistent,
            "expected": {
                "health_stage": sorted(stages),
                "anomaly_status": sorted({r["anomaly_status"] for r in offset_results}),
                "action_code": sorted(actions),
                "priority": sorted({str(r["priority"]) for r in offset_results}),
                "soh_percent_range": [soh_lo, soh_hi],
                "soh_spread_points": round(soh_hi - soh_lo, 2),
            },
            # KHONG dump ca 1171 ban ghi offset (manifest phinh len 2.2 MB va khong
            # ai doc noi). Hai thu duoi tra loi dung cau hoi can tra loi: "nhan doi o
            # dau" va "moi nhan chiem bao nhieu phan stream".
            "label_distribution": _label_distribution(offset_results),
            "label_transitions": _label_transitions(offset_results),
        }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nDa ghi {len(scenarios)} scenario + manifest.json vao {OUT_DIR}/ "
          f"({time.perf_counter() - t_start:.0f}s)")


if __name__ == "__main__":
    main()

"""
Convert raw NASA PCoE .mat battery files → cleaned_dataset CSV format
expected by scripts/preprocess.py (metadata.csv + data/*.csv per cycle).

Usage:
    python scripts/convert_mat_to_csv.py --raw-dir data/raw/nasa/mat --output-dir data/raw/nasa/cleaned_dataset

Input:
    data/raw/nasa/mat/B0005.mat, B0006.mat, ... (downloaded from NASA PCoE / Kaggle mirror)

Output:
    data/raw/nasa/cleaned_dataset/metadata.csv        (battery_id, type, Capacity, test_id, filename)
    data/raw/nasa/cleaned_dataset/data/{battery_id}_{type}_{n}.csv  (Voltage_measured, Current_measured, Temperature_measured, Time)
"""

import argparse
import glob
import os

import numpy as np
import pandas as pd
import scipy.io


def load_battery_cycles(mat_path: str) -> list[dict]:
    """Parse one NASA .mat file into a list of cycle records (charge + discharge only)."""
    battery_id = os.path.splitext(os.path.basename(mat_path))[0]
    mat = scipy.io.loadmat(mat_path, simplify_cells=True)
    cycles = mat[battery_id]["cycle"]

    records = []
    for cycle in cycles:
        ctype = cycle["type"]
        if ctype not in ("charge", "discharge"):
            continue  # skip impedance — different fields, unused by preprocess.py

        data = cycle["data"]
        n = min(
            len(np.atleast_1d(data["Voltage_measured"])),
            len(np.atleast_1d(data["Current_measured"])),
            len(np.atleast_1d(data["Temperature_measured"])),
            len(np.atleast_1d(data["Time"])),
        )
        records.append(
            {
                "battery_id": battery_id,
                "type": ctype,
                "capacity": float(data["Capacity"]) if ctype == "discharge" else None,
                "df": pd.DataFrame(
                    {
                        "Voltage_measured": np.atleast_1d(data["Voltage_measured"])[:n],
                        "Current_measured": np.atleast_1d(data["Current_measured"])[:n],
                        "Temperature_measured": np.atleast_1d(data["Temperature_measured"])[:n],
                        "Time": np.atleast_1d(data["Time"])[:n],
                    }
                ),
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True, help="Folder chứa file .mat gốc")
    parser.add_argument("--output-dir", required=True, help="Folder output cleaned_dataset")
    args = parser.parse_args()

    data_dir = os.path.join(args.output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    mat_files = sorted(glob.glob(os.path.join(args.raw_dir, "*.mat")))
    if not mat_files:
        raise FileNotFoundError(f"Không tìm thấy file .mat nào trong {args.raw_dir}")

    meta_rows = []
    for mat_path in mat_files:
        records = load_battery_cycles(mat_path)
        for test_id, rec in enumerate(records):
            filename = f"{rec['battery_id']}_{rec['type']}_{test_id}.csv"
            rec["df"].to_csv(os.path.join(data_dir, filename), index=False)
            meta_rows.append(
                {
                    "battery_id": rec["battery_id"],
                    "type": rec["type"],
                    "Capacity": rec["capacity"],
                    "test_id": test_id,
                    "filename": filename,
                }
            )
        print(f"{os.path.basename(mat_path)}: {len(records)} cycles")

    meta_path = os.path.join(args.output_dir, "metadata.csv")
    pd.DataFrame(meta_rows).to_csv(meta_path, index=False)
    print(f"\nĐã ghi {len(meta_rows)} cycles → {meta_path}")


if __name__ == "__main__":
    main()

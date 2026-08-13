# Plan — LFP per-temperature error measurement

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-08-12
- **Issue:** chưa tạo — xem §Ghi chú cuối
- **Bối cảnh:** sau khi wire `soh_mamba_v2.1-lfp.pth` vào production (config sync 3 hằng số)

## Mục tiêu

Làm cho sai số của model LFP **đo được theo nhiệt độ và theo từng cell**, thay vì một con số
gộp duy nhất.

Đây là bước 1/3 của hướng "optimize cho mọi trường hợp". Nó **không cải thiện độ chính xác** —
nó là điều kiện để biết bước 2 (lọc dữ liệu bẩn) và bước 3 (xử lý confound nhiệt độ) có tác
dụng thật hay không.

## Vấn đề cụ thể

1. `data/processed_lfp/{train,val,test}.pt` chỉ chứa `X`, `X_feat`, `y`
   ([preprocess_snl.py:570-578](../../scripts/preprocess_snl.py#L570-L578)). Không có `cell_id`,
   không có nhiệt độ per-window ⇒ **không thể** cắt lỗi theo nhiệt độ hay theo cell.
2. `test_mae = 1.5421%` là số gộp. Test split = 1 cell SNL @35 °C + các cell Severson @30 °C
   ⇒ con số bị nhóm 30 °C áp đảo, không nói gì về 35 °C riêng.
3. Đo thực nghiệm: cùng một cửa sổ xả, đổi nhiệt độ 10→40 °C làm SOH lệch **7.6 điểm** và lật
   nhãn `Normal → Degrading` tại 35 °C. Chưa biết đây là quy luật thật của dữ liệu hay lối tắt
   model học được — không có công cụ đo thì không kết luận được.

## Scope

**Trong scope**
- Ghi metadata per-window (cell_id, nhiệt độ thô, cycle_idx) vào file `.pt` của đường SNL+Severson
- Script eval cắt sai số theo lưới (nhiệt độ × dải SOH) và theo từng cell
- Cell notebook Kaggle chạy eval đó sau khi train

**Ngoài scope** (làm ở bước sau, không gộp vào đây)
- Lọc dữ liệu bẩn (`temperature min = 0.0 °C`, `voltage min = 1.889 V/cell`)
- Ablation bỏ feature nhiệt độ / LOTO eval
- Retrain, đổi hyperparameter, đổi split
- Đường NASA (`scripts/preprocess.py`) — giữ nguyên

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/preprocess_lfp.py` | modify | `cycles_to_windows()` thêm tham số `return_meta=False`; khi True trả thêm dict meta |
| `scripts/preprocess_snl.py` | modify | Gọi với `return_meta=True`, lưu meta vào `.pt` |
| `scripts/eval_soh_by_temp.py` | create | Eval cắt theo lưới nhiệt độ × SOH + theo cell |
| `notebooks/kaggle_train_lfp_v21.ipynb` | modify | Thêm 1 cell chạy eval sau cell train |
| `tests/test_preprocess_snl.py` | modify | Thêm test cho meta (file này đang untracked — WIP của user) |

## Approach

### 1. `cycles_to_windows(..., return_meta=False)`

Hàm này **dùng chung** giữa `preprocess_lfp.py` và `preprocess_snl.py`, nên **không đổi chữ ký
trả về mặc định** — thêm tham số opt-in để caller cũ không gãy.

Khi `return_meta=True`, trả thêm `dict`:

| Khoá | Kiểu | Nguồn |
|---|---|---|
| `cell_idx` | `int32[N]` | chỉ số vào `cell_ids` |
| `cell_ids` | `list[str]` | bảng tra ngược |
| `temp_mean_c` | `float32[N]` | `cycle_raw[i:i+30, 2].mean()` — **độ C thô, TRƯỚC khi scale** |
| `cycle_idx` | `int32[N]` | số chu kỳ thật của cửa sổ |

`temp_mean_c` phải lấy từ `cycle_raw` chứ không phải `cycle_scaled`: cắt theo trục đã MinMax-scale
là cắt theo một trục phụ thuộc scaler, không so sánh được giữa các lần train.

### 2. Lưu vào `.pt`

Thêm khoá vào dict `torch.save`. **Tương thích ngược**: `load_split()`
([train.py:125-143](../../scripts/train.py#L125-L143)) chỉ đọc `X`/`X_feat`/`y` và bỏ qua khoá lạ
⇒ file mới vẫn train được bằng code cũ, file cũ vẫn load được bằng code mới (eval báo thiếu meta
và dừng có thông báo rõ, không traceback).

### 3. `scripts/eval_soh_by_temp.py`

```
--data-dir data/processed_lfp --split test
--weights models/weights/soh_mamba_v2.1-lfp.pth
--feature-scaler models/weights/feature_scaler_lfp.pkl
```

Dùng lại `evaluate()` của `train.py` để không lệch convention tính metric. Xuất:

- Bảng **MAE / RMSE / N** theo bin nhiệt độ 5 °C × dải SOH (`<80`, `80-85`, `85-90`, `90-95`, `≥95`)
- Bảng **MAE / RMSE / N** theo từng `cell_id`
- Đánh dấu ô có `N` dưới ngưỡng là **không đủ mẫu để kết luận** — quan trọng vì test hiện chỉ có
  1 cell SNL, phần lớn ô sẽ rỗng và đó chính là phát hiện cần thấy

### 4. Cell notebook

Chạy sau cell train, in bảng ra output Kaggle. Dữ liệu SNL/Severson chỉ có trên Kaggle
(`data/raw/` local chỉ có NASA) nên eval này **không chạy được ở local**.

## Steps

- [ ] B1: `return_meta` cho `cycles_to_windows` + test giữ nguyên hành vi khi `False`
- [ ] B2: `preprocess_snl.py` lưu meta vào 3 file `.pt` + test có đủ 4 khoá, `temp_mean_c` đúng °C thô
- [ ] B3: `eval_soh_by_temp.py` + test trên dữ liệu giả nhỏ
- [ ] B4: Cell notebook
- [ ] B5: `pytest tests/ -v` PASS (hiện 702 passed — không được giảm)
- [ ] B6: User chạy preprocess + train + eval trên Kaggle → lấy bảng số thật

## Tiêu chí hoàn thành

Chạy được 1 lệnh trên Kaggle và đọc ra: **"ở 35 °C, dải SOH 80-85%, MAE là X% trên N mẫu"**.
Nếu N quá nhỏ để kết luận thì bảng phải nói thẳng điều đó.

## Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Đổi hàm dùng chung làm gãy `preprocess_lfp.py` | Tham số opt-in, mặc định giữ nguyên chữ ký cũ; test khoá hành vi mặc định |
| File `.pt` cũ không có meta | Eval báo lỗi rõ ràng kèm lệnh preprocess cần chạy lại |
| `tests/test_preprocess_snl.py` là WIP chưa commit của user | Chỉ **thêm** test mới, không sửa/xoá test đang có |
| Phải preprocess lại toàn bộ trên Kaggle | Có — meta chỉ sinh khi chạy lại. Không cần train lại: eval nạp checkpoint sẵn có |

## Ghi chú

Chưa tạo GitHub Issue. Repo có tiền lệ plan không gắn số (`logs/fix-artifact-contract-guard/`,
`logs/eval/`). Nếu muốn theo đúng flow Sprint Board thì tạo issue trước với đủ nhãn
`status: init` / `role: AI` / `priority` / `type: feat`, rồi đổi tên thư mục thành `logs/GH-<n>/`.

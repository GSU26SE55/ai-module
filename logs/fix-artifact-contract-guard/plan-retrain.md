# Plan — Retrain RUL + Forecast (một lượt Kaggle duy nhất)

## Metadata

- **Status:** PLANNING · **Role:** AI · **Ngày:** 2026-08-07
- **Nhánh:** `fix/artifact-contract-guard`
- **Issue:** không có — user yêu cầu làm thẳng

---

## 1. Trả lời trước: cái gì PHẢI retrain, cái gì KHÔNG

| Artifact | Retrain? | Bằng chứng |
|---|---|---|
| SOH NASA `soh_mamba_v1.6.pth` | **KHÔNG** | `feat_dim=57` khớp extractor · e2e PASS · đang phục vụ production |
| SOH LFP `soh_mamba_v2.0-lfp.pth` | **KHÔNG** | `feat_dim=57` khớp · pin thật chấm đúng |
| Long `soh_mamba_long_v2.2.pth` | **KHÔNG** | `feat_dim=57` khớp |
| **RUL** `soh_mamba_rul_v1.0.pth` | **CÓ** | checkpoint lưu `feat_dim=54`, extractor sinh 57 → chết hẳn |
| **Forecast** `soh_mamba_forecast_v1.0.pth` | **CÓ** | file không tồn tại |

**Không đụng 3 model đang chạy.** Chúng đúng, và retrain là rủi ro không có lợi ích:
số liệu bài báo NCKH và hành vi BE đều đang dựa trên chúng.

---

## 2. Hai phát hiện làm đổi phạm vi

### 2.1 Forecast KHÔNG train được ngay — cần sửa code trước

Cả `train.py` chỉ có **3 chỗ `torch.save`**: SOH (dòng 457), long (855), RUL (1036).
**Không chỗ nào lưu forecast.**

`FORECAST_MAMBA_PATH` đã khai trong `config.py:133`, nhưng hai hàm `train_forecast_lobo()`
và `train_forecast_delta()` **chỉ đánh giá LOBO rồi in kết quả** — chạy xong không để lại gì.

⇒ Đây **không phải** "chỉ retrain". Phải thêm phần lưu checkpoint vào `train_forecast_delta()`
(nhánh `--delta`, help text ghi rõ *"safe multi-battery"*) trước khi có gì để train.

### 2.2 Dữ liệu RUL cực nhỏ — metric mặc định gần như vô nghĩa

```
data/processed_rul/train.pt : X (137, 30, 54)   <- 137 mau
                val.pt      : X ( 11, 30, 54)
                test.pt     : X (  5, 30, 54)   <- 5 mau
```

`test_mae_cycles=9.7057` ghi trong checkpoint cũ được đo trên **5 mẫu**. Con số đó không
mang ý nghĩa thống kê nào.

Đây chính là lý do `--lobo` tồn tại: NASA chỉ có ~26 pin, cắt theo pin thì tập test bé tí.
Leave-one-battery-out dùng lần lượt từng pin làm test → ước lượng đáng tin hơn nhiều.

⇒ Notebook chạy **cả hai**:
- `--rul` → sinh checkpoint để ship
- `--rul --lobo` → sinh **con số trung thực** để ghi vào tài liệu

Ghi `test_mae_cycles` từ nhánh 5 mẫu vào báo cáo là tự lừa mình.

> Lưu ý: dữ liệu local đang là **54 chiều** (sinh trước Gini). Notebook chạy lại preprocess
> trên Kaggle nên sẽ ra 57 — đó là mục đích.

### 2.3 Nhân tiện sửa gốc rễ của cảnh báo sklearn

Các notebook cũ cài `%pip install -q scikit-learn` **không ghim version** → Kaggle cho bản
nào thì dùng bản đó (đã ra 1.5.0), trong khi `requirements.txt` ghim **1.6.1**. Đó là lý do
mọi `.pkl` load lên đều kêu `InconsistentVersionWarning`.

Notebook mới ghim `scikit-learn==1.6.1`. Artifact **mới** sinh ra sẽ hết cảnh báo.
Các `.pkl` production cũ vẫn còn cảnh báo — xử riêng, không gộp vào đây.

---

## 3. Files

| File | Action | Ghi chú |
|---|---|---|
| `scripts/train.py` | modify | Thêm lưu checkpoint vào `train_forecast_delta()` — kèm `feat_dim`, `version`, `lookback`, `horizon` |
| `notebooks/kaggle_retrain_rul_forecast.ipynb` | create | Notebook một lượt, làm cả RUL lẫn Forecast |

Không đụng `models/weights/` ở local — artifact tải về từ Kaggle rồi mới commit.

---

## 4. Thiết kế notebook

Bám đúng khuôn `kaggle_train_lfp.ipynb` (đã được tôi luyện qua nhiều lần chạy hỏng), giữ
nguyên các bài học đắt giá:

| Cell | Nội dung | Vì sao |
|---|---|---|
| 1 | `nvidia-smi` + version torch | Chọn **GPU T4 x2**, KHÔNG dùng P100 (Kaggle PyTorch đã bỏ sm_60) |
| 2 | Clone repo, `BRANCH` là biến ở đầu | Dễ đổi khi cần |
| 3 | **Kiểm code clone về đúng bản mới** | Đúng cái bẫy từng làm mất ~11 giờ: notebook đã sửa nhưng code trên GitHub chưa push. Cell này fail → về máy `git push` |
| 4 | `%pip install scikit-learn==1.6.1 scipy joblib pandas` | Ghim version, xem §2.3 |
| 5 | Tìm NASA `cleaned_dataset` trong `/kaggle/input` | Cả RUL lẫn Forecast đều dùng bộ này ⇒ một lần **+ Add Data** |
| 6 | `preprocess_rul.py` + `preprocess_forecast.py` | Sinh lại dữ liệu **57 chiều** |
| 7 | Chốt dữ liệu ra đúng 57 chiều **trước khi train** | Sai chiều thì train xong mới biết là mất công vô ích |
| 8 | Train RUL (`--rul`) | Sinh checkpoint để ship |
| 9 | Train Forecast (`--forecast --delta`) | Cần code mới ở §2.1 |
| 10 | **ĐÓNG GÓI artifact vào zip** | **Đặt TRƯỚC bước chẩn đoán.** Một lần `assert` chẩn đoán fail đã giết notebook *sau khi* train xong 4 tiếng, mất sạch artifact |
| 11 | RUL LOBO (`--rul --lobo`) | Con số trung thực để ghi tài liệu |
| 12 | Kiểm nghiệm thu | Xem §5 |
| 13 | Dọn repo clone | Giảm dung lượng output |

**Thời gian ước tính:** rất nhanh — 137 mẫu × 30 chu kỳ × 57 chiều là bé. Cỡ **phút**, không
phải giờ. Một phiên Kaggle thừa sức chứa cả 3 lượt train.

---

## 5. Tiêu chí nghiệm thu (cell 12)

```python
assert ck_rul["feat_dim"] == 57          # guard mới sẽ chặn nếu sai
assert ck_forecast["feat_dim"] == 57
assert sklearn.__version__ == "1.6.1"    # khớp requirements.txt
```

Sau khi tải artifact về máy, kiểm ở local:

```
python -m pytest tests/ -q          # guard _resolve_feat_dim phải cho qua
python scripts/e2e_full_test.py     # 3 model production không được đổi hành vi
```

Nếu `_resolve_feat_dim()` vẫn raise sau khi thay artifact ⇒ preprocess trên Kaggle chưa
sinh đúng 57 chiều. **Không** sửa `SPECTRAL_FEAT_DIM` cho khớp.

---

## 6. Steps

- [ ] R1. Thêm lưu checkpoint vào `train_forecast_delta()` trong `scripts/train.py`
- [ ] R2. Test cho phần lưu đó (checkpoint có đủ `version`/`feat_dim`/`lookback`/`horizon`)
- [ ] R3. Viết `notebooks/kaggle_retrain_rul_forecast.ipynb` theo §4
- [ ] R4. Chạy `pytest` + `ruff` ở local — không được phát sinh lỗi mới
- [ ] R5. Đưa lệnh commit + push (user **phải push trước** khi chạy notebook, xem cell 3)
- [ ] R6. *(user)* Chạy notebook trên Kaggle, tải zip artifact về
- [ ] R7. Sau khi có artifact: chạy lại pytest + e2e ở local, rồi commit artifact

---

## 7. Điều tôi không hứa

**RUL sau retrain vẫn sẽ là một model học từ 137 mẫu.** Guard mới làm nó *chạy được*, không
làm nó *chính xác*. Con số LOBO ở cell 11 mới là thứ nói thật về chất lượng — nếu nó tệ thì
kết luận đúng là **chưa ship RUL**, chứ không phải tinh chỉnh cho tới khi con số đẹp.

Tương tự với Forecast: NASA ~26 pin là ít cho bài toán dự báo chuỗi.

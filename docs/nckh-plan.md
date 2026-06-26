# Ke hoach NCKH - AI Module du doan SOH/RUL pin lithium-ion

> Ngay lap ke hoach: 2026-06-19  
> De tai du kien: Nghien cuu mo hinh du doan State of Health, Remaining Useful Life va phat hien bat thuong cho pin lithium-ion trong he thong nang luong mat troi  
> Pham vi repo: AI Module FastAPI + PyTorch, preprocessing, training, inference, evaluation  
> Pham vi thoi gian: 3 tuan, gia dinh model chinh da co san va trong tam la kiem chung - danh gia - viet bao cao - demo
> GitHub issue backlog chi tiet: `docs/nckh-mamba-github-issues.md`

## 1. Muc tieu nghien cuu

### Muc tieu chinh

Hoan thien, kiem chung va danh gia pipeline AI cho bai toan bao tri pin lithium-ion:

- Du doan SOH theo chuoi voltage, current, temperature.
- Du doan RUL hoac uoc luong vong doi con lai cua pin.
- Phat hien bat thuong va phan loai trang thai Normal, Degrading, Failed.
- So sanh anh huong cua sequence length `L` va viec bo sung dataset den do chinh xac.
- Dong goi thanh API de chung minh tinh ung dung trong he thong bao tri pin.

### Cau hoi nghien cuu

| Ma | Cau hoi |
|----|---------|
| RQ1 | Mo hinh Mamba/long-sequence co cai thien MAE/RMSE so voi CNN-LSTM, LSTM hoac baseline truyen thong khong? |
| RQ2 | Khi tang sequence length `L`, do chinh xac co tang on dinh hay chi tang den mot nguong nhat dinh? |
| RQ3 | Viec bo sung dataset sach, dung format, dung phan phoi co giup model tong quat hoa tot hon khong? |
| RQ4 | Pipeline inference co dap ung duoc latency muc tieu duoi 100ms khong? |

### Dau ra cuoi cung

- Bao cao NCKH hoan chinh.
- Bo thuc nghiem co log, bang ket qua va bieu do.
- Source code inference va script reproduce ket qua chinh co the chay lai.
- API demo du doan SOH/RUL va phan loai bat thuong.
- Slide thuyet trinh, poster neu can.

## 2. Thanh vien va vai tro

> Co the doi ten/vai tro neu nhom thay doi. Nguyen tac: moi nguoi co 1 mang chinh, 1 mang review cheo de viec duoc chia deu.

| Thanh vien | Vai tro chinh | Viec phu trach | Review cheo |
|------------|---------------|----------------|-------------|
| Tran Minh Tri | Leader + Research Coordinator | Lap scope, quan ly timeline, tong hop bao cao, dinh dang paper, dieu phoi meeting | Review API/demo va ket qua thuc nghiem |
| Nguyen Phuc Duy | Model Lead | SOH/RUL model, Mamba, long-sequence training, tuning hyperparameter | Review preprocessing va split data |
| Bui Phuoc Thang | Data Lead | Dataset, cleaning, preprocessing, feature engineering, train/val/test split | Review model training script |
| Mai Hong Thai | Evaluation Lead | Metric, baseline, ablation study, bang/bieu do ket qua, phan tich loi | Review paper methodology |
| Nguyen Nhat Minh | System + Demo Lead | FastAPI inference, demo flow, test API, tai lieu chay local, slide minh hoa | Review experiment log va reproducibility |

## 3. Nguyen tac chia viec

- Moi tuan moi thanh vien phai co mot deliverable ro rang.
- Khong ai chi lam tai lieu hoac chi lam code trong ca de tai; moi nguoi deu co phan nghien cuu, thuc nghiem va review.
- Moi task lon phai co owner va reviewer.
- Ket qua thuc nghiem phai ghi lai ngay sau khi chay, gom cau hinh, dataset, seed, metric va nhan xet.
- Khong thay doi test set sau khi da khoa protocol danh gia.
- Khi add dataset moi, phai kiem tra format, feature, label, missing value, leakage va phan phoi du lieu truoc khi train.

## 4. Timeline 3 tuan

| Tuan | Thoi gian | Muc tieu | Tri | Duy | Thang | Thai | Minh | Dau ra |
|------|-----------|----------|-----|-----|-------|------|------|--------|
| 1 | 2026-06-19 den 2026-06-25 | Khoa scope, paper, data protocol va reproduce model hien co | Chot de tai, outline bao cao, chia task, gom paper chinh | Kiem tra model/checkpoint hien co, ghi lai architecture va command reproduce | Thong ke dataset, kiem tra split, viet protocol preprocessing | Chot metric, tao template bang ket qua, kiem tra log cu | Kiem tra API/demo hien co, tao input mau | Scope 3 tuan + paper list + data protocol + reproduce result lan 1 |
| 2 | 2026-06-26 den 2026-07-02 | Chay thuc nghiem bo sung va tao bang/bieu do | Viet Related Work va Methodology ban dau | Chay lai best model, ablation `L` toi thieu 2-3 cau hinh, fine-tune neu can | Chuan hoa artifact data, ghi thong ke dataset, neu add dataset thi validate truoc | Tong hop MAE/RMSE/latency, ve chart prediction vs ground truth, error analysis | Test endpoint voi model artifact, do latency, quay/ghi demo flow | Bang ket qua + bieu do + demo API chay duoc |
| 3 | 2026-07-03 den 2026-07-09 | Hoan thien bao cao, slide, demo va Q&A | Tong hop report, format citation, chia phan thuyet trinh | Viet/chot phan model, chuan bi Q&A ve architecture va training | Viet/chot phan dataset, chuan bi Q&A ve split va leakage | Viet/chot phan experiments/results, kiem tra logic ket luan | Hoan thien slide demo, huong dan chay local, test lan cuoi | Final report + slide + demo + Q&A checklist |

## 5. Work package chi tiet

### WP1 - Literature Review

Owner: Tri  
Reviewer: Thai

Checklist:

- [ ] Tim 3-4 paper ve SOH prediction.
- [ ] Tim 2-3 paper ve RUL prediction neu giu scope RUL.
- [ ] Tim 2-3 paper ve Mamba, SSM hoac time-series deep learning.
- [ ] Tim 2-3 paper ve battery anomaly detection hoac predictive maintenance.
- [ ] Tao bang tong hop: paper, dataset, model, metric, ket qua, diem co the hoc.

Definition of Done:

- Co file tong hop paper.
- Moi paper co it nhat 3 y: bai toan, phuong phap, ket qua.
- Chon duoc 3-5 paper chinh de dua vao Related Work.

### WP2 - Dataset va preprocessing

Owner: Thang  
Reviewer: Duy

Checklist:

- [ ] Liet ke dataset dang dung: nguon, so battery, so cycle, feature, label.
- [ ] Kiem tra missing value, outlier, don vi do.
- [ ] Chot feature input: voltage, current, temperature va feature bo sung neu co.
- [ ] Chot label: SOH, RUL, anomaly status.
- [ ] Dam bao split theo battery/cycle hop ly, tranh data leakage.
- [ ] Neu add dataset moi, ghi ro truoc/sau khi merge co bao nhieu sample.

Definition of Done:

- Co protocol preprocessing co the lap lai.
- Co file train/val/test artifact dung format.
- Co bang thong ke dataset truoc va sau preprocessing.

### WP3 - Model training

Owner: Duy  
Reviewer: Thang

Checklist:

- [ ] Kiem tra checkpoint/model hien co: version, input shape, `L`, feature dim, metric da co.
- [ ] Chay lai best model de reproduce ket qua chinh.
- [ ] Chay ablation nho theo `L` voi 2-3 cau hinh uu tien: vi du 30, 512, 1024 hoac 4096 neu may cho phep.
- [ ] Fine-tune hoac train lai chi khi metric reproduce bi lech hoac dataset thay doi.
- [ ] Train/evaluate RULPredictor neu scope RUL duoc giu va artifact da san sang.
- [ ] Luu config, seed, checkpoint, log va metric.
- [ ] Chay them 1 seed phu cho best model neu du thoi gian.

Definition of Done:

- Moi experiment co command, config, log, metric.
- Model hien co co MAE/RMSE ro rang tren test set.
- Ket qua co the tai lap tu script.

### WP4 - Evaluation va phan tich

Owner: Thai  
Reviewer: Tri

Checklist:

- [ ] Dinh nghia metric: MAE, RMSE, MAPE neu can, latency, F1/anomaly neu co label.
- [ ] Lap bang so sanh baseline vs Mamba vs long-sequence.
- [ ] Lap bang ablation theo `L`.
- [ ] Lap bang before/after add dataset.
- [ ] Ve bieu do prediction vs ground truth.
- [ ] Phan tich case model sai nhieu.

Definition of Done:

- Co bang ket qua dung de dua thang vao report.
- Co it nhat 3 bieu do quan trong.
- Co nhan xet tai sao model tot/xau, khong chi ghi so.

### WP5 - API, demo va reproducibility

Owner: Minh  
Reviewer: Tri

Checklist:

- [ ] Kiem tra endpoint predict hien co.
- [ ] Dam bao model/scaler load mot lan khi startup.
- [ ] Test response co SOH/RUL/classification/confidence/latency neu scope yeu cau.
- [ ] Tao script demo hoac notebook goi API.
- [ ] Viet huong dan setup local.
- [ ] Kiem tra latency inference duoi 100ms voi input mau.

Definition of Done:

- Demo chay duoc tren may nhom.
- Co input mau va output mau.
- Co huong dan reproduce ngan gon.

### WP6 - Bao cao, slide va bao ve

Owner: Tat ca  
Reviewer cuoi: Tri

Checklist:

- [ ] Introduction: bai toan, dong luc, muc tieu.
- [ ] Related Work: so sanh cac huong tiep can.
- [ ] Methodology: data, model, training, metric.
- [ ] Experiments: setup, ket qua, ablation.
- [ ] Discussion: y nghia, gioi han, huong phat trien.
- [ ] Conclusion: dong gop chinh.
- [ ] Slide: problem, method, result, demo, conclusion.

Definition of Done:

- Bao cao khong thieu citation.
- Bang/bieu do co caption va giai thich.
- Slide co luong thuyet trinh ro rang, moi nguoi nam phan Q&A cua minh.

## 6. Ma tran thuc nghiem toi thieu

### Experiment 1 - Baseline comparison

| Model | L | Dataset | Metric can ghi |
|-------|---|---------|----------------|
| LSTM/CNN-LSTM | 30 | Dataset goc | MAE, RMSE, latency |
| MambaSOHPredictor | 30 | Dataset goc | MAE, RMSE, latency |
| Long Mamba | 512 hoac 1024 | Dataset goc | MAE, RMSE, latency |

### Experiment 2 - Anh huong sequence length `L`

| L | Muc dich | Ket qua can theo doi |
|---|----------|----------------------|
| 30 | Baseline ngan, nhanh | MAE/RMSE/latency |
| 128 | Them context gan | MAE/RMSE/latency |
| 512 | Context trung binh | MAE/RMSE/latency |
| 1024 | Context dai | MAE/RMSE/latency |
| 2048 hoac 4096 | Long-sequence | MAE/RMSE/VRAM/time train/latency |

### Experiment 3 - Anh huong add dataset

| Setup | Mo ta | Can ket luan |
|-------|------|--------------|
| Dataset goc | Chi dung data hien tai | Baseline metric |
| Dataset goc + dataset moi | Merge sau khi validate | Metric tang/giam bao nhieu |
| Dataset moi only neu du data | Kiem tra domain shift | Model co tong quat hoa khong |

### Experiment 4 - Robustness va reproducibility

| Setup | Muc dich |
|-------|----------|
| Seed 42 | Ket qua chinh |
| Seed 7 | Kiem tra on dinh |
| Seed 2026 | Kiem tra on dinh |
| Test latency CPU | Kiem tra kha nang deploy |

## 7. Template ghi log thuc nghiem

Dung format nay cho moi lan train:

```text
Experiment ID:
Ngay chay:
Nguoi chay:
Git commit:
Dataset:
Split:
Model:
L:
Feature:
Hyperparameter:
Seed:
Command:
Train time:
Best val loss:
Test MAE:
Test RMSE:
Latency:
Nhan xet:
File log/checkpoint:
```

## 8. Checklist add dataset moi

Truoc khi dua dataset moi vao training:

- [ ] Co nguon du lieu ro rang va co the cite.
- [ ] Co cung loai feature hoac co mapping hop ly sang voltage/current/temperature.
- [ ] Co label SOH/RUL hoac du thong tin tinh label.
- [ ] Khong co leakage giua train/val/test.
- [ ] Don vi do thong nhat.
- [ ] Missing value va outlier da duoc xu ly.
- [ ] So sanh phan phoi dataset moi voi dataset cu.
- [ ] Chay baseline truoc khi train model nang.

Ket luan can ghi ro:

- Dataset moi lam MAE/RMSE tang hay giam?
- Co giup khi tang `L` khong?
- Co lam model cham hon hoac kho train hon khong?
- Co domain shift khong?

## 9. Lich hop va cach quan ly

### Weekly meeting

- Thoi luong: 30-45 phut/tuan.
- Moi nguoi bao cao 3 y: da lam, dang vuong, tuan toi lam gi.
- Leader cap nhat timeline va unblock task.

### Daily async

Moi nguoi nhan nhanh tren group:

```text
Yesterday:
Today:
Blocker:
Need review from:
```

### Quy uoc review

- Code/model/data thay doi lon can it nhat 1 reviewer.
- Ket qua thuc nghiem can Evaluation Lead kiem tra truoc khi dua vao report.
- Bao cao can doc cheo: nguoi khong viet section do se review.

## 10. Rui ro va cach xu ly

| Rui ro | Anh huong | Cach xu ly |
|--------|-----------|------------|
| Dataset it, model overfit | Metric dep ao, kho bao ve | Split dung protocol, them baseline, dung regularization |
| Add dataset bi lech phan phoi | Metric giam | Bao cao nhu mot ket qua nghien cuu, khong ep merge neu khong tot |
| Tang `L` lam train cham/het VRAM | Cham tien do | Dung progressive warmup, micro-batch, gradient accumulation |
| Metric khong dat target | Kho thuyet phuc | Phan tich loi, them ablation, so sanh baseline cong bang |
| API demo loi luc bao ve | Mat diem demo | Chuan bi input mau, checkpoint on dinh, script demo offline |
| Bao cao thieu citation | Yeu phan NCKH | Chot Related Work ngay trong tuan 1, khong de cuoi ky |

## 11. Moc nghiem thu noi bo

| Moc | Dieu kien dat |
|-----|---------------|
| Gate 1 - Het tuan 1 | Co scope 3 tuan, paper list, data protocol, model hien co reproduce duoc |
| Gate 2 - Het tuan 2 | Co bang ket qua, bieu do, latency, error analysis va demo API chay duoc |
| Final - Het tuan 3 | Report, slide, demo, Q&A va artifact reproduce san sang |

## 12. Backlog uu tien

### Must have

- [ ] Literature review co citation.
- [ ] Dataset protocol tranh leakage.
- [ ] Model hien co reproduce duoc ket qua chinh.
- [ ] Bang MAE/RMSE va latency.
- [ ] It nhat 1 bang so sanh hoac ablation de the hien tinh nghien cuu.
- [ ] Report hoan chinh.
- [ ] Demo API.

### Should have

- [ ] Baseline comparison neu co san code/log.
- [ ] RUL prediction.
- [ ] Anomaly detection evaluation.
- [ ] Ablation theo `L` voi 2-3 cau hinh.
- [ ] So sanh truoc/sau khi add dataset.
- [ ] Them 1 seed phu cho best model.

### Nice to have

- [ ] Dashboard demo.
- [ ] Explainability/feature importance.
- [ ] Deployment container.
- [ ] Poster NCKH.

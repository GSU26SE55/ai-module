# GitHub Issue Plan - NCKH Mamba SOH Prediction

> Thoi gian: 3 tuan  
> Trong tam bai bao: Mo hinh Mamba/long-sequence cho du doan State of Health pin lithium-ion  
> Gia dinh hien tai: da co model/chung cu code chinh, can reproduce, danh gia, phan tich va viet bai bao  
> File lien quan: `docs/nckh-plan.md`

## 1. GitHub setup de chia task

### Milestones

| Milestone | Thoi gian | Muc tieu | Dieu kien dong milestone |
|-----------|-----------|----------|---------------------------|
| `W1 - Scope, Data, Reproduce` | 2026-06-19 den 2026-06-25 | Khoa cau hoi nghien cuu, paper nen, data protocol, reproduce model hien co | Co scope, paper list, data protocol, architecture note, metric reproduce lan 1 |
| `W2 - Experiments, Ablation, Analysis` | 2026-06-26 den 2026-07-02 | Chay thuc nghiem can cho bai bao Mamba | Co bang ket qua, ablation theo `L`, latency, error analysis, chart |
| `W3 - Paper, Slide, Demo` | 2026-07-03 den 2026-07-09 | Hoan thien bai bao va demo | Co final report, slide, demo script, Q&A checklist |

### Labels

| Label | Muc dich |
|-------|----------|
| `nckh` | Tat ca task thuoc bai nghien cuu |
| `paper:mamba` | Noi dung truc tiep lien quan dong gop Mamba |
| `type:research` | Doc paper, viet ly thuyet, tong hop tai lieu |
| `type:experiment` | Chay training/evaluation/benchmark |
| `type:docs` | Viet report, slide, reproducibility notes |
| `type:demo` | API, demo, script trinh bay |
| `area:data` | Dataset, preprocessing, split, leakage |
| `area:model` | Model architecture, checkpoint, training |
| `area:evaluation` | Metric, chart, error analysis |
| `area:paper` | Bao cao NCKH |
| `priority:P0` | Bat buoc co de bai bao hoan thanh |
| `priority:P1` | Nen co de bai bao thuyet phuc hon |
| `priority:P2` | Co thi tot, khong chan final |
| `blocked` | Dang bi chan boi data/model/log/quyet dinh |

### Thanh vien mac dinh

| Thanh vien | Role | Issue nen nhan |
|------------|------|----------------|
| Tran Minh Tri | Leader + Paper Coordinator | Scope, outline, report, review, slide |
| Nguyen Phuc Duy | Model Lead | Mamba architecture, checkpoint, reproduce, ablation |
| Bui Phuoc Thang | Data Lead | Dataset protocol, preprocessing, data statistics |
| Mai Hong Thai | Evaluation Lead | Metrics, results table, chart, error analysis |
| Nguyen Nhat Minh | Demo + Reproducibility Lead | API, latency, demo, setup guide |

## 2. Quy tac tao issue

Moi issue nen co format:

```md
## Goal

## Tasks
- [ ] ...

## Acceptance Criteria
- [ ] ...

## Deliverables
- ...

## Dependencies
- ...
```

Nguyen tac:

- Moi issue chi co 1 owner chinh va 1 reviewer.
- Issue P0 phai dong truoc khi sang final.
- Experiment issue phai gan kem log, command, config, seed, metric.
- Paper issue phai gan kem section/report file da cap nhat.
- Neu ket qua khong tot, van dong issue neu co phan tich ro ly do.

## 3. Board workflow

| Column | Y nghia |
|--------|---------|
| `Backlog` | Da tao issue nhung chua lam |
| `Ready` | Da ro input, co the lam ngay |
| `In Progress` | Dang lam |
| `Need Review` | Da co deliverable, cho reviewer kiem tra |
| `Done` | Dat Acceptance Criteria |

## 4. Issue backlog chi tiet

### Issue 01 - Khoa scope bai bao Mamba va dong gop chinh

Assignee: Tran Minh Tri  
Reviewer: Nguyen Phuc Duy  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `paper:mamba`, `type:research`, `area:paper`, `priority:P0`

## Goal

Khoa pham vi bai bao de ca nhom khong bi lech sang qua nhieu huong nhu RUL, anomaly hoac full system. Trong tam la Mamba cho du doan SOH pin lithium-ion.

## Tasks

- [ ] Dat ten de tai tam thoi.
- [ ] Chot bai toan chinh: SOH regression.
- [ ] Chot bai toan phu: RUL/anomaly/API chi dung de minh hoa neu khong du thoi gian.
- [ ] Viet 3-4 dong gop chinh cua bai bao.
- [ ] Chot cau hoi nghien cuu RQ1-RQ4.
- [ ] Chot metric bat buoc: MAE, RMSE, latency.
- [ ] Chot experiment bat buoc: reproduce model, ablation `L`, latency, error analysis.

## Acceptance Criteria

- [ ] Co 1 section scope trong report/plan.
- [ ] Ca nhom dong y rang bai bao tap trung vao Mamba-SOH.
- [ ] Co danh sach experiment P0/P1/P2.

## Deliverables

- Scope statement.
- Research questions.
- Contribution list.

## Dependencies

- Khong co.

---

### Issue 02 - Tong hop related work ve Mamba/SSM va SOH battery

Assignee: Tran Minh Tri  
Reviewer: Mai Hong Thai  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `paper:mamba`, `type:research`, `area:paper`, `priority:P0`

## Goal

Tao nen tang ly thuyet cho bai bao: vi sao dung Mamba/State Space Model cho chuoi thoi gian dai trong bai toan pin.

## Tasks

- [ ] Tim 2-3 paper ve Mamba hoac State Space Models cho sequence/time-series.
- [ ] Tim 3-4 paper ve SOH prediction/RUL lithium-ion battery.
- [ ] Tim 1-2 paper ve long sequence modeling hoac Transformer/LSTM baseline neu can so sanh.
- [ ] Lap bang: Paper, Dataset, Model, Metric, Ket qua, Diem lien quan den de tai.
- [ ] Viet ban nhap Related Work 600-900 tu.
- [ ] Ghi ro gap: LSTM/Transformer co han che voi chuoi dai, Mamba co loi the linear-time/long context.

## Acceptance Criteria

- [ ] Co it nhat 8 paper co citation day du.
- [ ] Co bang tong hop paper.
- [ ] Related Work da lien ket truc tiep voi dong gop Mamba cua nhom.

## Deliverables

- Bang literature review.
- Draft Related Work.

## Dependencies

- Issue 01.

---

### Issue 03 - Mo ta architecture MambaSOHPredictor tu code hien co

Assignee: Nguyen Phuc Duy  
Reviewer: Tran Minh Tri  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:model`, `area:paper`, `priority:P0`

## Goal

Bien code model hien co thanh mo ta khoa hoc ro rang trong Methodology.

## Tasks

- [ ] Doc `src/models/soh_predictor.py` va ghi lai input/output shape.
- [ ] Ghi ro cac thanh phan: input projection, Mamba block, normalization, pooling, feature fusion, regression head.
- [ ] Ghi ro cac hyperparameter quan trong: `d_model`, `d_state`, `pooling`, `input_features`, `feat_dim`, `L`.
- [ ] Giai thich vi sao Mamba phu hop chuoi pin dai hon LSTM/CNN-LSTM.
- [ ] Ve so do architecture bang Mermaid/ASCII hoac hinh trong report.
- [ ] Neu co `use_official_mamba`, ghi ro mode nao duoc dung trong experiment chinh.

## Acceptance Criteria

- [ ] Methodology co mo ta architecture doc lap, khong chi paste code.
- [ ] Co bang hyperparameter.
- [ ] Co hinh/diagram pipeline model.

## Deliverables

- Section Model Architecture.
- Bang hyperparameter.
- Architecture diagram.

## Dependencies

- Issue 01.

---

### Issue 04 - Khoa data protocol va chong data leakage

Assignee: Bui Phuoc Thang  
Reviewer: Nguyen Phuc Duy  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `type:docs`, `area:data`, `priority:P0`

## Goal

Dam bao ket qua bai bao dang tin cay: split train/val/test khong ro ri thong tin tuong lai hoac cung battery/cycle sai cach.

## Tasks

- [ ] Liet ke dataset dang dung: nguon, battery ID, so cycle, feature, label.
- [ ] Ghi ro cach tinh SOH label.
- [ ] Kiem tra input artifact: `train.pt`, `val.pt`, `test.pt` gom key nao.
- [ ] Ghi ro split theo battery/cycle/time va ly do.
- [ ] Kiem tra missing value/outlier/unit.
- [ ] Ghi ro cach tao window theo `L`.
- [ ] Tao bang data statistics: train/val/test samples, sequence length, feature dim, label range.

## Acceptance Criteria

- [ ] Co Data Protocol co the dua vao report.
- [ ] Co bang thong ke dataset.
- [ ] Co ket luan ro: cach split hien tai co/khong co leakage.

## Deliverables

- Data protocol.
- Dataset statistics table.

## Dependencies

- Issue 01.

---

### Issue 05 - Reproduce ket qua model Mamba hien co

Assignee: Nguyen Phuc Duy  
Reviewer: Mai Hong Thai  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `paper:mamba`, `type:experiment`, `area:model`, `area:evaluation`, `priority:P0`

## Goal

Chay lai hoac verify checkpoint hien co de co con so MAE/RMSE chinh dung cho bai bao.

## Tasks

- [ ] Xac dinh checkpoint Mamba chinh dang dung.
- [ ] Xac dinh command reproduce/evaluate.
- [ ] Ghi lai environment: Python, PyTorch, CPU/GPU, RAM/VRAM neu co.
- [ ] Chay evaluation tren test set.
- [ ] Ghi lai MAE, RMSE, loss, inference latency neu command co.
- [ ] Luu log vao folder/ghi duong dan log.
- [ ] So sanh ket qua reproduce voi metric da ghi trong checkpoint/log cu.

## Acceptance Criteria

- [ ] Co ket qua MAE/RMSE test set.
- [ ] Co command va config de nguoi khac chay lai.
- [ ] Sai lech voi log cu neu co phai duoc giai thich.

## Deliverables

- Experiment log.
- Bang reproduce result.
- Command reproduce.

## Dependencies

- Issue 04.

---

### Issue 06 - Tao bang experiment matrix cho bai bao Mamba

Assignee: Mai Hong Thai  
Reviewer: Tran Minh Tri  
Milestone: `W1 - Scope, Data, Reproduce`  
Labels: `nckh`, `paper:mamba`, `type:experiment`, `area:evaluation`, `priority:P0`

## Goal

Chot thuc nghiem nao bat buoc chay trong 3 tuan, tranh lam qua nhieu nhung khong co ket luan.

## Tasks

- [ ] Tao bang experiment P0/P1/P2.
- [ ] P0: reproduce Mamba best model.
- [ ] P0: ablation theo `L` toi thieu 2-3 cau hinh.
- [ ] P0: latency benchmark.
- [ ] P0: error analysis.
- [ ] P1: baseline comparison neu co san model/log.
- [ ] P1: add dataset impact neu dataset moi da san sang.
- [ ] P2: official Mamba vs pure PyTorch hoac pooling ablation neu du thoi gian.

## Acceptance Criteria

- [ ] Co experiment matrix duoc ca nhom dong y.
- [ ] Moi experiment co owner, input, output metric, deadline.
- [ ] Khong co experiment mo ho hoac qua scope.

## Deliverables

- Experiment matrix table.

## Dependencies

- Issue 01.
- Issue 04.
- Issue 05.

---

### Issue 07 - Benchmark anh huong sequence length `L`

Assignee: Nguyen Phuc Duy  
Reviewer: Mai Hong Thai  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `paper:mamba`, `type:experiment`, `area:model`, `area:evaluation`, `priority:P0`

## Goal

Chung minh/phan tich gia tri cua long-sequence Mamba: khi tang `L`, metric va latency thay doi the nao.

## Tasks

- [ ] Chot cac `L` se chay: uu tien `30`, `512`, `1024`; them `2048`/`4096` neu may cho phep.
- [ ] Tao/kiem tra data artifact ung voi tung `L`.
- [ ] Chay evaluation hoac train/fine-tune neu can cho tung `L`.
- [ ] Ghi lai MAE, RMSE, train time, inference latency, memory/VRAM neu co.
- [ ] Ghi lai command/config/log cho tung `L`.
- [ ] Neu `L` tang nhung metric khong tot hon, phan tich ly do: noise, data it, overfit, label phu thuoc gan hon xa.

## Acceptance Criteria

- [ ] Co bang ablation theo `L`.
- [ ] Co nhan xet ro rang: `L` nao tot nhat va trade-off la gi.
- [ ] Co it nhat 1 chart MAE/RMSE theo `L`.

## Deliverables

- Ablation table.
- Chart theo `L`.
- Short analysis paragraph cho report.

## Dependencies

- Issue 04.
- Issue 05.
- Issue 06.

---

### Issue 08 - Baseline comparison voi LSTM/CNN-LSTM hoac log cu

Assignee: Nguyen Phuc Duy  
Reviewer: Mai Hong Thai  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `type:experiment`, `area:model`, `area:evaluation`, `priority:P1`

## Goal

Tao diem so sanh de ket qua Mamba co y nghia hon, nhung khong de baseline lam tre bai bao.

## Tasks

- [ ] Kiem tra repo/log cu co baseline LSTM/CNN-LSTM khong.
- [ ] Neu co, verify metric va config.
- [ ] Neu khong co, chay baseline nhanh voi cung split neu thoi gian cho phep.
- [ ] Ghi ro baseline dung input `L` nao.
- [ ] So sanh cong bang: cung data split, cung metric.
- [ ] Neu khong chay duoc baseline, ghi vao limitation va dung literature comparison.

## Acceptance Criteria

- [ ] Co baseline result hoac ly do ro vi sao baseline bi loai khoi scope.
- [ ] Neu co baseline, bang result gom Mamba vs baseline.

## Deliverables

- Baseline comparison table.
- Limitation note neu khong co baseline.

## Dependencies

- Issue 05.
- Issue 06.

---

### Issue 09 - Benchmark latency inference cua Mamba

Assignee: Nguyen Nhat Minh  
Reviewer: Nguyen Phuc Duy  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `paper:mamba`, `type:experiment`, `type:demo`, `area:model`, `priority:P0`

## Goal

Chung minh model khong chi chinh xac ma con co kha nang deploy API cho he thong bao tri.

## Tasks

- [ ] Chot input mau dung shape voi model.
- [ ] Do latency inference local tren CPU hoac GPU.
- [ ] Do latency qua FastAPI endpoint neu demo da san sang.
- [ ] Chay nhieu lan, ghi average, median, p95 neu co.
- [ ] Ghi ro batch size, sequence length `L`, hardware.
- [ ] So sanh voi muc tieu `<100ms` neu phu hop.

## Acceptance Criteria

- [ ] Co bang latency.
- [ ] Co command/script do latency.
- [ ] Co ket luan deployability trong report.

## Deliverables

- Latency table.
- API/sample benchmark note.

## Dependencies

- Issue 05.

---

### Issue 10 - Error analysis va bieu do prediction vs ground truth

Assignee: Mai Hong Thai  
Reviewer: Tran Minh Tri  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `type:experiment`, `area:evaluation`, `area:paper`, `priority:P0`

## Goal

Lam phan ket qua co chieu sau: khong chi dua MAE/RMSE ma phan tich model sai o dau, vi sao.

## Tasks

- [ ] Tao chart predicted SOH vs actual SOH.
- [ ] Tao chart residual/error distribution.
- [ ] Tao chart MAE/RMSE theo `L`.
- [ ] Tim top case sai nhieu nhat.
- [ ] Phan tich sai so theo vung SOH cao/thap neu du data.
- [ ] Viet 1-2 doan Discussion ve han che va nguyen nhan.

## Acceptance Criteria

- [ ] Co it nhat 3 bieu do dung duoc trong report.
- [ ] Co error analysis khong chung chung.
- [ ] Co ket luan lien ket voi cau hoi nghien cuu.

## Deliverables

- Figures.
- Error analysis text.

## Dependencies

- Issue 05.
- Issue 07.

---

### Issue 11 - Validate dataset moi neu muon add data

Assignee: Bui Phuoc Thang  
Reviewer: Mai Hong Thai  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `type:experiment`, `area:data`, `priority:P1`

## Goal

Neu nhom muon add dataset, phai chung minh dataset moi sach va khong lam ket qua sai lech do domain shift/leakage.

## Tasks

- [ ] Ghi nguon dataset moi va cach cite.
- [ ] Mapping feature sang voltage/current/temperature/feature hien co.
- [ ] Kiem tra label SOH/RUL co tinh duoc khong.
- [ ] So sanh distribution dataset moi vs dataset cu.
- [ ] Kiem tra missing value/outlier/unit.
- [ ] De xuat cach split sau khi merge.
- [ ] Chi merge/chay train khi pass checklist.

## Acceptance Criteria

- [ ] Co report validate dataset moi.
- [ ] Co quyet dinh: use / not use / use as external test.
- [ ] Neu use, co bang before-after metric.

## Deliverables

- Dataset validation note.
- Before-after table neu co.

## Dependencies

- Issue 04.

---

### Issue 12 - Tong hop result table chinh cho bai bao

Assignee: Mai Hong Thai  
Reviewer: Tran Minh Tri  
Milestone: `W2 - Experiments, Ablation, Analysis`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:evaluation`, `area:paper`, `priority:P0`

## Goal

Chuan hoa toan bo ket qua vao cac bang co the dua thang vao paper.

## Tasks

- [ ] Tao bang main result: model, dataset, `L`, MAE, RMSE, latency.
- [ ] Tao bang ablation `L`.
- [ ] Tao bang baseline comparison neu co.
- [ ] Tao bang environment/config.
- [ ] Kiem tra don vi va so chu so thap phan thong nhat.
- [ ] Viet caption va interpretation cho tung bang.

## Acceptance Criteria

- [ ] Bang ket qua khong mau thuan voi log.
- [ ] Reviewer check duoc nguon cua moi con so.
- [ ] Bang co caption san sang dua vao report.

## Deliverables

- Results tables.
- Captions.

## Dependencies

- Issue 05.
- Issue 07.
- Issue 09.
- Issue 10.

---

### Issue 13 - Viet Methodology section cho Mamba-SOH

Assignee: Nguyen Phuc Duy  
Reviewer: Tran Minh Tri  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:paper`, `area:model`, `priority:P0`

## Goal

Viet phan phuong phap ro rang, co tinh khoa hoc, giai thich pipeline Mamba-SOH tu data den prediction.

## Tasks

- [ ] Mo ta bai toan SOH regression.
- [ ] Mo ta input window `X in R^(L x F)` va feature phu `X_feat` neu dung.
- [ ] Mo ta Mamba block/SSM o muc paper, khong qua code-level.
- [ ] Mo ta pooling/fusion/regression head.
- [ ] Mo ta loss, optimizer, early stopping, seed, gradient accumulation neu dung long sequence.
- [ ] Them diagram architecture.
- [ ] Them bang hyperparameter.

## Acceptance Criteria

- [ ] Section Methodology doc lap, nguoi khong doc code van hieu.
- [ ] Dung thuat ngu khoa hoc nhat quan.
- [ ] Khong noi qua kha nang model neu experiment chua chung minh.

## Deliverables

- Methodology section.

## Dependencies

- Issue 03.
- Issue 04.
- Issue 05.

---

### Issue 14 - Viet Experiments va Results section

Assignee: Mai Hong Thai  
Reviewer: Tran Minh Tri  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:paper`, `area:evaluation`, `priority:P0`

## Goal

Bien ket qua experiment thanh phan bao cao thuyet phuc, co setup, metric, bang, hinh va nhan xet.

## Tasks

- [ ] Viet experiment setup: dataset, split, hardware, metric.
- [ ] Dua bang main result vao report.
- [ ] Dua bang ablation `L` vao report.
- [ ] Dua latency result vao report.
- [ ] Dua charts va error analysis vao report.
- [ ] Tra loi tung research question bang ket qua.
- [ ] Viet limitation: data size, generalization, external validation, compute constraint.

## Acceptance Criteria

- [ ] Results section co bang, hinh, nhan xet.
- [ ] Cac ket luan co bang chung tu experiment.
- [ ] Khong co con so nao khong truy duoc ve log.

## Deliverables

- Experiments section.
- Results/Discussion section.

## Dependencies

- Issue 10.
- Issue 12.

---

### Issue 15 - Viet Introduction, Abstract va Conclusion

Assignee: Tran Minh Tri  
Reviewer: Mai Hong Thai  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:paper`, `priority:P0`

## Goal

Dong goi cau chuyen bai bao: van de pin lithium-ion, kho khan long-sequence, de xuat Mamba, ket qua va y nghia ung dung.

## Tasks

- [ ] Viet Abstract 150-250 tu.
- [ ] Viet Introduction: context, problem, gap, contribution.
- [ ] Viet Contributions dang bullet.
- [ ] Viet Conclusion: ket qua chinh, han che, huong phat trien.
- [ ] Dam bao Abstract khong claim qua ket qua.
- [ ] Dong bo thuat ngu voi Methodology/Results.

## Acceptance Criteria

- [ ] Abstract co problem-method-result-contribution.
- [ ] Introduction neu ro gap va ly do dung Mamba.
- [ ] Conclusion khop voi ket qua thuc nghiem.

## Deliverables

- Abstract.
- Introduction.
- Conclusion.

## Dependencies

- Issue 01.
- Issue 02.
- Issue 12.

---

### Issue 16 - Hoan thien API demo cho Mamba prediction

Assignee: Nguyen Nhat Minh  
Reviewer: Nguyen Phuc Duy  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `type:demo`, `area:model`, `priority:P0`

## Goal

Co demo ngan gon cho thay model Mamba co the duoc goi qua API, phu hop voi he thong bao tri.

## Tasks

- [ ] Kiem tra endpoint predict hien co load model/scaler mot lan khi startup.
- [ ] Tao input JSON mau dung shape voi model.
- [ ] Chay request mau va luu response.
- [ ] Ghi lai SOH prediction, classification neu co, inference_ms.
- [ ] Tao script demo hoac command curl/httpie.
- [ ] Viet huong dan chay local ngan gon.
- [ ] Chuan bi fallback demo neu server loi: screenshot/log/output mau.

## Acceptance Criteria

- [ ] Demo chay duoc tren may nhom.
- [ ] Co input mau va output mau.
- [ ] Co huong dan reproduce trong README/report appendix.

## Deliverables

- Demo command/script.
- Sample request/response.
- Local setup note.

## Dependencies

- Issue 05.
- Issue 09.

---

### Issue 17 - Tao reproducibility package

Assignee: Nguyen Nhat Minh  
Reviewer: Bui Phuoc Thang  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `type:docs`, `area:data`, `area:model`, `priority:P0`

## Goal

Dam bao nguoi khac trong nhom hoac giang vien co the hieu cach chay lai ket qua chinh.

## Tasks

- [ ] Liet ke dependencies/env.
- [ ] Liet ke data artifact can co.
- [ ] Liet ke checkpoint/model artifact can co.
- [ ] Viet command preprocess neu can.
- [ ] Viet command evaluate/reproduce.
- [ ] Viet command run API/demo.
- [ ] Ghi ro output expected.

## Acceptance Criteria

- [ ] Co huong dan reproduce tu dau den cuoi.
- [ ] It nhat 1 thanh vien khac doc va chay/kiem tra duoc.
- [ ] Khong thieu duong dan artifact quan trong.

## Deliverables

- Reproducibility guide.

## Dependencies

- Issue 04.
- Issue 05.
- Issue 16.

---

### Issue 18 - Lam slide thuyet trinh va Q&A checklist

Assignee: Tran Minh Tri  
Reviewer: Nguyen Nhat Minh  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `type:docs`, `type:demo`, `area:paper`, `priority:P0`

## Goal

Chuan bi phan bao ve/thuyet trinh de moi thanh vien nam ro phan minh.

## Tasks

- [ ] Tao slide outline 8-12 slide.
- [ ] Slide 1: Title + team.
- [ ] Slide 2: Problem/Motivation.
- [ ] Slide 3: Dataset.
- [ ] Slide 4: Mamba architecture.
- [ ] Slide 5: Training/evaluation setup.
- [ ] Slide 6: Main results.
- [ ] Slide 7: Ablation `L`.
- [ ] Slide 8: Demo/API.
- [ ] Slide 9: Limitation/Future work.
- [ ] Slide 10: Conclusion.
- [ ] Tao Q&A checklist theo role.

## Acceptance Criteria

- [ ] Slide co flow ro trong 7-10 phut.
- [ ] Moi thanh vien co phan tra loi rieng.
- [ ] Ket qua tren slide khop report.

## Deliverables

- Slide deck.
- Q&A checklist.

## Dependencies

- Issue 12.
- Issue 13.
- Issue 14.
- Issue 16.

---

### Issue 19 - Final review report va consistency check

Assignee: Tran Minh Tri  
Reviewer: Tat ca thanh vien  
Milestone: `W3 - Paper, Slide, Demo`  
Labels: `nckh`, `paper:mamba`, `type:docs`, `area:paper`, `priority:P0`

## Goal

Kiem tra lan cuoi de bai bao khong bi loi logic, thieu citation, sai so lieu hoac mau thuan giua cac section.

## Tasks

- [ ] Check title/abstract/introduction co dung trong tam Mamba khong.
- [ ] Check Related Work co citation day du.
- [ ] Check Methodology khop code/model.
- [ ] Check Dataset khop artifact.
- [ ] Check Results khop log.
- [ ] Check hinh/bang co caption.
- [ ] Check conclusion khong claim qua muc.
- [ ] Check format, grammar, spelling.
- [ ] Check references.

## Acceptance Criteria

- [ ] Tat ca P0 issue da dong.
- [ ] Report co the nop/thuyet trinh.
- [ ] Khong con TODO quan trong.

## Deliverables

- Final report.
- Review checklist signed off.

## Dependencies

- Tat ca issue P0 truoc do.

## 5. Dependency map

```text
Issue 01 Scope
  -> Issue 02 Related Work
  -> Issue 03 Model Architecture
  -> Issue 04 Data Protocol
  -> Issue 06 Experiment Matrix

Issue 04 Data Protocol
  -> Issue 05 Reproduce Mamba
  -> Issue 07 L Ablation
  -> Issue 11 Dataset Add Validation
  -> Issue 17 Reproducibility

Issue 05 Reproduce Mamba
  -> Issue 07 L Ablation
  -> Issue 09 Latency
  -> Issue 10 Error Analysis
  -> Issue 12 Result Tables
  -> Issue 16 API Demo

Issue 12 Result Tables
  -> Issue 14 Experiments/Results
  -> Issue 15 Abstract/Conclusion
  -> Issue 18 Slides

Issue 13 + Issue 14 + Issue 15 + Issue 16
  -> Issue 19 Final Review
```

## 6. De xuat chia viec theo tuan

### Tuan 1

| Thanh vien | Issue chinh | Ket qua cuoi tuan |
|------------|-------------|-------------------|
| Tri | #01, #02 | Scope, RQ, contribution, paper list |
| Duy | #03, #05 | Model architecture note, reproduce metric |
| Thang | #04 | Data protocol, dataset statistics |
| Thai | #06 | Experiment matrix, metric template |
| Minh | Ho tro #05, chuan bi #09/#16 | Input mau/API status |

### Tuan 2

| Thanh vien | Issue chinh | Ket qua cuoi tuan |
|------------|-------------|-------------------|
| Duy | #07, #08 | Ablation `L`, baseline neu co |
| Thang | #11 | Dataset validation neu add data |
| Thai | #10, #12 | Chart, error analysis, result table |
| Minh | #09 | Latency benchmark |
| Tri | Review #10/#12, tiep tuc report | Draft report skeleton |

### Tuan 3

| Thanh vien | Issue chinh | Ket qua cuoi tuan |
|------------|-------------|-------------------|
| Duy | #13 | Methodology Mamba |
| Thai | #14 | Experiments/Results |
| Tri | #15, #18, #19 | Abstract/Intro/Conclusion, slide, final review |
| Minh | #16, #17 | Demo API, reproducibility guide |
| Thang | Review #17, hoan thien Data section | Data section final |

## 7. Minimum viable paper checklist

Neu chi con it thoi gian, day la nhung issue khong duoc bo:

- [ ] #01 Scope bai bao Mamba.
- [ ] #02 Related Work.
- [ ] #03 Model Architecture.
- [ ] #04 Data Protocol.
- [ ] #05 Reproduce Mamba.
- [ ] #07 Ablation `L`.
- [ ] #09 Latency.
- [ ] #10 Error Analysis.
- [ ] #12 Result Tables.
- [ ] #13 Methodology.
- [ ] #14 Experiments/Results.
- [ ] #15 Abstract/Intro/Conclusion.
- [ ] #16 Demo API.
- [ ] #19 Final Review.

## 8. GitHub issue title list

Dung danh sach nay de tao issue nhanh:

1. `[NCKH][P0] Khoa scope bai bao Mamba va dong gop chinh`
2. `[NCKH][P0] Tong hop related work ve Mamba/SSM va SOH battery`
3. `[NCKH][P0] Mo ta architecture MambaSOHPredictor tu code hien co`
4. `[NCKH][P0] Khoa data protocol va chong data leakage`
5. `[NCKH][P0] Reproduce ket qua model Mamba hien co`
6. `[NCKH][P0] Tao bang experiment matrix cho bai bao Mamba`
7. `[NCKH][P0] Benchmark anh huong sequence length L`
8. `[NCKH][P1] Baseline comparison voi LSTM/CNN-LSTM hoac log cu`
9. `[NCKH][P0] Benchmark latency inference cua Mamba`
10. `[NCKH][P0] Error analysis va bieu do prediction vs ground truth`
11. `[NCKH][P1] Validate dataset moi neu muon add data`
12. `[NCKH][P0] Tong hop result table chinh cho bai bao`
13. `[NCKH][P0] Viet Methodology section cho Mamba-SOH`
14. `[NCKH][P0] Viet Experiments va Results section`
15. `[NCKH][P0] Viet Introduction, Abstract va Conclusion`
16. `[NCKH][P0] Hoan thien API demo cho Mamba prediction`
17. `[NCKH][P0] Tao reproducibility package`
18. `[NCKH][P0] Lam slide thuyet trinh va Q&A checklist`
19. `[NCKH][P0] Final review report va consistency check`


Chạy kiểm thử cho ticket hoặc PR được chỉ định.

Ticket/PR: `$ARGUMENTS`

Thực hiện đúng theo `.claude/agents/tester.md`:
1. Xác định scope: BE / FE / Mobile / AI dựa vào ticket `$ARGUMENTS`
2. Chuẩn bị test data (không dùng production data)
3. Chạy test cases: happy path → edge cases → auth/role → error handling
4. Xuất báo cáo:
```
## TEST REPORT — KAN-XX — YYYY-MM-DD
### TÓM TẮT
[1–2 câu về kết quả chung]

### KẾT QUẢ
| Test case | Kết quả | Ghi chú |
|-----------|---------|---------|

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Sau khi có kết quả, lưu vào:
```
logs/KAN-XX/test.md
```
Nếu folder chưa tồn tại → tạo mới.

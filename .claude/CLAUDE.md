# Claude Agent System —GSU26SE55

Hệ thống agent hỗ trợ dự án Capstone **Solar Lithium-ion Battery Maintenance Management System** — nghiên cứu kỹ thuật, theo dõi tiến độ team, và hỗ trợ phát triển phần mềm.

---

## Ngữ cảnh dự án

**Dự án:** Nền tảng AI giám sát và bảo trì pin lithium-ion cho hệ thống năng lượng mặt trời.
**Nhóm:** 5 sinh viên (3 BE + 2 FE) — GVHD: Trương Long
**Timeline:** 8 sprint, từ 11/5/2026 → 6/9/2026

**Hệ thống gồm 3 phần:**
- Mobile App (React Native/Expo) — giám sát pin real-time
- Web App (ReactJS) — quản lý Admin/Manager/Staff + SLA ticket theo ITIL
- AI Module — phân loại trạng thái pin, dự đoán SOH bằng LSTM/CNN-LSTM

> Chi tiết đầy đủ xem tại: [memory.md](memory.md)

---

## Cấu trúc hệ thống

```
.claude/
├── CLAUDE.md              ← file này — bộ não dự án
├── CLAUDE.local.md        ← ghi chú cá nhân, không push lên Git
├── settings.json          ← permissions + hooks (commit được)
├── settings.local.json    ← MCP servers + settings private
├── memory.md              ← thông tin dự án chi tiết
├── rules/                 ← quy tắc — mọi người đều follow
│   ├── workflow.md        ← quy trình làm việc & git flow
│   ├── design.md          ← kiến trúc hệ thống 3-layer
│   └── tech-defaults.md   ← tech stack mặc định
├── agents/                ← sub-agent chuyên dụng (leader dùng)
│   ├── researcher.md      ← thu thập & tổng hợp thông tin
│   ├── reviewer.md        ← kiểm tra chất lượng & khuyến nghị
│   └── tester.md          ← kiểm thử BE/FE/Mobile/AI trước khi merge
└── skills/
    ├── leader/            ← CHỈ LEADER dùng
    │   ├── review-team.md ← /review-team  — tracking toàn team
    │   ├── sprint-plan.md ← /sprint-plan  — lên kế hoạch sprint
    │   └── member-status.md ← /member-status — check từng người
    └── dev/               ← team dev dùng (không dùng leader skills)
        ├── task.md        ← /task KAN-XX       — làm việc trên ticket
        ├── code-review.md ← /code-review       — tự review trước khi ship
        ├── ship.md        ← /ship KAN-XX       — tạo PR + cập nhật Jira
        └── review-pr.md   ← /review-pr KAN-XX  — review PR của đồng đội
```

---

## Phân quyền sử dụng

| | Leader | BE Dev | FE Dev |
|--|--------|--------|--------|
| **rules/** (đọc) | ✅ | ✅ | ✅ |
| `/kltn-task` | ✅ | ✅ | ✅ |
| `/kltn-reviewcode` | ✅ | ✅ | ✅ |
| `/kltn-test` | ✅ | ✅ | ✅ |
| `/kltn-ship` | ✅ | ✅ | ✅ |
| `/kltn-reviewpr` | ✅ | ✅ | ✅ |
| `/kltn-team` | ✅ | ❌ | ❌ |
| `/kltn-sprint` | ✅ | ❌ | ❌ |
| `/kltn-member` | ✅ | ❌ | ❌ |
| **agents/** | ✅ | ❌ | ❌ |

---

## Nguyên tắc hoạt động

- **Rules** — quy tắc bất biến, không ai được bỏ qua khi code
- **Dev skills** — quy trình chuẩn: `/kltn-task` → `/kltn-reviewcode` → `/kltn-test` → `/kltn-ship`
- **Leader skills** — tracking và planning, không can thiệp vào flow coding của dev
- Kết quả review và sprint plan xuất trong conversation — không lưu file ngoài

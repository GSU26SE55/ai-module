"""Classification feedback store (F4) — kỹ thuật viên chấm lại phân loại của AI.

BE đã có sẵn `StaffFeedbackEnum` (Correct / FalsePositive / FalseNegative) và lưu vào
`anomaly_classifications.staff_feedback`, nhưng KHÔNG có đường nào gửi ngược về AI. Nghĩa là
vòng học đóng lại ở phía BE: AI không bao giờ biết mình phân loại sai để mà sửa.

Cố ý KHÔNG dùng ChromaDB như prescription history: ở đó cần truy hồi ngữ nghĩa để lấy ca
tương tự làm few-shot, còn ở đây chỉ cần đếm đúng/sai và giữ bản ghi cho lần retrain sau.
Kéo theo cả chromadb + sentence-transformers cho một việc append 4 trường là đắt vô ích, và
lại thêm một điểm hỏng cho một endpoint đáng ra phải luôn nhận được.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

FEEDBACK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "classification_feedback",
)
FEEDBACK_PATH = os.path.join(FEEDBACK_DIR, "feedback.jsonl")

# Giá trị hợp lệ — khớp StaffFeedbackEnum phía BE (1/2/3). Sai giá trị phải bị TỪ CHỐI chứ
# không ghi bừa: một file retrain lẫn nhãn rác thì tệ hơn hẳn một file thiếu vài dòng.
VALID_VERDICTS = ("correct", "false_positive", "false_negative")
VALID_CLASSIFICATIONS = ("Normal", "Degrading", "Failed")

_lock = threading.Lock()


def record_feedback(
    battery_id: str,
    classification: str,
    verdict: str,
    model_version: str = "",
    classified_at: str = "",
    note: str = "",
) -> dict:
    """Ghi 1 bản ghi feedback, trả về bộ đếm chạy hiện tại.

    Raises:
        ValueError: verdict hoặc classification không hợp lệ — caller map thành
            422 (REST) / INVALID_ARGUMENT (gRPC).
    """
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"verdict phải là một trong {VALID_VERDICTS}, nhận {verdict!r}"
        )
    if classification not in VALID_CLASSIFICATIONS:
        raise ValueError(
            f"classification phải là một trong {VALID_CLASSIFICATIONS}, "
            f"nhận {classification!r}"
        )

    record = {
        "battery_id": battery_id,
        "classification": classification,
        "verdict": verdict,
        "model_version": model_version,
        "classified_at": classified_at,
        "note": note,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Khoá quanh cả ghi lẫn đọc lại: uvicorn chạy nhiều worker/thread, hai lần append
    # xen kẽ có thể cắt ngang dòng của nhau và làm hỏng JSONL vĩnh viễn.
    with _lock:
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return _stats_unlocked()


def stats() -> dict:
    """Bộ đếm precision/recall thô — đủ để biết model đang sai kiểu nào."""
    with _lock:
        return _stats_unlocked()


def _stats_unlocked() -> dict:
    counts = {"correct": 0, "false_positive": 0, "false_negative": 0}
    if not os.path.exists(FEEDBACK_PATH):
        return _with_derived(counts)

    with open(FEEDBACK_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line).get("verdict")
            except json.JSONDecodeError:
                # Một dòng hỏng không được làm chết cả thống kê — bỏ qua và nói ra.
                logger.warning("Bỏ qua dòng feedback hỏng trong %s", FEEDBACK_PATH)
                continue
            if v in counts:
                counts[v] += 1
    return _with_derived(counts)


def _with_derived(counts: dict) -> dict:
    tp = counts["correct"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    # Chỉ tính khi có mẫu: precision=0 lúc chưa có feedback nào sẽ bị đọc nhầm thành
    # "model sai hết", trong khi sự thật là "chưa ai chấm".
    precision = round(tp / (tp + fp), 3) if (tp + fp) else None
    recall = round(tp / (tp + fn), 3) if (tp + fn) else None
    return {
        "total": tp + fp + fn,
        **counts,
        "precision": precision,
        "recall": recall,
    }

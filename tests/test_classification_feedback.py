"""F4 — store phản hồi phân loại: chống hỏng và số liệu suy dẫn.

Trọng tâm là các nhánh mà một lỗi im lặng sẽ làm hỏng quyết định retrain: một dòng hỏng
không được xoá sổ cả thống kê, và "chưa ai chấm" phải phân biệt được với "đã chấm và sai hết".
"""
import pytest

import src.services.classification_feedback as cf


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    # Store là append-only toàn cục — dùng chung giữa các test sẽ khiến bộ đếm rò sang
    # nhau và mọi khẳng định về precision thành vô nghĩa.
    monkeypatch.setattr(cf, "FEEDBACK_DIR", str(tmp_path))
    monkeypatch.setattr(cf, "FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    return tmp_path


class TestStatsResilience:
    def test_stats_on_missing_file_returns_zeros_not_error(self):
        """Chưa có file (deploy mới) phải trả 0, không được ném lỗi.

        Endpoint /health và caller đọc số này ngay từ lần chạy đầu, khi chưa ai chấm gì.
        """
        s = cf.stats()
        assert s["total"] == 0
        assert s["correct"] == s["false_positive"] == s["false_negative"] == 0
        # None, KHÔNG phải 0.0 — 0.0 đọc thành "model sai hết".
        assert s["precision"] is None
        assert s["recall"] is None

    def test_corrupted_line_is_skipped_others_still_counted(self, _isolated_store):
        """Một dòng hỏng KHÔNG được xoá sổ cả thống kê.

        JSONL bị cắt giữa dòng là chuyện có thật khi container bị kill lúc đang ghi. Nếu
        stats ném lỗi ở đó thì toàn bộ dữ liệu retrain thành vô dụng chỉ vì một byte.
        """
        cf.record_feedback("B1", "Failed", "correct")
        with open(cf.FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write('{"verdict": "correct"  <<< dòng bị cắt\n')
        cf.record_feedback("B2", "Normal", "false_positive")

        s = cf.stats()
        assert s["total"] == 2, "hai dòng hợp lệ vẫn phải được đếm"
        assert s["correct"] == 1 and s["false_positive"] == 1

    def test_blank_lines_are_ignored(self, _isolated_store):
        cf.record_feedback("B1", "Failed", "correct")
        with open(cf.FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write("\n   \n")

        assert cf.stats()["total"] == 1


class TestDerivedMetrics:
    def test_precision_none_until_a_positive_prediction_is_judged(self):
        """false_negative không vào mẫu số precision ⇒ precision vẫn chưa tính được."""
        cf.record_feedback("B1", "Normal", "false_negative")
        s = cf.stats()
        assert s["precision"] is None
        assert s["recall"] == 0.0, "recall CÓ mẫu (tp=0, fn=1) nên tính được và bằng 0"

    def test_precision_and_recall_computed_from_counts(self):
        for _ in range(3):
            cf.record_feedback("B1", "Failed", "correct")
        cf.record_feedback("B1", "Failed", "false_positive")
        cf.record_feedback("B1", "Failed", "false_negative")

        s = cf.stats()
        assert s["total"] == 5
        assert s["precision"] == 0.75   # 3 / (3+1)
        assert s["recall"] == 0.75      # 3 / (3+1)


class TestValidation:
    @pytest.mark.parametrize("verdict", ["", "ok", "Correct", "CORRECT", "true"])
    def test_rejects_unknown_verdict(self, verdict):
        # Ghi bừa nhãn lạ làm hỏng file retrain một cách âm thầm — file vẫn đọc được,
        # chỉ là học sai. Từ chối ngay tại cửa.
        with pytest.raises(ValueError, match="verdict"):
            cf.record_feedback("B1", "Failed", verdict)

    @pytest.mark.parametrize("classification", ["", "failed", "Broken", "normal"])
    def test_rejects_unknown_classification(self, classification):
        with pytest.raises(ValueError, match="classification"):
            cf.record_feedback("B1", classification, "correct")

    def test_rejected_record_is_not_written(self, _isolated_store):
        """Bị từ chối thì KHÔNG được để lại dấu vết trong file."""
        with pytest.raises(ValueError):
            cf.record_feedback("B1", "Failed", "nope")
        assert cf.stats()["total"] == 0

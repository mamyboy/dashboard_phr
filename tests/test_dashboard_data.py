import csv
import tempfile
import unittest
from pathlib import Path

from dashboard_data import apply_detail_context, build_province_summary, safe_json_for_script


HEADERS = [
    "rank", "province_code", "province_name", "region_id", "region_name",
    "masks", "encounters", "answered", "citizens", "hospitals", "districts",
    "matched", "unmatched", "match_rate_pct", "share_pct", "first_date_be",
    "last_date_be",
]


class ProvinceSummaryTests(unittest.TestCase):
    def test_builds_latest_target_province_summary_and_benchmarks(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            older = folder / "phr_masks_province_20260803_120000.csv"
            latest = folder / "ระดับจังหวัด" / "phr_masks_province_20260804_155003.csv"
            latest.parent.mkdir()
            rows = [
                [1, "92", "ตรัง", 12, "เขตสุขภาพที่ 12", 480, 480, 120, 128, 66, 9, 480, 0, 100, 2.4, 25611214, 25690706],
                [2, "91", "สตูล", 12, "เขตสุขภาพที่ 12", 120, 120, 17, 52, 14, 5, 120, 0, 100, 0.6, 25620329, 25690720],
                [3, "90", "สงขลา", 12, "เขตสุขภาพที่ 12", 130, 130, 1, 111, 27, 13, 130, 0, 100, 0.65, 25560423, 25690710],
                [4, "31", "บุรีรัมย์", 9, "เขตสุขภาพที่ 9", 1218, 1218, 142, 324, 137, 22, 1208, 10, 99.18, 6.09, 25610226, 25690727],
            ]
            for path, satun_masks in ((older, 119), (latest, 120)):
                with path.open("w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(HEADERS)
                    for row in rows:
                        item = list(row)
                        if item[2] == "สตูล":
                            item[5] = satun_masks
                            item[6] = satun_masks
                        writer.writerow(item)

            summary = build_province_summary(
                folder,
                target_province="สตูล",
                previous_detail={"masks": 118, "citizens": 53, "answered": 17},
            )

            self.assertEqual(summary["snapshot_iso"], "2026-08-04T15:50:03")
            self.assertEqual(summary["snapshot_label"], "4/8/2026 15:50")
            self.assertEqual(summary["province"]["masks"], 120)
            self.assertEqual(summary["province"]["delta_masks"], 2)
            self.assertEqual(summary["province"]["delta_citizens"], -1)
            self.assertAlmostEqual(summary["province"]["answer_rate"], 14.1667, places=3)
            self.assertEqual(summary["province"]["region_rank"], 3)
            self.assertEqual(summary["province"]["region_count"], 3)
            self.assertEqual(summary["province"]["national_count"], 4)

    def test_same_day_detail_uses_previous_day_as_delta_baseline(self):
        summary = {
            "snapshot_iso": "2026-08-04T17:53:52",
            "province": {"masks": 120, "citizens": 52, "answered": 17},
        }
        result = apply_detail_context(
            summary,
            detail_dates=["20260803", "20260804"],
            detail_labels=["3/8/2026", "4/8/2026"],
            masks=[118, 120],
            citizens=[53, 52],
            answered=[17, 17],
        )
        self.assertTrue(result["detail_aligned"])
        self.assertEqual(result["baseline_label"], "3/8/2026")
        self.assertEqual(result["province"]["delta_masks"], 2)
        self.assertEqual(result["province"]["delta_citizens"], -1)
        self.assertEqual(result["province"]["delta_answered"], 0)
        self.assertEqual(result["detail_totals"]["citizens"], 52)
        self.assertEqual(result["detail_gap"]["citizens"], 0)

    def test_safe_json_prevents_closing_script_tag(self):
        rendered = safe_json_for_script({"name": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script>", rendered.lower())
        self.assertIn("\\u003c/script\\u003e", rendered.lower())


if __name__ == "__main__":
    unittest.main()

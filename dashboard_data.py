"""Pure data helpers for the PHR Masks dashboard generator."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional


INT_FIELDS = {
    "rank",
    "masks",
    "encounters",
    "answered",
    "citizens",
    "hospitals",
    "districts",
    "matched",
    "unmatched",
    "status_pending",
    "status_in_progress",
    "status_completed",
    "status_no_error_found",
    "status_not_recorded",
    "action_none_yet",
    "action_data_corrected",
    "action_other",
    "action_not_recorded",
}
FLOAT_FIELDS = {"match_rate_pct", "share_pct"}

STATUS_LABELS = {
    "status_pending": "รอตรวจสอบ",
    "status_in_progress": "อยู่ระหว่างตรวจสอบ",
    "status_completed": "ตรวจเสร็จสิ้น",
    "status_no_error_found": "ไม่พบข้อผิดพลาด",
    "status_not_recorded": "ยังไม่บันทึก",
}

ACTION_LABELS = {
    "action_none_yet": "ยังไม่ดำเนินการ",
    "action_data_corrected": "แก้ไขข้อมูลแล้ว",
    "action_other": "ดำเนินการอื่นๆ",
    "action_not_recorded": "ยังไม่บันทึก",
}


def safe_json_for_script(value: Any) -> str:
    """Serialize JSON so source data cannot terminate an inline script element."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _snapshot_datetime(path: Path) -> datetime:
    match = re.search(r"(\d{8})_(\d{6})", path.name)
    if not match:
        raise ValueError(f"Invalid province snapshot filename: {path.name}")
    return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")


def _number(value: Optional[str], *, integer: bool) -> Any:
    text = (value or "").strip()
    if not text:
        return 0 if integer else 0.0
    return int(float(text)) if integer else float(text)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in INT_FIELDS:
            row[field] = _number(row.get(field), integer=True)
        for field in FLOAT_FIELDS:
            row[field] = _number(row.get(field), integer=False)
    return rows


def apply_detail_context(
    summary: Optional[dict[str, Any]],
    *,
    detail_dates: list[str],
    detail_labels: list[str],
    masks: list[int],
    citizens: list[int],
    answered: list[int],
) -> Optional[dict[str, Any]]:
    """Attach coverage metadata and compare the province snapshot with the prior day."""
    if summary is None or not detail_dates:
        return summary
    snapshot_date = summary["snapshot_iso"][:10].replace("-", "")
    aligned = detail_dates[-1] == snapshot_date
    baseline_index = -2 if aligned and len(detail_dates) > 1 else -1
    province = summary["province"]
    province["delta_masks"] = province["masks"] - masks[baseline_index]
    province["delta_citizens"] = province["citizens"] - citizens[baseline_index]
    province["delta_answered"] = province["answered"] - answered[baseline_index]
    summary["detail_aligned"] = aligned
    summary["detail_latest_label"] = detail_labels[-1]
    summary["baseline_label"] = detail_labels[baseline_index]
    summary["detail_totals"] = {
        "masks": masks[-1], "citizens": citizens[-1], "answered": answered[-1]
    }
    summary["detail_gap"] = {
        "masks": province["masks"] - masks[-1],
        "citizens": province["citizens"] - citizens[-1],
        "answered": province["answered"] - answered[-1],
    }
    return summary


def build_province_summary(
    folder: Path | str,
    *,
    target_province: str,
    previous_detail: Optional[Mapping[str, int]] = None,
) -> Optional[dict[str, Any]]:
    """Build latest province/region/national context for one target province."""
    folder = Path(folder)
    files = sorted(folder.rglob("phr_masks_province_*.csv"), key=_snapshot_datetime)
    if not files:
        return None

    latest = files[-1]
    snapshot = _snapshot_datetime(latest)
    rows = _load_rows(latest)
    province = next((row for row in rows if row.get("province_name") == target_province), None)
    if province is None:
        raise ValueError(f"Province {target_province!r} not found in {latest}")

    valid = [row for row in rows if str(row.get("province_code", "")) != "00"]
    region = [row for row in valid if row.get("region_id") == province.get("region_id")]
    region_sorted = sorted(region, key=lambda row: row["masks"], reverse=True)

    masks = province["masks"]
    citizens = province["citizens"]
    answered = province["answered"]
    province["answer_rate"] = 100 * answered / masks if masks else 0.0
    province["cases_per_citizen"] = masks / citizens if citizens else 0.0
    province["region_rank"] = region_sorted.index(province) + 1
    province["region_count"] = len(region)
    province["national_count"] = len(valid)

    previous = dict(previous_detail or {})
    province["delta_masks"] = masks - previous.get("masks", masks)
    province["delta_citizens"] = citizens - previous.get("citizens", citizens)
    province["delta_answered"] = answered - previous.get("answered", answered)

    region_masks = sum(row["masks"] for row in region)
    region_answered = sum(row["answered"] for row in region)
    national_masks = sum(row["masks"] for row in valid)
    national_answered = sum(row["answered"] for row in valid)

    return {
        "source_file": latest.name,
        "snapshot_iso": snapshot.isoformat(),
        "snapshot_label": f"{snapshot.day}/{snapshot.month}/{snapshot.year} {snapshot:%H:%M}",
        "province": province,
        "region": {
            "id": province.get("region_id"),
            "name": province.get("region_name"),
            "masks": region_masks,
            "answer_rate": round(100 * region_answered / region_masks, 2) if region_masks else 0.0,
            "province_share_pct": round(100 * masks / region_masks, 2) if region_masks else 0.0,
        },
        "national": {
            "masks": national_masks,
            "answer_rate": round(100 * national_answered / national_masks, 2) if national_masks else 0.0,
        },
    }

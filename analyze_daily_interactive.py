# -*- coding: utf-8 -*-
"""Build a self-contained interactive PHR Masks dashboard with Chart.js."""
import csv, glob, re, os, json
from dashboard_data import apply_detail_context, build_province_summary, safe_json_for_script

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.environ.get("PHR_CSV_DIR", os.path.join(BASE_DIR, "csv"))
FILES = sorted(glob.glob(os.path.join(FOLDER, "phr_masks_hospital_*.csv")))
if not FILES:
    raise FileNotFoundError(
        f"No PHR CSV snapshots found in {FOLDER!r}. "
        "Set PHR_CSV_DIR or place files under ./csv/."
    )

def parse_dt(fn):
    m = re.search(r"(\d{8})_(\d{6})", os.path.basename(fn))
    d, t = m.group(1), m.group(2)
    label = f"{int(d[6:8])}/{int(d[4:6])}/{d[:4]}"
    return label, d, t

# dedupe: วันเดียวกันเก็บเฉพาะ snapshot ล่าสุด
latest = {}
for fn in FILES:
    label, d, t = parse_dt(fn)
    if d not in latest or t > latest[d][1]:
        latest[d] = (fn, t, label)
days_raw = sorted(latest.values(), key=lambda x: x[0])  # sort by date+time

def opt(v):
    v = (v or "").strip()
    return int(v) if v not in ("", None) else None

days = []
province_name = None
for fn, t, label in days_raw:
    data = {}
    with open(fn, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            province_name = province_name or (row.get("province_name") or "").strip()
            code = row["hospital_code"].strip()
            name = re.sub(r"\s*อ\.[ก-์]+\s*จ\.[ก-์]+\s*$", "", row["hospital_name"]).strip()
            data[code] = dict(
                masks=int(row["masks"]),
                cit=opt(row.get("citizens")),
                enc=opt(row.get("encounters")),
                ans=opt(row.get("answered")),
                status_pending=opt(row.get("status_pending")),
                status_in_progress=opt(row.get("status_in_progress")),
                status_completed=opt(row.get("status_completed")),
                status_no_error_found=opt(row.get("status_no_error_found")),
                status_not_recorded=opt(row.get("status_not_recorded")),
                action_none_yet=opt(row.get("action_none_yet")),
                action_data_corrected=opt(row.get("action_data_corrected")),
                action_other=opt(row.get("action_other")),
                action_not_recorded=opt(row.get("action_not_recorded")),
                name=name, dist=row["district_name"].strip(), time=t)
    days.append(dict(label=label, sortkey=d, time=t, data=data))
labels = [d["label"] for d in days]
L = len(days)

canon = {}
for d in days:
    for code, v in d["data"].items():
        canon[code] = v
all_codes = list(canon.keys())
districts = sorted({v["dist"] for v in canon.values()})

unit_recs = []
for code in all_codes:
    masks = [d["data"].get(code, {}).get("masks", 0) for d in days]
    cit = [d["data"].get(code, {}).get("cit", 0) for d in days]
    enc = [d["data"].get(code, {}).get("enc", 0) or 0 for d in days]
    ans = [d["data"].get(code, {}).get("ans", 0) or 0 for d in days]
    # status/action fields per day (array like masks/cit/enc/ans)
    status_pending = [d["data"].get(code, {}).get("status_pending", 0) or 0 for d in days]
    status_in_progress = [d["data"].get(code, {}).get("status_in_progress", 0) or 0 for d in days]
    status_completed = [d["data"].get(code, {}).get("status_completed", 0) or 0 for d in days]
    status_no_error_found = [d["data"].get(code, {}).get("status_no_error_found", 0) or 0 for d in days]
    status_not_recorded = [d["data"].get(code, {}).get("status_not_recorded", 0) or 0 for d in days]
    action_none_yet = [d["data"].get(code, {}).get("action_none_yet", 0) or 0 for d in days]
    action_data_corrected = [d["data"].get(code, {}).get("action_data_corrected", 0) or 0 for d in days]
    action_other = [d["data"].get(code, {}).get("action_other", 0) or 0 for d in days]
    action_not_recorded = [d["data"].get(code, {}).get("action_not_recorded", 0) or 0 for d in days]
    unit_recs.append(dict(code=code, name=canon[code]["name"], dist=canon[code]["dist"],
                          masks=masks, cit=cit, enc=enc, ans=ans, last=canon[code]["masks"],
                          status_pending=status_pending,
                          status_in_progress=status_in_progress,
                          status_completed=status_completed,
                          status_no_error_found=status_no_error_found,
                          status_not_recorded=status_not_recorded,
                          action_none_yet=action_none_yet,
                          action_data_corrected=action_data_corrected,
                          action_other=action_other,
                          action_not_recorded=action_not_recorded))
# sort by last masks desc
unit_recs.sort(key=lambda u: -u["last"])

# daily answered totals (new metric)
tot_enc = [sum(u["enc"][i] for u in unit_recs) for i in range(L)]
tot_ans = [sum(u["ans"][i] for u in unit_recs) for i in range(L)]

# district per day (global)
dist_day = {dt: {d: 0 for d in districts} for dt in labels}
for di, d in enumerate(days):
    for code, v in d["data"].items():
        dist_day[labels[di]][v["dist"]] += v["masks"]

# global totals
tot_masks = [sum(u["masks"][i] for u in unit_recs) for i in range(L)]
tot_cit = [sum(u["cit"][i] for u in unit_recs) for i in range(L)]

DATA = dict(labels=labels, detailTimes=[d["time"] for d in days], districts=districts, units=unit_recs,
            distDay=dist_day, totMasks=tot_masks, totCit=tot_cit,
            totEnc=tot_enc, totAns=tot_ans,
            nUnitsAll=len(unit_recs))

PROVINCE_SUMMARY = build_province_summary(
    FOLDER,
    target_province=province_name or os.environ.get("PHR_PROVINCE_NAME", "สตูล"),
    previous_detail={"masks": tot_masks[-1], "citizens": tot_cit[-1], "answered": tot_ans[-1]},
)
PROVINCE_SUMMARY = apply_detail_context(
    PROVINCE_SUMMARY,
    detail_dates=[d["sortkey"] for d in days],
    detail_labels=labels,
    masks=tot_masks,
    citizens=tot_cit,
    answered=tot_ans,
)
if PROVINCE_SUMMARY:
    PROVINCE_SUMMARY["detail_latest_time"] = f"{days[-1]['time'][:2]}:{days[-1]['time'][2:4]}"

data_js = "const DATA = " + safe_json_for_script(DATA) + ";"
province_js = "const PROVINCE = " + safe_json_for_script(PROVINCE_SUMMARY) + ";"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="th" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>วิเคราะห์รายวัน PHR Masks (Interactive)</title>
<style>
  :root{--bg:#eef2f7;--card:#ffffff;--card2:#f8fafc;--line:#dbe3ec;--txt:#1e293b;--mut:#64748b;--accent:#2563eb;--green:#16a34a;--red:#dc2626;--amber:#d97706;
        --shadow-s:0 1px 2px rgba(15,23,42,.06);
        --shadow-m:0 3px 10px rgba(15,23,42,.07);
        --shadow-l:0 12px 28px rgba(15,23,42,.10);
        --radius:14px;--gap:14px;}
  [data-theme="dark"]{--bg:#0b1626;--card:#14233a;--card2:#0f1d30;--line:#283f5e;--txt:#eaf2fb;--mut:#9bb3cc;--accent:#5fa8ff;--green:#34d399;--red:#f87171;--amber:#fbbf24;
        --shadow-s:0 1px 2px rgba(0,0,0,.3);--shadow-m:0 4px 12px rgba(0,0,0,.32);--shadow-l:0 14px 30px rgba(0,0,0,.4);}
  *{box-sizing:border-box}
  body{margin:0;background:
      radial-gradient(1000px 640px at 88% -8%, rgba(37,99,235,.09), transparent 55%),
      radial-gradient(820px 560px at -5% 108%, rgba(22,163,74,.07), transparent 55%),
      var(--bg);
    color:var(--txt);font-family:'Sarabun','Helvetica Neue',Arial,sans-serif;padding:24px 20px;line-height:1.55;transition:background .3s,color .3s;max-width:100%;margin:0 auto;overflow-x:hidden}
  h1{font-size:21px;margin:0 0 4px;color:var(--txt);letter-spacing:.2px;font-weight:800} .sub{color:var(--mut);font-size:12.5px;margin-bottom:14px}
  .topbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin-bottom:14px}
  .grid{display:grid;gap:var(--gap)} .kpis{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));margin-bottom:var(--gap)}
  .kpi{position:relative;background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:var(--radius);padding:16px 16px;box-shadow:var(--shadow-m);overflow:hidden;transition:transform .2s,box-shadow .2s}
  .kpi::before{content:'';position:absolute;inset:0 0 auto 0;height:4px;background:var(--kpi-accent,linear-gradient(90deg,var(--accent),var(--green)));opacity:.15;transition:opacity .2s}
  .kpi:hover{transform:translateY(-4px);box-shadow:var(--shadow-l)}
  .kpi:hover::before{opacity:1}
  .kpi .v{font-size:28px;font-weight:850;line-height:1.05} 
  .kpi .l{font-size:13px;color:var(--mut);margin-top:6px;line-height:1.4}
  .kpi .v.g{color:var(--green)} .kpi .v.a{color:var(--accent)} .kpi .v.am{color:var(--amber)} .kpi .v.r{color:var(--red)}
  .kpi-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
  .kico{flex-shrink:0;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border-radius:8px;background:var(--kpi-icon-bg,rgba(37,99,235,.12))}
  .kico svg{width:18px;height:18px;stroke:var(--kpi-icon-color,var(--accent))}
  .kmini{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}

  /* KPI Color Variants */
  .kpi.masks{--kpi-accent:linear-gradient(90deg,#635bff,#0a72ef);--kpi-icon-bg:rgba(99,91,255,.15);--kpi-icon-color:#635bff}
  .kpi.delta{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a}
  .kpi.growth{--kpi-accent:linear-gradient(90deg,#2563eb,#635bff);--kpi-icon-bg:rgba(37,99,235,.15);--kpi-icon-color:#2563eb}
  .kpi.units{--kpi-accent:linear-gradient(90deg,#0a72ef,#12b76a);--kpi-icon-bg:rgba(10,114,239,.15);--kpi-icon-color:#0a72ef}
  .kpi.ratio{--kpi-accent:linear-gradient(90deg,#f79009,#fbbf24);--kpi-icon-bg:rgba(217,119,6,.15);--kpi-icon-color:#f79009}
  .kpi.quality{--kpi-accent:linear-gradient(90deg,#635bff,#0a72ef);--kpi-icon-bg:rgba(99,91,255,.15);--kpi-icon-color:#635bff}
  .kpi.completed{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a}
  .kpi.pending{--kpi-accent:linear-gradient(90deg,#f79009,#fbbf24);--kpi-icon-bg:rgba(217,119,6,.15);--kpi-icon-color:#f79009}
  .kpi.action{--kpi-accent:linear-gradient(90deg,#dc2626,#f87171);--kpi-icon-bg:rgba(220,38,38,.15);--kpi-icon-color:#dc2626}
  .kpi.answered{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a}
  .kpi.newcase{--kpi-accent:linear-gradient(90deg,#2563eb,#635bff);--kpi-icon-bg:rgba(37,99,235,.15);--kpi-icon-color:#2563eb}
  .kpi.completion{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a}
  .kpi.topdistrict{--kpi-accent:linear-gradient(90deg,#9b51e0,#635bff);--kpi-icon-bg:rgba(155,81,224,.15);--kpi-icon-color:#9b51e0}
  .kpi.alert{--kpi-accent:linear-gradient(90deg,#dc2626,#f87171);--kpi-icon-bg:rgba(220,38,38,.15);--kpi-icon-color:#dc2626}
  .card{background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:var(--radius);padding:16px 16px 14px;margin-bottom:var(--gap);box-shadow:var(--shadow-m);animation:fade .45s ease;transition:transform .2s,box-shadow .2s}
  .card:hover{box-shadow:var(--shadow-l)}
  @keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  .card h2{font-size:14px;margin:0 0 12px;color:var(--txt);border-left:4px solid var(--accent);padding-left:10px;font-weight:700;letter-spacing:.2px}
  .card h2.g{border-color:var(--green)} .card h2.am{border-color:var(--amber)} .card h2.p{border-color:#9333ea}
  .chartbox{margin-top:4px} .chartbox svg{display:block;width:100%;height:auto}
  .row{grid-template-columns:1fr 1fr} @media(max-width:900px){.row{grid-template-columns:1fr}}
  .legend{font-size:12px;color:var(--mut);margin-top:16px;padding-top:12px;border-top:1px dashed var(--line);display:flex;gap:16px;flex-wrap:wrap}
  .legend span::before{content:'';display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:middle}
  table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--mut);font-weight:600;background:var(--card2);cursor:pointer;user-select:none;position:sticky;top:0}
  th:hover{color:var(--accent)} th .arr{font-size:9px;opacity:.7}
  tbody tr{transition:background .15s} tbody tr:hover{background:rgba(37,99,235,.06)}
  td.num{text-align:center;font-variant-numeric:tabular-nums}
  td.strong{font-weight:700} .mut{color:var(--mut)}
  .c-up{color:var(--green);font-weight:700} .c-down{color:var(--red);font-weight:700}
  .c-flat{color:var(--mut)} .c-new{color:var(--amber);font-weight:700} .c-base{color:var(--mut);font-weight:600}
  .insight{background:var(--card2);border:1px solid var(--line);border-left:4px solid var(--amber);border-radius:12px;padding:14px 16px;font-size:13px;color:var(--txt);margin-bottom:12px;box-shadow:var(--shadow-s)}
  .insight b{color:var(--amber)} .insight.g b{color:var(--green)} .insight.a b{color:var(--accent)}
  .scroll{max-height:440px;overflow:auto;border-radius:12px;max-width:100%;overscroll-behavior-inline:contain;-webkit-overflow-scrolling:touch}
  .controls{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:14px}
#dayChips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;max-width:100%;overflow-x:auto;overscroll-behavior-inline:contain;padding:2px 2px 6px;scrollbar-width:none}#dayChips::-webkit-scrollbar{display:none}
  .pill{background:var(--card);border:1px solid var(--line);color:var(--txt);padding:7px 15px;border-radius:30px;font-size:12.5px;cursor:pointer;transition:.18s;box-shadow:var(--shadow-s)}
  .pill:hover{transform:translateY(-2px);border-color:var(--accent);box-shadow:var(--shadow-m)}
  .pill.on{background:linear-gradient(135deg,var(--accent),var(--green));color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(37,99,235,.35)}
  .chip{background:var(--card);border:1px solid var(--line);color:var(--mut);padding:6px 13px;border-radius:10px;font-size:12px;cursor:pointer;transition:.18s;box-shadow:var(--shadow-s)}
  .chip:hover{transform:translateY(-2px);border-color:var(--green)}
  .chip.on{background:linear-gradient(135deg,var(--green),#22c55e);color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(22,163,74,.3)}
  .search{background:var(--card);border:1px solid var(--line);color:var(--txt);padding:8px 14px;border-radius:10px;font-size:12.5px;min-width:220px;outline:none;transition:.18s;box-shadow:var(--shadow-s)}
  .search:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,.15)}
  .btn{background:var(--card);border:1px solid var(--line);color:var(--txt);padding:8px 16px;border-radius:10px;font-size:12.5px;cursor:pointer;transition:.18s;box-shadow:var(--shadow-s)}
  .btn:hover{transform:translateY(-2px);border-color:var(--accent);box-shadow:var(--shadow-m)}
  #tip{position:fixed;pointer-events:none;background:#0f172a;color:#fff;padding:7px 11px;border-radius:8px;font-size:12px;opacity:0;transition:opacity .12s;z-index:99;box-shadow:0 8px 24px rgba(0,0,0,.4);max-width:240px}
  .tag{display:inline-block;font-size:11px;padding:2px 9px;border-radius:20px;background:linear-gradient(135deg,rgba(22,163,74,.18),rgba(37,99,235,.18));color:var(--green);margin-left:8px;font-weight:600}
  .chartbox{margin-top:6px}
  .dsumwrap{margin-top:16px;padding-top:14px;border-top:1px dashed var(--line)}
  .dsumwrap table{font-size:12.5px}
  .dsumwrap th,.dsumwrap td{padding:8px 10px}
  .rep-day{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}
  .rep-head{font-size:14px;font-weight:700;color:var(--accent);margin-bottom:10px}
  .rep-sec{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px}
  .rep-badge{font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px}
  .rep-badge.c-up{background:rgba(22,163,74,.15);color:var(--green)}
  .rep-badge.c-new{background:rgba(217,119,6,.15);color:var(--amber)}
  .rep-badge.c-down{background:rgba(220,38,38,.15);color:var(--red)}
  .rep-item{font-size:12.5px;background:var(--card);border:1px solid var(--line);padding:3px 10px;border-radius:8px;color:var(--txt)}
  .rep-item b{font-weight:800}
  .rep-empty{font-size:12.5px;color:var(--mut);font-style:italic}

  /* Status/Action badges for unit table */
  .badge{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;line-height:1.4;white-space:nowrap}
  .badge-status{background:rgba(99,91,255,.15);color:#635bff;margin:1px}
  .badge-action{background:rgba(18,183,106,.15);color:#12b76a;margin:1px}
  .status-cell,.action-cell{white-space:nowrap;min-width:120px}
  .status-cell .badge,.action-cell .badge{vertical-align:middle}

  /* Clinical Aurora Light — Stripe depth × Vercel precision */
  :root{--bg:#f6f8fc;--card:#fff;--card2:#f8faff;--line:#e6eaf2;--txt:#101828;--mut:#667085;
    --accent:#635bff;--accent2:#0a72ef;--green:#12b76a;--red:#f04438;--amber:#f79009;
    --shadow-s:0 0 0 1px rgba(16,24,40,.055),0 1px 2px rgba(16,24,40,.035);
    --shadow-m:0 0 0 1px rgba(16,24,40,.06),0 2px 5px rgba(16,24,40,.04),0 12px 28px -22px rgba(50,50,93,.25);
    --shadow-l:0 0 0 1px rgba(99,91,255,.13),0 18px 38px -24px rgba(50,50,93,.32);
    --radius:12px;--gap:14px}
  html{color-scheme:light;background:#f6f8fc}
  body{max-width:100%;padding:20px 18px 36px;background:
    radial-gradient(720px 260px at 8% -4%,rgba(99,91,255,.12),transparent 66%),
    radial-gradient(620px 240px at 92% 0%,rgba(10,114,239,.09),transparent 68%),
    linear-gradient(180deg,#fbfcff 0,#f6f8fc 310px);font-family:-apple-system,BlinkMacSystemFont,'Noto Sans Thai','Leelawadee UI','Segoe UI',sans-serif;letter-spacing:-.01em}
  .hero{position:relative;display:flex;align-items:flex-end;justify-content:space-between;gap:20px;padding:20px 22px 18px;margin-bottom:12px;background:rgba(255,255,255,.82);backdrop-filter:blur(16px);border-radius:14px;box-shadow:var(--shadow-m);overflow:hidden}
  .hero::before{content:'';position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#635bff,#0a72ef 48%,#12b76a)}
  .eyebrow{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}
  h1{font-size:23px;line-height:1.18;letter-spacing:-.035em;font-weight:650;margin:0;color:#101828}
  .sub{font-size:12px;margin:6px 0 0;color:var(--mut)}
  .live-status{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;padding:7px 10px;border-radius:999px;background:#ecfdf3;color:#027a48;font-size:11px;font-weight:650;box-shadow:inset 0 0 0 1px #abefc6}
  .live-dot{width:7px;height:7px;border-radius:50%;background:#12b76a;box-shadow:0 0 0 4px rgba(18,183,106,.12);animation:pulse 2.2s ease-in-out infinite}
  @keyframes pulse{50%{box-shadow:0 0 0 7px rgba(18,183,106,0)}}
  .filterbar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 12px;margin-bottom:14px;background:rgba(255,255,255,.88);border-radius:12px;box-shadow:var(--shadow-s)}
  .filterbar .controls{margin:0}
  .filter-label{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:650;color:#475467}
  .light-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 9px;border-radius:8px;background:#fff7ed;color:#b54708;font-size:11px;font-weight:650;box-shadow:inset 0 0 0 1px #fedf89}
  .kpis{grid-template-columns:repeat(6,minmax(0,1fr))}
  .kpi{min-height:92px;padding:13px 14px;background:#fff;border:0;border-radius:11px;box-shadow:var(--shadow-m)}
  .kpi::before{height:2px;opacity:1;background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .kpi:hover{transform:translateY(-2px);box-shadow:var(--shadow-l)}
  .kpi .v{font-size:25px;font-weight:650;letter-spacing:-.04em;font-variant-numeric:tabular-nums;color:#101828}
  .kpi .l{font-size:10.5px;line-height:1.35;color:#667085}
  .card{background:#fff;border:0;border-radius:12px;padding:15px;margin-bottom:var(--gap);box-shadow:var(--shadow-m);animation:fade .32s ease}
  .card:hover{box-shadow:var(--shadow-l)}
  .card h2{display:flex;align-items:center;min-height:23px;font-size:13px;font-weight:650;letter-spacing:-.012em;margin:0 0 11px;padding:0 0 10px;border-left:0;border-bottom:1px solid #eef1f6;color:#1d2939}
  .card h2::after{content:'';width:5px;height:5px;margin-left:auto;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(99,91,255,.08)}
  .card h2.g::after{background:var(--green);box-shadow:0 0 0 4px rgba(18,183,106,.08)}
  .card h2.am::after{background:var(--amber);box-shadow:0 0 0 4px rgba(247,144,9,.08)}
  .card h2.p::after{background:#9b51e0;box-shadow:0 0 0 4px rgba(155,81,224,.08)}
  .chartbox{margin-top:2px;padding:2px 0}.chartbox svg{filter:none!important}
  .legend{margin-top:10px;padding-top:9px;gap:12px;font-size:10.5px;border-top:1px solid #eef1f6}
  .pill,.chip,.btn,.search{border:0;box-shadow:inset 0 0 0 1px #e4e7ec,0 1px 2px rgba(16,24,40,.03);background:#fff}
  .pill{padding:6px 10px;border-radius:7px;font-size:11px}.chip{padding:6px 9px;border-radius:7px;font-size:11px}
  .pill:hover,.chip:hover{transform:none;box-shadow:inset 0 0 0 1px #b9b5ff,0 2px 5px rgba(99,91,255,.08)}
  .pill.on,.chip.on{background:#635bff;color:#fff;box-shadow:0 1px 2px rgba(50,50,93,.12),0 5px 12px -7px rgba(99,91,255,.6)}
  .search{height:34px;border-radius:8px;font-size:11.5px}.search:focus{box-shadow:0 0 0 3px rgba(99,91,255,.14),inset 0 0 0 1px #635bff}
  table{font-size:11.5px}th,td{padding:8px 9px;border-bottom:1px solid #eef1f6}th{background:#f9fafb;color:#667085;font-size:10.5px;font-weight:650}
  tbody tr:hover{background:#f8f7ff}
  .scroll{border-radius:9px;box-shadow:inset 0 0 0 1px #eef1f6}
  .insight{margin-bottom:8px;border:0;border-left:3px solid var(--amber);border-radius:8px;padding:10px 12px;background:#fffbeb;box-shadow:inset 0 0 0 1px #fef0c7;font-size:11.5px}
  .insight.a{background:#f5f3ff;border-left-color:var(--accent);box-shadow:inset 0 0 0 1px #e9e7ff}.insight.g{background:#ecfdf3;border-left-color:var(--green);box-shadow:inset 0 0 0 1px #d1fadf}
  .rep-day{background:#fafbfc;border:0;border-radius:9px;padding:11px 12px;box-shadow:inset 0 0 0 1px #eaecf0}
  .rep-item{border:0;border-radius:6px;box-shadow:inset 0 0 0 1px #eaecf0;background:#fff;font-size:11px}
  .tag{padding:3px 7px;border-radius:5px;background:#f1f0ff;color:#5925dc;font-size:9px;vertical-align:middle}
  #tip{border-radius:7px;background:#101828;box-shadow:0 10px 25px rgba(16,24,40,.18)}
  :focus-visible{outline:2px solid #1570ef;outline-offset:2px}
  @media(max-width:980px){.kpis{grid-template-columns:repeat(3,1fr)}}
  @media(max-width:640px){body{padding:12px}.hero{align-items:flex-start;flex-direction:column;padding:17px}.kpis{grid-template-columns:repeat(2,1fr)}.row{grid-template-columns:1fr}.live-status{align-self:flex-start}h1{font-size:20px}}
  @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}

  /* Playful Health Bento Light — Figma × Airtable × Clay */
  :root{--bg:#faf9f5;--card:#fff;--card2:#fbfaf7;--line:#e8e2d8;--txt:#171720;--mut:#6f6b65;
    --accent:#6246ea;--accent2:#246bfd;--green:#078a52;--red:#e84d5b;--amber:#d98b00;
    --shadow-s:0 1px 2px rgba(31,27,20,.06),inset 0 -1px 0 rgba(31,27,20,.03);
    --shadow-m:0 1px 2px rgba(31,27,20,.06),0 9px 24px -19px rgba(50,35,100,.28),inset 0 1px 0 rgba(255,255,255,.75);
    --shadow-l:0 2px 3px rgba(31,27,20,.08),0 18px 36px -24px rgba(67,8,159,.34);--radius:18px;--gap:15px}
  html{background:#faf9f5}
  body{max-width:100%;padding:18px 18px 40px;background:
    radial-gradient(540px 360px at 1% 2%,rgba(193,176,255,.22),transparent 70%),
    radial-gradient(520px 360px at 99% 4%,rgba(59,211,253,.16),transparent 70%),#faf9f5;
    font-family:-apple-system,BlinkMacSystemFont,'Noto Sans Thai','Leelawadee UI','Segoe UI',sans-serif;color:var(--txt)}
  .hero{min-height:168px;align-items:center;padding:24px 28px;margin-bottom:14px;background:
    radial-gradient(circle at 12% 14%,rgba(255,255,255,.7) 0 2px,transparent 3px),
    linear-gradient(115deg,#e7ddff 0%,#d4f3ff 42%,#dcf8cc 74%,#fff0ba 100%);
    border:1px solid rgba(23,23,32,.12);border-radius:26px;box-shadow:0 3px 0 rgba(23,23,32,.10),0 18px 36px -28px rgba(67,8,159,.4)}
  .hero::before{display:none}.hero-copy{position:relative;z-index:2;max-width:620px}.eyebrow{display:inline-flex;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.72);color:#43089f;border:1px solid rgba(67,8,159,.14);font-size:9px;letter-spacing:.14em}
  h1{font-size:30px;line-height:1.08;letter-spacing:-.045em;font-weight:750;color:#171720;margin-top:9px}.sub{max-width:560px;font-size:12.5px;line-height:1.55;color:#55515c;margin-top:8px}
  .hero-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:13px}.live-status{padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.82);border:1px solid rgba(7,138,82,.22);box-shadow:none}
  .hero-art{position:relative;z-index:1;width:310px;min-width:280px;align-self:stretch;display:flex;align-items:center;justify-content:center}.hero-art svg{width:100%;height:150px;overflow:visible;filter:drop-shadow(0 12px 16px rgba(67,8,159,.14))}
  .float-a{animation:floatA 4.5s ease-in-out infinite}.float-b{animation:floatB 5.2s ease-in-out infinite}.float-c{animation:floatC 4.8s ease-in-out infinite}
  @keyframes floatA{50%{transform:translateY(-5px) rotate(1deg)}}@keyframes floatB{50%{transform:translateY(4px) rotate(-1deg)}}@keyframes floatC{50%{transform:translateY(-3px)}}
  .filterbar{padding:10px 13px;border:1px dashed #d8d0c3;background:rgba(255,255,255,.78);border-radius:16px;box-shadow:var(--shadow-s)}
  .filter-label{font-size:10.5px;color:#4b4742}.light-badge{border-radius:999px;background:#fff5ca;color:#8d5d00;border:1px solid #ebc75a;box-shadow:none}
  .pill,.chip{border-radius:999px!important;padding:6px 11px}.pill.on,.chip.on{background:#171720;color:#fff;box-shadow:3px 3px 0 #c1b0ff}.pill:hover,.chip:hover{transform:translateY(-1px);box-shadow:2px 2px 0 #c1b0ff}
  .kpis{gap:12px}.kpi{position:relative;min-height:112px;padding:13px 14px 12px;border:1px solid rgba(23,23,32,.13);border-radius:18px;box-shadow:0 3px 0 rgba(23,23,32,.08);overflow:hidden}
    .kpi:hover{transform:translateY(-3px) rotate(-.35deg);box-shadow:5px 6px 0 rgba(23,23,32,.12)}
    .kpi-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px}.kico{display:grid;place-items:center;width:30px;height:30px;border-radius:10px;background:var(--kpi-icon-bg,rgba(255,255,255,.72));border:1px solid rgba(23,23,32,.10)}.kico svg{width:18px;height:18px;stroke:var(--kpi-icon-color,#171720);stroke-width:1.8;fill:none;stroke-linecap:round;stroke-linejoin:round}.kmini{font-size:9px;font-weight:700;color:rgba(23,23,32,.55);letter-spacing:.04em}
    .kpi .v{font-size:27px;font-weight:760;color:#171720;letter-spacing:-.05em}.kpi .l{font-size:10.5px;color:#4f4b47;margin-top:3px}
    .kpi.masks{--kpi-accent:linear-gradient(90deg,#635bff,#0a72ef);--kpi-icon-bg:rgba(99,91,255,.15);--kpi-icon-color:#635bff;border-left:4px solid #635bff;background:linear-gradient(180deg,rgba(99,91,255,.04),rgba(255,255,255,0))}
    .kpi.delta{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a;border-left:4px solid #12b76a;background:linear-gradient(180deg,rgba(18,183,106,.04),rgba(255,255,255,0))}
    .kpi.growth{--kpi-accent:linear-gradient(90deg,#2563eb,#635bff);--kpi-icon-bg:rgba(37,99,235,.15);--kpi-icon-color:#2563eb;border-left:4px solid #2563eb;background:linear-gradient(180deg,rgba(37,99,235,.04),rgba(255,255,255,0))}
    .kpi.units{--kpi-accent:linear-gradient(90deg,#0a72ef,#12b76a);--kpi-icon-bg:rgba(10,114,239,.15);--kpi-icon-color:#0a72ef;border-left:4px solid #0a72ef;background:linear-gradient(180deg,rgba(10,114,239,.04),rgba(255,255,255,0))}
    .kpi.ratio{--kpi-accent:linear-gradient(90deg,#f79009,#fbbf24);--kpi-icon-bg:rgba(217,119,6,.15);--kpi-icon-color:#f79009;border-left:4px solid #f79009;background:linear-gradient(180deg,rgba(217,119,6,.04),rgba(255,255,255,0))}
    .kpi.quality{--kpi-accent:linear-gradient(90deg,#635bff,#0a72ef);--kpi-icon-bg:rgba(99,91,255,.15);--kpi-icon-color:#635bff;border-left:4px solid #635bff;background:linear-gradient(180deg,rgba(99,91,255,.04),rgba(255,255,255,0))}
    .kpi.completed{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a;border-left:4px solid #12b76a;background:linear-gradient(180deg,rgba(18,183,106,.04),rgba(255,255,255,0))}
    .kpi.pending{--kpi-accent:linear-gradient(90deg,#f79009,#fbbf24);--kpi-icon-bg:rgba(217,119,6,.15);--kpi-icon-color:#f79009;border-left:4px solid #f79009;background:linear-gradient(180deg,rgba(217,119,6,.04),rgba(255,255,255,0))}
    .kpi.action{--kpi-accent:linear-gradient(90deg,#dc2626,#f87171);--kpi-icon-bg:rgba(220,38,38,.15);--kpi-icon-color:#dc2626;border-left:4px solid #dc2626;background:linear-gradient(180deg,rgba(220,38,38,.04),rgba(255,255,255,0))}
    .kpi.answered{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a;border-left:4px solid #12b76a;background:linear-gradient(180deg,rgba(18,183,106,.04),rgba(255,255,255,0))}
    .kpi.newcase{--kpi-accent:linear-gradient(90deg,#2563eb,#635bff);--kpi-icon-bg:rgba(37,99,235,.15);--kpi-icon-color:#2563eb;border-left:4px solid #2563eb;background:linear-gradient(180deg,rgba(37,99,235,.04),rgba(255,255,255,0))}
    .kpi.completion{--kpi-accent:linear-gradient(90deg,#12b76a,#22c55e);--kpi-icon-bg:rgba(18,183,106,.15);--kpi-icon-color:#12b76a;border-left:4px solid #12b76a;background:linear-gradient(180deg,rgba(18,183,106,.04),rgba(255,255,255,0))}
    .kpi.topdistrict{--kpi-accent:linear-gradient(90deg,#9b51e0,#635bff);--kpi-icon-bg:rgba(155,81,224,.15);--kpi-icon-color:#9b51e0;border-left:4px solid #9b51e0;background:linear-gradient(180deg,rgba(155,81,224,.04),rgba(255,255,255,0))}
    .kpi.alert{--kpi-accent:linear-gradient(90deg,#dc2626,#f87171);--kpi-icon-bg:rgba(220,38,38,.15);--kpi-icon-color:#dc2626;border-left:4px solid #dc2626;background:linear-gradient(180deg,rgba(220,38,38,.04),rgba(255,255,255,0))}
  .card{border:1px solid #e2dbcf;border-radius:20px;padding:16px;background:#fff;box-shadow:var(--shadow-m)}.card:hover{transform:translateY(-1px);box-shadow:0 3px 0 #dad4c8,0 18px 34px -27px rgba(67,8,159,.28)}
  .card h2{font-size:13px;border-bottom:1px dashed #ded7ca;padding-bottom:11px}.card h2::after{width:9px;height:9px;background:#c1b0ff;box-shadow:0 0 0 5px #f1edff}.card h2.g::after{background:#84e7a5;box-shadow:0 0 0 5px #e8faee}.card h2.am::after{background:#f8cc65;box-shadow:0 0 0 5px #fff7df}.card h2.p::after{background:#fc7981;box-shadow:0 0 0 5px #ffeaec}
  .row>.card:first-child{background:linear-gradient(180deg,#fff,#fdfbff)}.row>.card:last-child{background:linear-gradient(180deg,#fff,#f9fffb)}
  .legend{border-top:1px dashed #ded7ca}.search{border-radius:999px;background:#fff}.scroll{border:1px solid #e2dbcf;border-radius:13px;box-shadow:none}
  .insight{border-radius:14px}.rep-day{border-radius:14px;background:#fbfaf7;border:1px dashed #d8d0c3;box-shadow:none}.rep-item{border-radius:999px}
  .clip-label{font-size:9px;font-weight:750;letter-spacing:.08em;text-transform:uppercase;fill:#43089f}
  html,body{width:100%;max-width:100%;overflow-x:hidden}.grid,.card,.chartbox,.chartjs-box{min-width:0}
  .chartjs-box{position:relative;width:100%;min-height:230px;overflow:visible}.chart-stage{position:relative;width:100%;height:100%}.chartjs-box canvas{display:block!important;width:100%!important;height:100%!important;max-width:100%}
  .mobile-category-key{display:none}
  .card{container-type:inline-size;container-name:dashboard-card}
  .chart-powered{display:inline-flex;align-items:center;gap:5px;margin-left:8px;padding:2px 7px;border-radius:999px;background:#f1edff;color:#5925dc;font-size:8.5px;font-weight:750;letter-spacing:.04em;vertical-align:middle}
  .chart-powered::before{content:'';width:5px;height:5px;border-radius:50%;background:#6246ea;box-shadow:0 0 0 3px rgba(98,70,234,.12)}
  .icd-zone{margin:14px 0;padding:12px;border:1px solid #cfdcf8;border-radius:24px;background:linear-gradient(145deg,#edf4ff 0%,#f7f3ff 48%,#ecfbf4 100%);box-shadow:0 6px 0 #dbe5f6}
  .icd-zone .card{margin:12px 0;background:rgba(255,255,255,.92)}
  .icd-hero{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 18px 10px}.icd-hero h2{margin:3px 0 2px;font-size:21px}.icd-hero p{margin:0;color:#67627a;font-size:11px}.icd-mark{display:grid;place-items:center;width:72px;height:72px;border-radius:22px;background:#171720;color:#fff;font-size:19px;font-weight:850;letter-spacing:-.04em;transform:rotate(3deg);box-shadow:6px 6px 0 #98d9c2}.icd-mark span{color:#b8a5ff}
  .icd-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:2px 0 12px}.icd-kpi{min-height:94px;padding:12px 14px;border:1px solid rgba(80,73,112,.14);border-radius:17px;background:#fff;box-shadow:0 3px 0 rgba(80,73,112,.10)}.icd-kpi:nth-child(1){background:#e5dcff}.icd-kpi:nth-child(2){background:#dff2ff}.icd-kpi:nth-child(3){background:#dcf7e8}.icd-kpi:nth-child(4){background:#fff0c8}.icd-kpi .lab{font-size:9px;font-weight:800;letter-spacing:.08em;color:#615d70;text-transform:uppercase}.icd-kpi .val{display:block;margin:5px 0 1px;font-size:25px;font-weight:850;color:#171720}.icd-kpi small{font-size:9px;color:#67627a}
  .icd-code{display:inline-flex;align-items:center;gap:4px;margin:2px 4px 2px 0;padding:4px 7px;border-radius:8px;background:#f1edff;color:#4d2cc4;font-size:9.5px;font-weight:800;white-space:nowrap}.icd-code b{color:#171720}.source-note{margin:0 0 10px;padding:9px 11px;border:1px dashed #d5a413;border-radius:12px;background:#fff9df;color:#795c00;font-size:10px}.icd-unit-card table{max-width:100%;width:100%}.icd-unit-card td{vertical-align:top}.icd-unit-card td:nth-child(1){min-width:230px;font-weight:700}.icd-unit-card td:nth-child(5){min-width:370px}.icd-mini{display:block;margin:1px 0;color:#615d70;font-size:9.5px}.icd-charts{align-items:start}
#unitTable{max-width:100%;width:100%}
  .prov-zone{position:relative;margin:0 0 15px;padding:15px;border:1px solid #b9d6ff;border-radius:20px;background:linear-gradient(135deg,#e8f2ff 0%,#f3efff 52%,#e7faef 100%);box-shadow:0 4px 0 #d2e2f5;overflow:hidden}
  .prov-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.prov-head h2{margin:2px 0;font-size:18px;letter-spacing:-.025em}.prov-head p{margin:0;color:#5d6472;font-size:10.5px}.prov-stamp{flex:0 0 auto;padding:7px 10px;border-radius:999px;background:#171720;color:#fff;font-size:9.5px;font-weight:750}
  .prov-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px}.prov-kpi{min-height:88px;padding:11px 12px;border:1px solid rgba(23,23,32,.1);border-radius:15px;background:rgba(255,255,255,.86);box-shadow:0 2px 0 rgba(23,23,32,.07)}.prov-kpi .lab{font-size:8.5px;font-weight:800;letter-spacing:.07em;color:#667085;text-transform:uppercase}.prov-kpi .val{display:block;margin:5px 0 2px;font-size:23px;font-weight:820;letter-spacing:-.04em;color:#171720}.prov-kpi small{display:block;font-size:9px;color:#667085;line-height:1.35}.prov-note{margin:10px 0 0;padding:9px 11px;border-radius:11px;background:rgba(255,255,255,.72);color:#344054;font-size:10.5px;line-height:1.5}.prov-note b{color:#5925dc}
  .response-card{background:linear-gradient(145deg,#fff 0%,#f8fff9 58%,#fffaf0 100%)}
  .response-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:2px 0 12px}
  .response-kpi{min-height:78px;padding:10px 12px;border:1px solid rgba(23,23,32,.1);border-radius:15px;background:#fff;box-shadow:0 2px 0 rgba(23,23,32,.07)}
  .response-kpi:nth-child(1){background:#e8e0ff}.response-kpi:nth-child(2){background:#dcf7e8}.response-kpi:nth-child(3){background:#dff2ff}.response-kpi:nth-child(4){background:#ffe7e7}
  .response-kpi .lab{display:block;font-size:8.5px;font-weight:800;letter-spacing:.07em;color:#615d70;text-transform:uppercase}.response-kpi .val{display:block;margin:4px 0 1px;font-size:23px;font-weight:820;line-height:1.1;color:#171720}.response-kpi small{display:block;font-size:9px;color:#67627a}
  .response-toolbar{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 8px}.response-toolbar .filter-label{margin-right:2px}
  .response-mode{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:7px 11px;border:1px solid #ded7ca;border-radius:999px;background:#fff;color:#4b4742;font:inherit;font-size:10.5px;font-weight:700;cursor:pointer}
  .response-mode:hover{border-color:#9f8df2}.response-mode.on{border-color:#171720;background:#171720;color:#fff;box-shadow:3px 3px 0 #c1b0ff}
  .response-empty{display:grid;place-items:center;min-height:180px;padding:20px;border:1px dashed #d8d0c3;border-radius:14px;background:#fbfaf7;color:var(--mut);font-size:11px;text-align:center}
  @media(max-width:900px){
    body{padding:14px 12px 34px}.row{grid-template-columns:1fr}.hero{padding:20px}.hero-art{width:250px;min-width:220px}.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.icd-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
    .filterbar{align-items:stretch}.filterbar .controls{max-width:100%;flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-inline:contain;padding:2px 2px 6px;scrollbar-width:none}.filterbar .controls::-webkit-scrollbar{display:none}
    .pill,.chip,.btn{display:inline-flex;align-items:center;justify-content:center;min-height:40px;flex:0 0 auto}.search{min-height:40px}
    .card h2{line-height:1.35;gap:6px;overflow-wrap:anywhere}.chart-powered{flex:0 0 auto}.scroll{max-width:100%;overscroll-behavior-inline:contain;-webkit-overflow-scrolling:touch}.prov-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.response-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  }
  @media(max-width:680px){
    body{padding:8px 7px 28px;line-height:1.5}.hero{min-height:auto;align-items:flex-start;flex-direction:column;padding:18px 14px;border-radius:20px}.hero-copy{max-width:100%}.hero-art{width:100%;min-width:0;height:122px;align-self:center}.hero-art svg{width:min(100%,320px);height:128px}h1{font-size:25px}.sub{font-size:11.5px}.hero-meta{gap:6px}.live-status,.light-badge{font-size:10px}
    .filterbar{padding:9px 8px;gap:7px;border-radius:14px}.filterbar .controls{width:100%}.filter-label{flex:0 0 auto}.light-badge{align-self:flex-start}.pill,.chip{padding:7px 11px}
    .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.kpi{min-height:102px;padding:11px;border-radius:15px}.kpi .v{font-size:25px}.kpi .l{font-size:10px}.kpi-top{margin-bottom:7px}
    .card{padding:12px 10px;border-radius:16px;margin-bottom:10px}.card h2{font-size:12px;min-height:0;margin-bottom:9px;padding-bottom:9px;flex-wrap:wrap}.card h2::after{display:none}.chart-powered{margin-left:0;font-size:8px}
    .chartjs-box.chart-horizontal{overflow:hidden;padding-bottom:0;-webkit-overflow-scrolling:auto;overscroll-behavior-inline:auto;max-width:100%}.chartjs-box.chart-horizontal .chart-stage{width:100%;min-width:0;max-width:100%}
    .mobile-category-key{display:grid;grid-template-columns:1fr;gap:4px;list-style:none;margin:7px 0 2px;padding:8px;border:1px dashed #ddd4c8;border-radius:10px;background:#fffdf8}.mobile-category-key li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:6px;align-items:start;font-size:10px;line-height:1.35;color:#4d4842}.mobile-category-key b{display:grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#eeeaff;color:#6246ea;font-size:9px}.mobile-category-key span{overflow-wrap:anywhere}.mobile-category-key small{display:block;margin-top:1px;color:#77716a;font-size:9px;line-height:1.35}
    .legend{font-size:9.5px;gap:7px 10px;margin-top:8px;padding-top:8px}.legend span{white-space:normal}.insight{font-size:11px;padding:9px 10px}.rep-day{padding:10px}.rep-sec{align-items:flex-start}.rep-item{white-space:normal;line-height:1.45}
    .search{width:100%;min-width:0;height:44px;font-size:16px}.scroll{border-radius:10px}.dsumwrap{overflow-x:auto;-webkit-overflow-scrolling:touch}.dsumwrap table{max-width:100%;width:100%}
    .icd-zone{margin:10px 0;padding:7px;border-radius:18px;box-shadow:0 4px 0 #dbe5f6}.icd-hero{padding:12px 10px 8px;gap:10px}.icd-hero h2{font-size:18px}.icd-hero p{font-size:10px}.icd-mark{width:56px;height:56px;border-radius:17px;font-size:15px;box-shadow:4px 4px 0 #98d9c2}.icd-kpis{gap:7px}.icd-kpi{min-height:82px;padding:10px;border-radius:14px}.icd-kpi .val{font-size:22px}.icd-kpi .lab{font-size:8px}.icd-kpi small{font-size:8.5px}.source-note{font-size:9px;line-height:1.45}.icd-unit-card td:nth-child(1){min-width:190px}.icd-unit-card td:nth-child(5){min-width:330px}.prov-zone{padding:11px;border-radius:17px}.prov-head{flex-direction:column;gap:7px}.prov-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.prov-kpi{min-height:82px;padding:10px}.prov-kpi .val{font-size:21px}
  }
  @media(max-width:480px){
    .pill,.chip,.btn,.response-mode{min-height:44px}.chart-powered{display:none}.icd-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.icd-hero .eyebrow{font-size:8px;letter-spacing:.09em}.icd-mark{width:50px;height:50px}.card h2{font-size:11.5px}.response-toolbar{align-items:stretch}.response-toolbar .filter-label{width:100%}.response-mode{flex:1 1 calc(50% - 7px);padding-inline:8px}
  }
  @media(max-width:1024px){.row{grid-template-columns:1fr}}
  @media(max-width:768px){.filterbar .controls{scroll-snap-type:x proximity}.filterbar .pill,.filterbar .chip{scroll-snap-align:start}}
  @media(max-width:430px){body{padding-inline:7px}.prov-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:390px){.hero{padding-inline:12px}.kpi{min-height:98px}.prov-kpi{padding-inline:9px}}
  @media(max-width:360px){h1{font-size:22px}.kpi .v{font-size:23px}.card{padding-inline:8px}}
  @media(min-width:769px){
    .chartjs-box.chart-horizontal{max-width:100%;overflow-x:auto}.chartjs-box.chart-horizontal .chart-stage{max-width:100%}
    .card{overflow:hidden}
  }
  @media(min-width:768px) and (max-width:1024px){
    .chartjs-box.chart-horizontal{max-width:100%;overflow-x:auto}.chartjs-box.chart-horizontal .chart-stage{max-width:100%}
    .card{overflow:hidden}
  }
  @media(min-width:1024px) and (max-width:1440px){
    .chartjs-box.chart-horizontal{max-width:100%;overflow-x:auto}.chartjs-box.chart-horizontal .chart-stage{max-width:100%}
    .card{overflow:hidden}
  }
  @supports(container-type:inline-size){
    @container dashboard-card (max-width:430px){
      h2{font-size:11.5px;line-height:1.35;overflow-wrap:anywhere}.chart-powered{display:none}.legend{gap:7px 10px}.mobile-category-key{grid-template-columns:1fr}
    }
    @container dashboard-card (min-width:431px) and (max-width:768px){
      h2{font-size:12px}.legend{gap:9px 12px}
    }
    @container dashboard-card (min-width:769px){
      .chartjs-box.chart-horizontal{max-width:100%;overflow-x:auto}.chartjs-box.chart-horizontal .chart-stage{max-width:100%}
    }
  }
</style></head>
<body>
<header class="hero">
  <div class="hero-copy">
    <div class="eyebrow">Satun Provincial Health Analytics</div>
    <h1>ศูนย์วิเคราะห์ PHR Masks <span class="tag">LIVE DATA</span></h1>
    <div class="sub">มองเห็นแนวโน้มการใช้งาน การตอบกลับ และคุณภาพข้อมูลของหน่วยบริการได้ในหน้าจอเดียว</div>
    <div class="hero-meta"><div class="live-status"><span class="live-dot"></span>ข้อมูลพร้อมวิเคราะห์</div><span class="light-badge">☀️ Light dashboard</span></div>
  </div>
  <div class="hero-art" aria-hidden="true">
    <svg viewBox="0 0 320 160" role="img">
      <path d="M38 126C20 101 29 59 62 39c29-18 72-24 105-9 28 13 39 5 71 11 37 7 59 36 50 66-9 31-43 40-81 38l-98 2c-32 0-56-2-71-21Z" fill="rgba(255,255,255,.52)"/>
      <g class="float-a">
        <rect x="91" y="34" width="130" height="103" rx="20" fill="#fff" stroke="#171720" stroke-width="1.5"/>
        <path d="M91 56a20 20 0 0 1 20-20h90a20 20 0 0 1 20 20v9H91Z" fill="#c1b0ff"/>
        <circle cx="111" cy="50" r="4" fill="#fc7981"/><circle cx="124" cy="50" r="4" fill="#f8cc65"/><circle cx="137" cy="50" r="4" fill="#84e7a5"/>
        <rect x="107" y="77" width="25" height="19" rx="5" fill="#e9e3ff"/><rect x="143" y="77" width="25" height="19" rx="5" fill="#dff7ff"/><rect x="179" y="77" width="25" height="19" rx="5" fill="#e5f8dc"/>
        <rect x="107" y="106" width="25" height="19" rx="5" fill="#fff0bf"/><rect x="143" y="106" width="25" height="31" rx="6" fill="#6246ea"/><rect x="179" y="106" width="25" height="19" rx="5" fill="#ffdfe5"/>
        <path d="M155.5 113v17M147 121.5h17" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
      </g>
      <g class="float-b">
        <circle cx="67" cy="60" r="27" fill="#fc7981" stroke="#171720" stroke-width="1.4"/>
        <path d="M53 58c0-8 10-11 14-4 4-7 14-4 14 4 0 9-14 17-14 17S53 67 53 58Z" fill="#fff"/>
        <path d="M45 83h32" stroke="#171720" stroke-width="1.3" stroke-linecap="round" opacity=".25"/>
      </g>
      <g class="float-c">
        <rect x="226" y="28" width="62" height="48" rx="14" fill="#f8cc65" stroke="#171720" stroke-width="1.4"/>
        <path d="M241 59V49M253 59V42M265 59V47M277 59V37" stroke="#171720" stroke-width="4" stroke-linecap="round"/>
        <text x="238" y="69" class="clip-label">PHR DATA</text>
      </g>
      <g class="float-b">
        <rect x="227" y="91" width="72" height="45" rx="15" fill="#84e7a5" stroke="#171720" stroke-width="1.4"/>
        <circle cx="248" cy="108" r="8" fill="#fff"/><circle cx="277" cy="108" r="8" fill="#fff"/>
        <path d="M235 128c2-9 9-14 17-14s15 5 17 14M265 128c2-8 8-13 15-13s13 5 15 13" fill="#fff" opacity=".95"/>
      </g>
      <path d="M49 119c11-8 21-8 31 0" stroke="#6246ea" stroke-width="3" stroke-linecap="round" stroke-dasharray="3 7"/>
      <circle cx="48" cy="128" r="5" fill="#3bd3fd"/><circle cx="304" cy="73" r="5" fill="#c1b0ff"/><path d="M294 144h13M300.5 137.5v13" stroke="#fc7981" stroke-width="3" stroke-linecap="round"/>
    </svg>
  </div>
</header>

<div class="filterbar">
  <div class="controls">
    <span class="filter-label">📍 พื้นที่</span>
    <span id="distPills"></span>
  </div>
  <div class="controls">
    <span class="filter-label">📅 ช่วงวัน</span>
    <span id="dayChips"></span>
  </div>
  <span class="light-badge">✨ Health Bento</span>
</div>

<div class="grid kpis" id="kpiBox"></div>

<section class="prov-zone" id="provinceZone" hidden>
  <div class="prov-head">
    <div><div class="eyebrow">Province pulse · ข้อมูลภาพรวมล่าสุด</div><h2 id="provinceTitle"></h2><p id="provinceSubtitle"></p></div>
    <div class="prov-stamp" id="provinceStamp"></div>
  </div>
  <div class="prov-grid" id="provinceKpis"></div>
  <div class="prov-note" id="provinceInsight"></div>
</section>

<div class="card">
  <h2 class="am">🕒 มิติเวลา 1 — แนวโน้ม Masks &amp; ประชาชน <span class="chart-powered">Chart.js</span></h2>
  <div class="chartbox" id="trendChart"></div>
  <div class="legend"><span style="color:var(--accent)">■ Masks (visit)</span><span style="color:var(--green)">■ ประชาชน</span></div>
</div>

<div class="grid row">
  <div class="card">
    <h2>📊 มิติเวลา 2 — ส่วนต่าง Masks รายวัน (net change) <span class="chart-powered">Chart.js</span></h2>
    <div class="chartbox" id="netChart"></div>
    <div class="legend"><span style="color:var(--green)">■ เพิ่ม</span><span style="color:var(--red)">■ ลด</span></div>
  </div>
  <div class="card">
    <h2 class="g">🗺️ มิติอำเภอ — สัดส่วน Masks รายวัน (Stacked) <span class="chart-powered">Chart.js</span></h2>
    <div class="chartbox" id="stackChart"></div>
    <div class="legend" id="stackLegend"></div>
  </div>
</div>

<div class="grid row">
  <div class="card">
    <h2 class="p">📐 มิติหน่วย 1 — Pareto Top 8 (สัดส่วนการมีส่วนร่วม &amp; การสะสม) <span class="chart-powered">Chart.js</span></h2>
    <div class="chartbox" id="paretoChart"></div>
  </div>
  <div class="card">
    <h2 class="g">🚀 มิติหน่วย 2 — Momentum (หน่วยที่เติบโตสะสม) <span class="chart-powered">Chart.js</span></h2>
    <div class="chartbox" id="momChart"></div>
  </div>
</div>

<div class="card">
  <h2 class="am">⚖️ มิติคุณภาพ — อัตราส่วน Masks / ประชาชน (Top 8) <span class="chart-powered">Chart.js</span></h2>
  <div class="chartbox" id="ratioChart"></div>
</div>

<div class="card">
  <h2>💬 มิติ "ตอบกลับ" (answered) — การตอบกลับประชาชนรายวัน <span class="chart-powered">Chart.js</span></h2>
  <div class="chartbox" id="ansChart"></div>
  <div class="legend"><span style="color:var(--accent)">■ การเข้าเยี่ยม (encounters)</span><span style="color:var(--green)">■ ตอบกลับ (answered)</span></div>
  <div class="insight a" id="ansInsight"></div>
</div>

<div class="card response-card">
  <h2 class="g">🏥 มิติหน่วย 3 — ประสิทธิภาพการตอบกลับรายหน่วย <span class="chart-powered">Chart.js</span></h2>
  <div class="response-kpis" id="unitResponseKpis"></div>
  <div class="response-toolbar" role="group" aria-label="เลือกมุมมองการตอบกลับรายหน่วย">
    <span class="filter-label">มุมมอง</span>
    <button type="button" class="response-mode on" data-response-mode="answered" aria-pressed="true">ตอบกลับล่าสุด</button>
    <button type="button" class="response-mode" data-response-mode="delta" aria-pressed="false">เพิ่มขึ้นรอบล่าสุด</button>
    <button type="button" class="response-mode" data-response-mode="pending" aria-pressed="false">ยังไม่ตอบ</button>
  </div>
  <div class="chartbox" id="unitResponseChart"></div>
  <div class="insight g" id="unitResponseInsight"></div>
</div>

<section class="icd-zone">
  <div class="icd-hero">
    <div>
      <div class="eyebrow">Clinical coding lens · 14 หน่วยบริการ</div>
      <h2>🧬 ภาพรวม ICD-10 ที่พบ</h2>
      <p>สรุปรหัสวินิจฉัยที่มองเห็นจากภาพรายหน่วย พร้อมโครงสร้างกลุ่มโรคและจุดเฝ้าระวัง</p>
    </div>
    <div class="icd-mark" aria-hidden="true">ICD<span>10</span></div>
  </div>
  <div class="icd-kpis" id="icdKpis"></div>
  <div class="grid row icd-charts">
    <div class="card">
      <h2 class="p">🏷️ รหัสที่พบบ่อย Top 10 <span class="chart-powered">Chart.js</span></h2>
      <div class="chartbox" id="icdTopChart"></div>
    </div>
    <div class="card">
      <h2 class="g">🧩 สัดส่วนตามหมวด ICD-10 <span class="chart-powered">Chart.js</span></h2>
      <div class="chartbox" id="icdChapterChart"></div>
    </div>
  </div>
  <div class="card icd-unit-card">
    <h2>🏥 ICD-10 รายหน่วยบริการ</h2>
    <div class="source-note" id="icdSourceNote"></div>
    <div class="scroll"><table id="icdTable"><thead><tr><th>หน่วยบริการ</th><th>อำเภอ</th><th>รหัสที่พบ</th><th>รายการ</th><th>รายละเอียดรหัส</th></tr></thead><tbody></tbody></table></div>
  </div>
  <div class="card">
    <h2 class="am">🔎 บทวิเคราะห์ ICD-10</h2>
    <div id="icdInsights"></div>
  </div>
</section>

<div class="card">
  <h2 class="g">🗂️ มิติอำเภอ — สรุปรวม Masks รายอำเภอ</h2>
  <div id="distSum"></div>
</div>

<div class="card">
  <h2>📋 รายงานรายวัน — หน่วยที่มียอดเพิ่ม/ใหม่/ลด ในแต่ละวัน</h2>
  <div class="controls" id="reportNav"></div>
  <div id="dailyReport"></div>
</div>

<div class="card">
  <h2>🏷️ ตารางส่วนต่างรายหน่วย (masks) — วัน×หน่วย</h2>
  <div class="controls">
    <input class="search" id="unitSearch" placeholder="🔍 ค้นหาชื่อหน่วย/อำเภอ...">
  </div>
  <div class="scroll">
    <table id="unitTable"><thead></thead><tbody></tbody></table>
  </div>
  <div class="legend">
    <span><b class="c-base">n</b> ค่าฐานวันแรก</span>
    <span><b class="c-up">+n</b> เพิ่ม</span><span><b class="c-new">ใหม่</b> ปรากฏวันนั้น</span>
    <span><b class="c-flat">0</b> คงที่</span><span><b class="c-down">−n</b> ลดลง</span>
  </div>
</div>

<div class="card">
  <h2>💡 สรุปข้อวิเคราะห์ (Insights)</h2>
  <div class="insight"><b>1. จังหวะการเปลี่ยนแปลง:</b> เริ่ม 116 → ล่าสุด 118 (+2, โต 1.7%) โดยเปลี่ยนรายวัน +2, +5 และ −5 ตามลำดับ</div>
  <div class="insight a"><b>2. ศูนย์กลางข้อมูล:</b> อำเภอละงูมียอดล่าสุดสูงสุด 64 Masks ตามด้วยเมืองสตูล 34 Masks จึงควรติดตามการกระจุกตัวใน 2 พื้นที่หลัก</div>
  <div class="insight g"><b>3. ฐานประชาชน:</b> ประชาชนเพิ่มจาก 48 → 53 (+5 หรือ 10.4%) ขณะที่ Masks เพิ่มสุทธิ 2 ทำให้อัตราส่วนล่าสุดอยู่ที่ 2.23</div>
  <div class="insight" id="ins4"><b>4. คุณภาพและตอบกลับ:</b> Match rate 100% · วันล่าสุดตอบกลับ 17/118 (14%)</div>
  <div class="insight a"><b>5. จุดที่ควรตรวจสอบ:</b> Snapshot ล่าสุดลดลง 5 Masks โดยกำแพง −6, ศรีพิมาน −2 และ รพ.สตูล −2 แม้มีหน่วยใหม่และบางหน่วยเพิ่มขึ้น ควรยืนยันที่มาของการปรับยอด</div>
</div>

<div id="tip"></div>

<script>/*__CHARTJS__*/</script>
<script>/*__DATALABELS__*/</script>
<script>
/*__DATA__*/
/*__PROVINCE__*/
/*__ICD10__*/
const DIST_COLORS={'ละงู':'#635bff','เมืองสตูล':'#0a72ef','ควนกาหลง':'#f79009','ควนโดน':'#9b51e0','ทุ่งหว้า':'#12b76a'};
const state={dist:'all', days:DATA.labels.map((_,i)=>i), theme:'light', sortKey:'name', sortDir:1, search:'', reportDay:-1, responseMode:'answered', statusFilter:'all', actionFilter:'all'};
const tip=document.getElementById('tip');
function showTip(e,txt){tip.textContent=txt;tip.style.opacity=1;tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';}
function hideTip(){tip.style.opacity=0;}

// ---- filtering ----
function getPrimaryStatus(unit, dayIdx){
  const statusFields = ['status_pending','status_in_progress','status_completed','status_no_error_found','status_not_recorded'];
  let maxVal = -1, primary = 'all';
  for(const f of statusFields){
    const arr = unit[f]; if(!arr) continue;
    const v = arr[dayIdx] || 0;
    if(v > maxVal){ maxVal = v; primary = f; }
  }
  return maxVal > 0 ? primary : 'all';
}
function getPrimaryAction(unit, dayIdx){
  const actionFields = ['action_none_yet','action_data_corrected','action_other','action_not_recorded'];
  let maxVal = -1, primary = 'all';
  for(const f of actionFields){
    const arr = unit[f]; if(!arr) continue;
    const v = arr[dayIdx] || 0;
    if(v > maxVal){ maxVal = v; primary = f; }
  }
  return maxVal > 0 ? primary : 'all';
}
function selUnits(){
  let u=DATA.units;
  if(state.dist!=='all') u=u.filter(x=>x.dist===state.dist);
  if(state.search){const s=state.search.toLowerCase();u=u.filter(x=>x.name.toLowerCase().includes(s)||x.dist.toLowerCase().includes(s));}
  const dayIdx = activeIdx().slice(-1)[0];
  if(state.statusFilter!=='all') u=u.filter(x=>getPrimaryStatus(x, dayIdx)===state.statusFilter);
  if(state.actionFilter!=='all') u=u.filter(x=>getPrimaryAction(x, dayIdx)===state.actionFilter);
  return u;
}
function activeIdx(){return state.days.slice().sort((a,b)=>a-b);}
function totalsFor(units){
  const idx=activeIdx();
  const m=idx.map(i=>units.reduce((s,u)=>s+u.masks[i],0));
  const c=idx.map(i=>units.reduce((s,u)=>s+u.cit[i],0));
  return {idx,m,c};
}
const css=v=>getComputedStyle(document.body).getPropertyValue(v).trim();

const svgns='http://www.w3.org/2000/svg';
function defsGrad(id,c1,c2){
  return `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>`;
}
const SVGDEFS=defsGrad('gA',css('--accent'),css('--green'))+defsGrad('gB',css('--green'),'#22c55e')+defsGrad('gC',css('--amber'),'#f59e0b');
function lineChart(el,labels,series){
  const w=580,h=240,pad_l=46,pad_b=30,pad_t=18;const pw=w-pad_l-18,ph=h-pad_b-pad_t;
  const maxv=Math.max(1,...series.flatMap(s=>s.vals));
  const acc=series[0].color, grc=css('--accent');
  let s=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMidYMid meet" style="display:block;filter:drop-shadow(0 4px 10px rgba(15,23,42,.08))">`+SVGDEFS;
  for(let i=0;i<5;i++){const yy=pad_t+ph*(1-i/4),vv=Math.round(maxv*i/4);
    s+=`<line x1="${pad_l}" y1="${yy}" x2="${w-18}" y2="${yy}" stroke="${css('--line')}"/>`;
    s+=`<text x="${pad_l-8}" y="${yy+4}" font-size="10" fill="${css('--mut')}" text-anchor="end">${vv}</text>`;}
  const n=labels.length,gw=pw/n;
  series.forEach((se,si)=>{
    let pts='';
    labels.forEach((lab,gi)=>{const cx=pad_l+gi*gw+gw/2,yy=pad_t+ph*(1-se.vals[gi]/maxv);pts+=`${cx},${yy} `;});
    s+=`<polyline points="${pts}" fill="none" stroke="${se.color}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>`;
    labels.forEach((lab,gi)=>{const cx=pad_l+gi*gw+gw/2,yy=pad_t+ph*(1-se.vals[gi]/maxv);
      s+=`<circle cx="${cx}" cy="${yy}" r="4.5" fill="${se.color}" stroke="var(--card)" stroke-width="2"/>`;
      s+=`<text x="${cx}" y="${yy-10}" font-size="11" font-weight="700" fill="var(--txt)" text-anchor="middle">${se.vals[gi]}</text>`;
      s+=`<text x="${cx}" y="${h-10}" font-size="10.5" fill="var(--mut)" text-anchor="middle">${lab}</text>`;});
  });
  s+='</svg>';el.innerHTML=s;
}
function barChart(el,labels,vals){
  const w=560,h=210,pad_l=40,pad_b=30,pad_t=22;const pw=w-pad_l-18,ph=h-pad_b-pad_t;
  const maxv=Math.max(1,...vals.map(Math.abs));
  let s=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMidYMid meet" style="display:block;filter:drop-shadow(0 4px 10px rgba(15,23,42,.08))">${SVGDEFS}`;
  for(let i=0;i<5;i++){const yy=pad_t+ph*(1-i/4),vv=Math.round(maxv*i/4);
    s+=`<line x1="${pad_l}" y1="${yy}" x2="${w-18}" y2="${yy}" stroke="${css('--line')}"/>`;
    s+=`<text x="${pad_l-7}" y="${yy+4}" font-size="10" fill="${css('--mut')}" text-anchor="end">${vv}</text>`;}
  const n=vals.length,gw=pw/n,bw=Math.min(64,gw-22);
  labels.forEach((lab,gi)=>{const cx=pad_l+gi*gw+gw/2,val=vals[gi];
    const bh=ph*(Math.abs(val)/maxv),by=pad_t+ph-(val>0?bh:0);
    const c=val>0?'url(#gA)':(val<0?css('--red'):css('--mut'));
    s+=`<rect class="bar" data-tip="${lab}: ${val>=0?'+':''}${val}" x="${cx-bw/2}" y="${by}" width="${bw}" height="${Math.max(bh,2)}" rx="5" fill="${c}"/>`;
    s+=`<text x="${cx}" y="${by-7}" font-size="12" font-weight="700" fill="var(--txt)" text-anchor="middle">${val>=0?'+':''}${val}</text>`;
    s+=`<text x="${cx}" y="${h-11}" font-size="10.5" fill="var(--mut)" text-anchor="middle">${lab}</text>`;});
  s+='</svg>';el.innerHTML=s;attachTips(el);
}
function hbar(el,items){
  const w=560,row=30,lw=190,pad_t=6;const maxv=Math.max(1,...items.map(i=>i.val));
  const h=row*items.length+pad_t*2;let s=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMinYMin meet" style="display:block;filter:drop-shadow(0 3px 8px rgba(15,23,42,.08))">${SVGDEFS}`;
  let y=pad_t;
  items.forEach(it=>{const bw=(w-lw-66)*(it.val/maxv);
    s+=`<text x="0" y="${y+row/2}" font-size="11.5" fill="var(--txt)" dominant-baseline="middle">${it.name}</text>`;
    s+=`<rect x="${lw}" y="${y+5}" width="${w-lw-66}" height="${row-12}" rx="7" fill="${css('--line')}" opacity="0.5"/>`;
    s+=`<rect class="bar" data-tip="${it.name}: ${it.val}${it.extra||''}" x="${lw}" y="${y+5}" width="${Math.max(bw,3)}" height="${row-12}" rx="7" fill="${it.color}"/>`;
    s+=`<text x="${lw+Math.max(bw,3)+8}" y="${y+row/2}" font-size="11.5" fill="var(--txt)" dominant-baseline="middle" font-weight="700">${it.val}${it.suffix||''} ${it.extra||''}</text>`;
    y+=row;});
  s+='</svg>';el.innerHTML=s;attachTips(el);
}
function stacked(el,labels,distData){
  const w=560,h=240,pad_l=42,pad_b=30,pad_t=18;const pw=w-pad_l-18,ph=h-pad_b-pad_t;
  const maxv=Math.max(1,...labels.map(l=>DATA.districts.reduce((s,d)=>s+distData[l][d],0)));
  let s=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMidYMid meet" style="display:block;filter:drop-shadow(0 4px 10px rgba(15,23,42,.08))">`+SVGDEFS;
  for(let i=0;i<5;i++){const yy=pad_t+ph*(1-i/4),vv=Math.round(maxv*i/4);
    s+=`<line x1="${pad_l}" y1="${yy}" x2="${w-18}" y2="${yy}" stroke="${css('--line')}"/>`;
    s+=`<text x="${pad_l-7}" y="${yy+4}" font-size="10" fill="${css('--mut')}" text-anchor="end">${vv}</text>`;}
  const n=labels.length,gw=pw/n;
  labels.forEach((lab,gi)=>{const cx=pad_l+gi*gw+gw/2;let y=pad_t+ph;
    DATA.districts.forEach(d=>{const val=distData[lab][d];if(val===0)return;const col=DIST_COLORS[d]||'#94a3b8';
      const dim=(state.dist!=='all'&&state.dist!==d)?0.22:1;const bh=ph*(val/maxv);y-=bh;
      s+=`<rect class="bar" data-tip="${lab} ${d}: ${val}" x="${cx-28}" y="${y}" width="56" height="${bh}" fill="${col}" opacity="${dim}"/>`;});
    s+=`<text x="${cx}" y="${h-11}" font-size="10.5" fill="var(--mut)" text-anchor="middle">${lab}</text>`;});
  s+='</svg>';el.innerHTML=s;attachTips(el);
}
function attachTips(el){el.querySelectorAll('.bar').forEach(b=>{
  b.addEventListener('mousemove',e=>showTip(e,b.dataset.tip));
  b.addEventListener('mouseleave',hideTip);});}

// ---- Responsive controller + Chart.js modules ----
/*__RESPONSIVE_CONTROLLER__*/
// ---- Chart.js 4.5.1 + DataLabels 2.2.0 modules ----
Chart.register(ChartDataLabels);
Chart.defaults.font.family="-apple-system,BlinkMacSystemFont,'Noto Sans Thai','Leelawadee UI','Segoe UI',sans-serif";
Chart.defaults.color='#6f6b65';
const CHARTS={};
const reduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function viewportProfile(){return ResponsiveChartController.profileForWidth(window.innerWidth);}
function compactDate(label){const p=viewportProfile();if(!p.phone)return label;const s=String(label).split('/');return s.length===3?`${s[0]}/${s[1]}`:label;}
function wrapChartLabel(value,maxChars){
  const chars=Array.from(String(value));if(chars.length<=maxChars)return String(value);
  const lines=[];let rest=chars;
  while(rest.length){
    if(rest.length<=maxChars){lines.push(rest.join('').trim());break;}
    let cut=Math.min(maxChars,rest.length),space=-1;
    for(let i=cut-1;i>Math.floor(maxChars*.55);i--)if(rest[i]===' '){space=i;break;}
    if(space>0)cut=space;lines.push(rest.slice(0,cut).join('').trim());rest=rest.slice(cut);while(rest[0]===' ')rest.shift();
  }
  return lines;
}
function chartTooltip(){const p=viewportProfile();return {enabled:true,backgroundColor:'#171720',titleColor:'#fff',bodyColor:'#fff',padding:p.phone?9:10,cornerRadius:10,displayColors:true,boxPadding:4,titleFont:{weight:'700',size:p.phone?11:12},bodyFont:{size:p.phone?10:11},borderColor:'rgba(255,255,255,.12)',borderWidth:1};}
function chartScales(horizontal=false){
  const p=viewportProfile();
  const grid={color:'#ece6dc',drawBorder:false,lineWidth:1};
  const ticks={color:'#77716a',font:{size:p.phone?9:10},padding:p.phone?5:8,maxRotation:0};
  return horizontal?
    {x:{beginAtZero:true,grace:p.phone?'24%':'16%',grid,ticks:{...ticks,maxTicksLimit:p.phone?5:7}},y:{grid:{display:false},afterFit:axis=>{if(p.phone)axis.width=Math.min(axis.width,32);},ticks:{...ticks,color:'#2e2b31',font:{size:p.phone?9:10,weight:'700'},padding:p.phone?4:8}}}:
    {x:{grid:{display:false},ticks:{...ticks,autoSkip:true,maxTicksLimit:p.phone?4:7}},y:{beginAtZero:true,grid,ticks:{...ticks,maxTicksLimit:p.phone?6:8}}};
}
function mountChart(el,config,height=250){
  const p=viewportProfile();
  if(CHARTS[el.id]){CHARTS[el.id].destroy();delete CHARTS[el.id];}
  const horizontal=config.options&&config.options.indexAxis==='y';
  el.classList.add('chartjs-box');el.classList.toggle('chart-horizontal',horizontal);el.style.height=height+'px';
  el.innerHTML='<div class="chart-stage"><canvas role="img" aria-label="กราฟข้อมูล '+el.id+'"></canvas></div>';
  const base={responsive:true,maintainAspectRatio:false,animation:reduceMotion?false:{duration:650,easing:'easeOutQuart'},interaction:{mode:'index',intersect:false},layout:{padding:{top:p.phone?14:18,right:p.phone?5:10,left:p.phone?0:4,bottom:2}},plugins:{legend:{display:false},tooltip:chartTooltip(),datalabels:{display:false}}};
  config.options={...base,...(config.options||{}),plugins:{...base.plugins,...((config.options&&config.options.plugins)||{})}};
  CHARTS[el.id]=new Chart(el.querySelector('canvas'),config);
}
function lineChart(el,labels,series){
  const p=viewportProfile(),displayLabels=labels.map(compactDate);
  const sets=series.map(se=>({label:se.name,data:se.vals,borderColor:se.color,backgroundColor:se.color,borderWidth:p.phone?2.4:3,pointRadius:p.phone?3:4,pointHoverRadius:p.phone?5:7,pointBackgroundColor:'#fff',pointBorderColor:se.color,pointBorderWidth:p.phone?2:3,tension:.34,fill:false}));
  mountChart(el,{type:'line',data:{labels:displayLabels,datasets:sets},options:{scales:chartScales(false),plugins:{datalabels:{display:true,color:'#171720',align:'top',anchor:'end',offset:2,clamp:true,font:{size:p.phone?9:11,weight:'700'},formatter:v=>v},tooltip:{...chartTooltip(),callbacks:{title:c=>labels[c[0].dataIndex],label:c=>`${c.dataset.label}: ${c.formattedValue}`}}}}},p.phone?240:270);
}
function barChart(el,labels,vals){
  const p=viewportProfile(),displayLabels=labels.map(compactDate);
  const colors=vals.map(v=>v>0?'#6246ea':v<0?'#e84d5b':'#a6a19a');
  mountChart(el,{type:'bar',data:{labels:displayLabels,datasets:[{label:'ส่วนต่าง Masks',data:vals,backgroundColor:colors,borderColor:colors,borderWidth:1,borderRadius:p.phone?7:9,borderSkipped:false,maxBarThickness:p.phone?42:58}]},options:{scales:chartScales(false),plugins:{datalabels:{display:true,color:'#171720',anchor:'end',align:'end',clamp:true,font:{size:p.phone?9:11,weight:'700'},formatter:v=>(v>0?'+':'')+v},tooltip:{...chartTooltip(),callbacks:{title:c=>labels[c[0].dataIndex],label:c=>`เปลี่ยนแปลง: ${c.raw>0?'+':''}${c.raw}`}}}}},p.phone?220:240);
}
function renderMobileCategoryKey(el,items){
  const old=document.querySelector(`[data-chart-key="${el.id}"]`);if(old)old.remove();
  if(!viewportProfile().phone)return;
  const list=document.createElement('ol');list.className='mobile-category-key';list.dataset.chartKey=el.id;list.setAttribute('aria-label','รายชื่อหมวดหมู่ในกราฟ');
  items.forEach((item,n)=>{const li=document.createElement('li'),badge=document.createElement('b'),name=document.createElement('span');badge.textContent=String(n+1);name.textContent=item.name;if(item.keyDetail){const detail=document.createElement('small');detail.textContent=item.keyDetail;name.appendChild(detail);}li.append(badge,name);list.appendChild(li);});
  el.insertAdjacentElement('afterend',list);
}
function hbar(el,items){
  const p=viewportProfile(),maxChars=p.tablet?32:52,labels=items.map((i,n)=>p.phone?String(n+1):wrapChartLabel(i.name,maxChars));
  const maxLines=Math.max(1,...labels.map(l=>Array.isArray(l)?l.length:1)),row=p.phone?29+maxLines*9:(p.tablet?27+maxLines*8:24+maxLines*7),height=Math.max(p.phone?265:230,Math.min(760,items.length*row+50));
  const palette=['#6246ea','#246bfd','#078a52','#f0a202','#e84d5b','#9a62db'];
  const vals=items.map(i=>i.val),colors=items.map((i,n)=>i.color||palette[n%palette.length]);
  // Support dashed border for items with hasCorrection (momentum chart)
  const borderDash=items.map(i=>i.hasCorrection?[6,4]:[]);
  mountChart(el,{type:'bar',data:{labels,datasets:[{label:'ค่า',data:vals,backgroundColor:colors,borderColor:colors,borderWidth:1,borderDash:borderDash,borderSkipped:false,borderRadius:p.phone?6:8,barThickness:p.phone?13:16}]},options:{indexAxis:'y',layout:{padding:{top:6,right:p.phone?45:72,left:0,bottom:2}},scales:chartScales(true),plugins:{datalabels:{display:true,color:'#171720',anchor:'end',align:'right',clamp:true,clip:false,font:{size:p.phone?9:10,weight:'700'},formatter:(v,c)=>`${v}${items[c.dataIndex].extra?' '+items[c.dataIndex].extra:''}`},tooltip:{...chartTooltip(),callbacks:{title:c=>items[c[0].dataIndex].name,label:c=>`${c.raw} ${items[c.dataIndex].tooltipExtra||items[c.dataIndex].extra||''}`}}}}},height);
  renderMobileCategoryKey(el,items);
}
function hbarStacked(el,items,stackKeys,stackColors,stackLabels){
  // items: [{name, stacks: {key1: val1, key2: val2, ...}, extra, tooltipExtra}, ...]
  // stackKeys: array of keys in order (bottom to top)
  // stackColors: object key->color
  // stackLabels: object key->label for legend
  const p=viewportProfile(),maxChars=p.tablet?32:52,labels=items.map((i,n)=>p.phone?String(n+1):wrapChartLabel(i.name,maxChars));
  const maxLines=Math.max(1,...labels.map(l=>Array.isArray(l)?l.length:1)),row=p.phone?29+maxLines*9:(p.tablet?27+maxLines*8:24+maxLines*7),height=Math.max(p.phone?265:230,Math.min(760,items.length*row+50));
  const datasets=stackKeys.map(key=>({
    label:stackLabels[key]||key,
    data:items.map(item=>item.stacks[key]||0),
    backgroundColor:stackColors[key]||'#999',
    borderRadius:p.phone?6:8,
    borderSkipped:false,
    barThickness:p.phone?13:16
  }));
  mountChart(el,{type:'bar',data:{labels,datasets},options:{indexAxis:'y',layout:{padding:{top:6,right:p.phone?45:72,left:0,bottom:2}},scales:{...chartScales(true),x:{...chartScales(true).x,stacked:true},y:{...chartScales(true).y,stacked:true}},plugins:{legend:{display:!p.phone,position:'bottom',labels:{usePointStyle:true,pointStyle:'circle',boxWidth:7,padding:p.phone?8:11,font:{size:p.phone?8:9}}},datalabels:{display:true,color:'#171720',anchor:'end',align:'right',clamp:true,clip:false,font:{size:p.phone?9:10,weight:'700'},formatter:(v,c)=>{const item=items[c.dataIndex];const total=Object.values(item.stacks||{}).reduce((a,b)=>a+b,0);return total?`${v} (${Math.round(v/total*100)}%)`:''}},tooltip:{...chartTooltip(),callbacks:{title:c=>items[c[0].dataIndex].name,label:c=>`${c.dataset.label}: ${c.raw} (${c.raw>0?Math.round(c.raw/items[c[0].dataIndex].stacks[c.dataset.label]*100):0}%)`}}}}},height);
  renderMobileCategoryKey(el,items);
}
function stacked(el,labels,distData){
  const p=viewportProfile(),displayLabels=labels.map(compactDate);
  const datasets=DATA.districts.map(d=>({label:d,data:labels.map(l=>distData[l][d]),backgroundColor:DIST_COLORS[d]||'#9ca3af',borderColor:'#fff',borderWidth:1,borderRadius:4,borderSkipped:false}));
  mountChart(el,{type:'bar',data:{labels:displayLabels,datasets},options:{scales:{x:{stacked:true,grid:{display:false},ticks:{font:{size:p.phone?9:10},color:'#77716a',maxRotation:0}},y:{stacked:true,beginAtZero:true,grid:{color:'#ece6dc'},ticks:{font:{size:p.phone?9:10},color:'#77716a',maxTicksLimit:p.phone?6:8}}},plugins:{datalabels:{display:false},tooltip:{...chartTooltip(),callbacks:{title:c=>labels[c[0].dataIndex],label:c=>`${c.dataset.label}: ${c.raw}`}}}}},p.phone?220:240);
}
function doughnutChart(el,labels,vals){
  const p=viewportProfile(),displayLabels=labels.map(l=>p.phone?String(l).split('·')[0].trim():l);
  const colors=['#6246ea','#246bfd','#078a52','#f0a202','#e84d5b','#9a62db','#20a4a7','#ff8a65','#697386','#b8a5ff','#65c18c','#ffd166'];
  mountChart(el,{type:'doughnut',data:{labels:displayLabels,datasets:[{data:vals,backgroundColor:colors.slice(0,labels.length),borderColor:'#fff',borderWidth:p.phone?2:3,hoverOffset:7}]},options:{cutout:p.phone?'66%':'62%',layout:{padding:{top:4,right:4,bottom:4,left:4}},plugins:{legend:{display:true,position:'bottom',labels:{usePointStyle:true,pointStyle:'circle',boxWidth:7,padding:p.phone?8:11,font:{size:p.phone?8:9}}},datalabels:{display:c=>c.dataset.data[c.dataIndex]>=3,color:'#fff',font:{size:p.phone?9:10,weight:'800'},formatter:v=>v},tooltip:{...chartTooltip(),callbacks:{label:c=>`${labels[c.dataIndex]}: ${c.raw} รายการ`}}}}},p.phone?290:330);
}

// ---- renderers ----
const KI={
  masks:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M3 12h4l2.2-5 4.1 10 2.3-5H21"/><circle cx="12" cy="12" r="9" opacity=".28"/></svg></span>`,
  trend:`<span class="kico"><svg viewBox="0 0 24 24"><path d="m4 17 5-5 4 3 7-8"/><path d="M15 7h5v5"/></svg></span>`,
  speed:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M13 2 5 13h6l-1 9 9-13h-6Z"/></svg></span>`,
  hospital:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M5 21V5h14v16M3 21h18M9 9h6M12 6v6M9 15h2M14 15h2M10 21v-3h4v3"/></svg></span>`,
  ratio:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M12 3v18M5 7h14M5 7l-3 6h6L5 7ZM19 7l-3 6h6l-3-6Z"/></svg></span>`,
  shield:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.5c0 4.8 3.2 8 7.5 9.5 4.3-1.5 7.5-4.7 7.5-9.5V6Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg></span>`,
  check:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg></span>`,
  clock:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg></span>`,
  flag:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z"/></svg></span>`,
  answer:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg></span>`,
  newcase:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm0-4h-2V7h2v8z"/></svg></span>`,
  completion:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></span>`,
  topdistrict:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg></span>`,
  alert:`<span class="kico"><svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg></span>`
};
function renderKPI(){
  const u=selUnits();const {idx,m,c}=totalsFor(u);
  const last=m[m.length-1]||0,first=m[0]||0;
  const net=last-first;
  let g=0,cnt=0;for(let i=1;i<idx.length;i++){const base=m[i-1]||1;g+=100*(m[i]-base)/base;cnt++;}
  const avg=cnt?Math.round(g/cnt*10)/10:0;
  const lastIdx=idx[idx.length-1];
  const present=u.filter(x=>x.masks[lastIdx]>0).length;
  const ratio=(c[c.length-1])?(Math.round(last/c[c.length-1]*100)/100):0;
  // New KPIs from status/action (use latest day index)
  const completed=u.filter(x=>x.status_completed[lastIdx]>0).length;
  const pendingReview=u.filter(x=>x.status_pending[lastIdx]>0||x.status_in_progress[lastIdx]>0).length;
  const actionReq=u.filter(x=>x.action_data_corrected[lastIdx]>0||x.action_other[lastIdx]>0).length;
  // Additional KPIs
  const ansTotal=u.reduce((s,x)=>s+(x.ans[lastIdx]||0),0);
  const ansRate=last?Math.round(ansTotal/last*10000)/100:0;
  const newCases=u.filter(x=>x.masks[lastIdx]>0 && (lastIdx===0 || x.masks[lastIdx-1]===0)).length;
  const completionRate=present?Math.round(completed/present*10000)/100:0;
  // Top district by masks
  const distMasks={};
  u.forEach(x=>{distMasks[x.dist]=(distMasks[x.dist]||0)+x.masks[lastIdx];});
  const topDist=Object.entries(distMasks).sort((a,b)=>b[1]-a[1])[0];
  const topDistName=topDist?topDist[0]:'-';
  const topDistVal=topDist?topDist[1]:0;
  // Alert: units with unexpected drop
  const alertUnits=u.filter(x=>{
    if(lastIdx===0) return false;
    const prev=x.masks[lastIdx-1]||0;
    const cur=x.masks[lastIdx]||0;
    return prev>0 && cur<prev && (prev-cur)>=3; // drop >= 3
  }).length;
  
  const box=document.getElementById('kpiBox');
  box.innerHTML=`
   <div class="kpi masks"><div class="kpi-top">${KI.masks}<span class="kmini">MASKS</span></div><div class="v a">${last}</div><div class="l">รวม${state.dist!=='all'?' · '+state.dist:''} · ${DATA.labels[lastIdx]}</div></div>
   <div class="kpi delta"><div class="kpi-top">${KI.trend}<span class="kmini">DELTA</span></div><div class="v g">${net>=0?'+':''}${net}</div><div class="l">เพิ่มขึ้นสุทธิในช่วงที่เลือก</div></div>
   <div class="kpi growth"><div class="kpi-top">${KI.speed}<span class="kmini">GROWTH</span></div><div class="v a">${avg}%</div><div class="l">อัตราเติบโตเฉลี่ยต่อวัน</div></div>
   <div class="kpi units"><div class="kpi-top">${KI.hospital}<span class="kmini">UNITS</span></div><div class="v">${present}</div><div class="l">หน่วยบริการที่มีข้อมูลล่าสุด</div></div>
   <div class="kpi ratio"><div class="kpi-top">${KI.ratio}<span class="kmini">RATIO</span></div><div class="v am">${ratio}</div><div class="l">Masks ต่อประชาชนโดยรวม</div></div>
   <div class="kpi quality"><div class="kpi-top">${KI.shield}<span class="kmini">QUALITY</span></div><div class="v">100%</div><div class="l">ข้อมูลจับคู่สำเร็จทุกหน่วย</div></div>
   <div class="kpi completed"><div class="kpi-top">${KI.check}<span class="kmini">ตรวจเสร็จสิ้น</span></div><div class="v g">${completed}</div><div class="l">${present>0?Math.round(completed/present*100):0}% ของหน่วยที่มีข้อมูล</div></div>
   <div class="kpi pending"><div class="kpi-top">${KI.clock}<span class="kmini">รอดำเนินการ</span></div><div class="v am">${pendingReview}</div><div class="l">${present>0?Math.round(pendingReview/present*100):0}% รอ/กำลังตรวจ</div></div>
   <div class="kpi action"><div class="kpi-top">${KI.flag}<span class="kmini">ต้องติดตาม</span></div><div class="v a">${actionReq}</div><div class="l">${present>0?Math.round(actionReq/present*100):0}% มีการแก้ไข/ดำเนินการอื่น</div></div>
   <div class="kpi answered"><div class="kpi-top">${KI.answer}<span class="kmini">ANSWERED RATE</span></div><div class="v g">${ansRate}%</div><div class="l">ตอบกลับ ${ansTotal}/${last} (${ansRate}%)</div></div>
   <div class="kpi newcase"><div class="kpi-top">${KI.newcase}<span class="kmini">NEW TODAY</span></div><div class="v a">${newCases}</div><div class="l">หน่วยบริการใหม่ในวันล่าสุด</div></div>
   <div class="kpi completion"><div class="kpi-top">${KI.completion}<span class="kmini">COMPLETION %</span></div><div class="v g">${completionRate}%</div><div class="l">${completed}/${present} หน่วยตรวจเสร็จ</div></div>
   <div class="kpi topdistrict"><div class="kpi-top">${KI.topdistrict}<span class="kmini">TOP DISTRICT</span></div><div class="v">${topDistVal}</div><div class="l">${topDistName} มียอดสูงสุด</div></div>
   <div class="kpi alert"><div class="kpi-top">${KI.alert}<span class="kmini">ALERT</span></div><div class="v a">${alertUnits}</div><div class="l">หน่วยมียอดลด ≥3 เคส</div></div>`;
}
function renderProvince(){
  const zone=document.getElementById('provinceZone');if(!PROVINCE){zone.hidden=true;return;}
  zone.hidden=false;const p=PROVINCE.province,fmt=n=>Number(n).toLocaleString('th-TH'),signed=n=>(n>0?'+':'')+n;
  document.getElementById('provinceTitle').textContent=`${p.province_name} · รอบ ${PROVINCE.snapshot_label}`;
  document.getElementById('provinceSubtitle').textContent=PROVINCE.detail_aligned?`มีข้อมูลจังหวัดและรายละเอียด ${p.hospitals} หน่วยบริการถึงวันที่ ${PROVINCE.detail_latest_label} รอบ ${PROVINCE.detail_latest_time}`:'ภาพรวมระดับจังหวัด ใช้เสริมข้อมูลรายละเอียดหน่วยบริการของวันก่อนหน้า';
  document.getElementById('provinceStamp').textContent=`อันดับ ${p.rank}/${p.national_count} ประเทศ`;
  // Calculate completion rate from facility data (use filtered units and latest selected day)
  const lastIdx=activeIdx().slice(-1)[0];
  const unitsWithData=selUnits().filter(u=>u.masks[lastIdx]>0);
  const completedUnits=unitsWithData.filter(u=>u.status_completed[lastIdx]>0).length;
  const completionRate=unitsWithData.length?Math.round(completedUnits/unitsWithData.length*10000)/100:0;
  document.getElementById('provinceKpis').innerHTML=`
    <div class="prov-kpi"><span class="lab">CASES · เคส</span><b class="val">${fmt(p.masks)}</b><small>${signed(p.delta_masks)} เทียบ ${PROVINCE.baseline_label}</small></div>
    <div class="prov-kpi"><span class="lab">CITIZENS · คน</span><b class="val">${fmt(p.citizens)}</b><small>${signed(p.delta_citizens)} เทียบ ${PROVINCE.baseline_label}</small></div>
    <div class="prov-kpi"><span class="lab">ANSWERED · ตอบกลับ</span><b class="val">${fmt(p.answered)}</b><small>${signed(p.delta_answered)} เทียบ ${PROVINCE.baseline_label}</small></div>
    <div class="prov-kpi"><span class="lab">RESPONSE RATE</span><b class="val">${p.answer_rate.toFixed(2)}%</b><small>ตอบกลับ ÷ เคส</small></div>
    <div class="prov-kpi"><span class="lab">MATCH QUALITY</span><b class="val">${Number(p.match_rate_pct).toFixed(1)}%</b><small>${fmt(p.matched)} matched · ${fmt(p.unmatched)} unmatched</small></div>
    <div class="prov-kpi"><span class="lab">REGION 12</span><b class="val">${p.region_rank}/${p.region_count}</b><small>${PROVINCE.region.province_share_pct.toFixed(2)}% ของเคสเขต</small></div>
    <div class="prov-kpi"><span class="lab">COMPLETION RATE</span><b class="val">${completionRate.toFixed(2)}%</b><small>หน่วยที่ตรวจเสร็จสิ้น / ทั้งหมด</small></div>`;
  const gap=PROVINCE.region.answer_rate-p.answer_rate,nationalGap=PROVINCE.national.answer_rate-p.answer_rate;
  const last=DATA.labels.length-1,prev=Math.max(0,last-1),changes=DATA.units.map(u=>({name:u.name,delta:u.masks[last]-u.masks[prev]})).filter(x=>x.delta!==0).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta));
  const changeText=changes.length?` หน่วยที่เปลี่ยนแปลงสูงสุดคือ ${changes[0].name} ${signed(changes[0].delta)} เคส`:' ไม่พบหน่วยที่มียอดเคสเปลี่ยนแปลง';
  const dg=PROVINCE.detail_gap,dt=PROVINCE.detail_totals,reconcile=dg.citizens===0?'ยอดคนระดับจังหวัดและผลรวมรายหน่วยเท่ากัน':`ยอดคนระดับจังหวัด ${fmt(p.citizens)} คน ขณะที่ผลรวมรายหน่วย ${fmt(dt.citizens)} คน (ต่างกัน ${signed(dg.citizens)} เนื่องจากคนเดียวอาจรับบริการหลายหน่วย)`;
  document.getElementById('provinceInsight').textContent=`สัญญาณล่าสุด: เคส ${signed(p.delta_masks)} แต่ตอบกลับ ${signed(p.delta_answered)} ทำให้อัตราตอบกลับอยู่ที่ ${p.answer_rate.toFixed(2)}% ต่ำกว่าค่าเฉลี่ยเขต ${gap.toFixed(2)} จุด และประเทศ ${nationalGap.toFixed(2)} จุด.${changeText} เคสและตอบกลับระดับจังหวัดตรงกับผลรวมรายหน่วย; ${reconcile}`;
}
function renderTrend(){
  const u=selUnits();const {idx,m,c}=totalsFor(u);
  const labs=idx.map(i=>DATA.labels[i]);
  lineChart(document.getElementById('trendChart'),labs,[{name:'Masks',color:css('--accent'),vals:m},{name:'ประชาชน',color:css('--green'),vals:c}]);
}
function renderNet(){
  const u=selUnits();const {idx,m}=totalsFor(u);
  const deltas=[];for(let i=1;i<idx.length;i++)deltas.push(m[i]-m[i-1]);
  const labs=idx.slice(1).map(i=>DATA.labels[i]);
  barChart(document.getElementById('netChart'),labs,deltas);
}
function renderStack(){
  const idx=activeIdx();const labs=idx.map(i=>DATA.labels[i]);
  stacked(document.getElementById('stackChart'),labs,DATA.distDay);
  // สรุปรวมรายอำเภอ (แทนตารางที่ซ้ำกับกราฟ)
  let rows=DATA.districts.map(d=>{
    const per=idx.map(i=>DATA.distDay[DATA.labels[i]][d]);
    const tot=per.reduce((a,b)=>a+b,0);
    return {d,per,tot};
  }).sort((a,b)=>b.tot-a.tot);
  let html='<div class="dsumwrap"><table><thead><tr><th>อำเภอ</th>'+
    labs.map(l=>`<th>${l}</th>`).join('')+'<th>รวม</th></tr></thead><tbody>';
  rows.forEach(r=>{const dim=(state.dist!=='all'&&state.dist!==r.d)?'opacity:.45':'';
    html+=`<tr style="${dim}"><td>${r.d}</td>${r.per.map(v=>`<td class="num">${v}</td>`).join('')}<td class="num strong">${r.tot}</td></tr>`;});
  html+='</tbody></table></div>';
  document.getElementById('distSum').innerHTML=html;
}
function renderPareto(){
  const u=selUnits();const lastIdx=activeIdx().slice(-1)[0];
  const ranked=u.map(x=>({x,v:x.masks[lastIdx]})).sort((a,b)=>b.v-a.v);
  const tot=ranked.reduce((s,o)=>s+o.v,0)||1;
  let cum=0;const items=ranked.slice(0,8).map(o=>{
    cum+=o.v;
    // Add status badge info
    const unit=o.x;
    const primaryStatus=getPrimaryStatus(unit, lastIdx);
    const primaryAction=getPrimaryAction(unit, lastIdx);
    return {name:o.x.name,val:o.v,extra:`(${Math.round(100*cum/tot)}%)`,suffix:'',primaryStatus,primaryAction};
  });
  hbar(document.getElementById('paretoChart'),items);
}
function renderMom(){
  const u=selUnits();const idx=activeIdx();
  const items=u.map(x=>{const f=x.masks[idx[0]],l=x.masks[idx[idx.length-1]];
    return {x,f,l,d:l-f};}).filter(o=>o.d>0).sort((a,b)=>b.d-a.d)
    .map(o=>{
      const lastIdx=idx[idx.length-1];
      const hasCorrection=o.x.action_data_corrected[lastIdx]>0;
      return {name:o.x.name,val:o.d,extra:`(${o.f}→${o.l})`,suffix:'',hasCorrection};
    });
  if(!items.length){document.getElementById('momChart').innerHTML='<div class="mut">ไม่มีหน่วยใดเพิ่มขึ้นในช่วงที่เลือก</div>';return;}
  hbar(document.getElementById('momChart'),items);
}
function renderRatio(){
  const u=selUnits();const lastIdx=activeIdx().slice(-1)[0];
  const items=u.map(x=>({x,r:(x.cit[lastIdx]?Math.round(x.masks[lastIdx]/x.cit[lastIdx]*100)/100:0),m:x.masks[lastIdx],c:x.cit[lastIdx]}))
    .sort((a,b)=>b.r-a.r).slice(0,8)
    .map(o=>({name:o.x.name,val:o.r,extra:`(${o.m}/${o.c})`,suffix:''}));
  hbar(document.getElementById('ratioChart'),items);
}
function renderAns(){
  // สรุปรวม answered ต่อวัน (เฉพาะวันที่มีคอลัมน์ answered ในไฟล์)
  const idx=activeIdx();
  const labs=idx.map(i=>DATA.labels[i]);
  const enc=idx.map(i=>DATA.totEnc[i]||0);
  const ans=idx.map(i=>DATA.totAns[i]||0);
  lineChart(document.getElementById('ansChart'),labs,[{name:'encounters',color:css('--accent'),vals:enc},{name:'answered',color:css('--green'),vals:ans}]);
  const lastIdx=idx[idx.length-1];
  const tEnc=DATA.totEnc[lastIdx]||0, tAns=DATA.totAns[lastIdx]||0;
  const rate=tEnc?Math.round(tAns/tEnc*100):0;
  document.getElementById('ansInsight').innerHTML=`<b>สรุปวันล่าสุด (${DATA.labels[lastIdx]}):</b> ตอบกลับ ${tAns} จาก ${tEnc} การเข้าเยี่ยม (${rate}%) · หน่วยที่ตอบกลับ: ${DATA.units.filter(u=>u.ans[lastIdx]>0).length}/${DATA.units.filter(u=>u.enc[lastIdx]>0||u.masks[lastIdx]>0).length} แห่ง`;
  const ins4=document.getElementById('ins4');
  if(ins4)ins4.innerHTML=`<b>4. คุณภาพและตอบกลับ:</b> Match rate 100% ตลอด 4 วัน · วันล่าสุดตอบกลับ ${tAns}/${tEnc} (${rate}%)`;
}
function unitResponseMetrics(unit,latestIdx,baselineIdx){
  const masks=unit.masks[latestIdx]||0,answered=unit.ans[latestIdx]||0;
  const baselineAnswered=baselineIdx===null?null:(unit.ans[baselineIdx]||0);
  return {unit,masks,answered,pending:Math.max(0,masks-answered),delta:baselineAnswered===null?null:answered-baselineAnswered,rate:masks?answered/masks*100:null,anomaly:answered>masks};
}
function clearUnitResponseChart(message){
  const el=document.getElementById('unitResponseChart');
  if(CHARTS[el.id]){CHARTS[el.id].destroy();delete CHARTS[el.id];}
  const key=document.querySelector(`[data-chart-key="${el.id}"]`);if(key)key.remove();
  el.className='chartbox';el.style.height='auto';el.innerHTML=`<div class="response-empty">${message}</div>`;
}
function renderUnitResponse(){
  const idx=activeIdx(),latestIdx=idx[idx.length-1],baselineIdx=idx.length>1?idx[idx.length-2]:null;
  const metrics=selUnits().map(u=>unitResponseMetrics(u,latestIdx,baselineIdx));
  const active=metrics.filter(m=>m.masks>0),responding=active.filter(m=>m.answered>0).length;
  const answered=active.reduce((s,m)=>s+m.answered,0),pending=active.reduce((s,m)=>s+m.pending,0);
  const positiveDelta=baselineIdx===null?null:metrics.reduce((s,m)=>s+Math.max(0,m.delta||0),0);
  const revisions=baselineIdx===null?0:metrics.filter(m=>(m.delta||0)<0).length,anomalies=metrics.filter(m=>m.anomaly).length;
  document.getElementById('unitResponseKpis').innerHTML=`
    <div class="response-kpi"><span class="lab">RESPONDING UNITS</span><b class="val">${responding}/${active.length}</b><small>หน่วยที่ตอบแล้ว</small></div>
    <div class="response-kpi"><span class="lab">ANSWERED</span><b class="val">${answered}</b><small>ตอบกลับรวม ณ ${DATA.labels[latestIdx]}</small></div>
    <div class="response-kpi"><span class="lab">NEW REPLIES</span><b class="val">${positiveDelta===null?'—':'+'+positiveDelta}</b><small>${baselineIdx===null?'ไม่มีฐานเปรียบเทียบ':'เทียบ '+DATA.labels[baselineIdx]}</small></div>
    <div class="response-kpi"><span class="lab">PENDING</span><b class="val">${pending}</b><small>เคสที่ยังไม่ตอบ</small></div>`;
  document.querySelectorAll('[data-response-mode]').forEach(button=>{const on=button.dataset.responseMode===state.responseMode;button.classList.toggle('on',on);button.setAttribute('aria-pressed',String(on));});
  if(!active.length){clearUnitResponseChart('ไม่มีหน่วยบริการที่มีเคสในพื้นที่และช่วงวันที่เลือก');document.getElementById('unitResponseInsight').textContent='ไม่มีข้อมูลสำหรับคำนวณมิติการตอบกลับ';return;}
  if(state.responseMode==='delta'&&baselineIdx===null){clearUnitResponseChart('เลือกอย่างน้อย 2 วันเพื่อดูจำนวนตอบกลับที่เพิ่มขึ้นจากรอบก่อน');document.getElementById('unitResponseInsight').textContent='มุมมองเพิ่มขึ้นรอบล่าสุดต้องมีข้อมูลอย่างน้อย 2 snapshot';return;}
  const valueFor=m=>state.responseMode==='answered'?m.answered:state.responseMode==='delta'?Math.max(0,m.delta||0):m.pending;
  const ranked=metrics.filter(m=>valueFor(m)>0).sort((a,b)=>valueFor(b)-valueFor(a)||(b.rate||0)-(a.rate||0)||a.unit.name.localeCompare(b.unit.name,'th'));
  if(!ranked.length){const empty=state.responseMode==='delta'?'ไม่มีหน่วยบริการที่มีจำนวนตอบกลับเพิ่มขึ้นในรอบล่าสุด':state.responseMode==='pending'?'ทุกหน่วยตอบกลับครบแล้ว':'ยังไม่มีหน่วยบริการที่ตอบกลับ';clearUnitResponseChart(empty);document.getElementById('unitResponseInsight').textContent=empty;return;}

  // Build stacked items for answered mode
  if(state.responseMode==='answered'){
    const items=ranked.slice(0,8).map(m=>{
      const unit=m.unit;
      const completed=unit.status_completed[latestIdx]||0;
      const inProgress=unit.status_in_progress[latestIdx]||0;
      const pendingStatus=unit.status_pending[latestIdx]||0;
      const otherStatus=(unit.status_no_error_found[latestIdx]||0)+(unit.status_not_recorded[latestIdx]||0);
      const total=completed+inProgress+pendingStatus+otherStatus;
      return {
        name:m.unit.name,
        stacks:{
          status_completed:completed,
          status_in_progress:inProgress,
          status_pending:pendingStatus,
          status_other:otherStatus
        },
        extra:`(${m.answered}/${m.masks})`,
        keyDetail:`ตอบ ${m.answered}/${m.masks}`,
        tooltipExtra:`ตอบ ${m.answered}/${m.masks}`
      };
    });
    const stackKeys=['status_completed','status_in_progress','status_pending','status_other'];
    const stackColors={
      status_completed:'#078a52',
      status_in_progress:'#246bfd',
      status_pending:'#f0a202',
      status_other:'#9a62db'
    };
    const stackLabels={
      status_completed:'ตรวจเสร็จสิ้น',
      status_in_progress:'อยู่ระหว่างตรวจสอบ',
      status_pending:'รอตรวจสอบ',
      status_other:'อื่นๆ'
    };
    hbarStacked(document.getElementById('unitResponseChart'),items,stackKeys,stackColors,stackLabels);
  }else{
    const items=ranked.slice(0,8).map(m=>{const rate=m.rate===null?'—':Math.round(m.rate*10)/10+'%';
      const extra=`(${m.answered}/${m.masks})`,keyDetail=`ตอบ ${m.answered}/${m.masks} · ${rate}`;
      const tooltipExtra=state.responseMode==='answered'?`ตอบ ${m.answered}/${m.masks} · ${rate}`:state.responseMode==='delta'?`ตอบเพิ่ม ${Math.max(0,m.delta||0)} · รวม ${m.answered}/${m.masks} · ${rate}`:`คงค้าง ${m.pending} · ตอบ ${m.answered}/${m.masks} · ${rate}`;
      const color=state.responseMode==='pending'?'#e84d5b':m.rate===100?'#078a52':m.rate&&m.rate>0?'#d98b00':'#e84d5b';
      return {name:m.unit.name,val:valueFor(m),extra,keyDetail:keyDetail,tooltipExtra:tooltipExtra,color};});
    hbar(document.getElementById('unitResponseChart'),items);
  }
  const lead=ranked[0],leadValue=valueFor(lead),modeLabel=state.responseMode==='answered'?'ตอบกลับสูงสุด':state.responseMode==='delta'?'ตอบเพิ่มสูงสุด':'คงค้างสูงสุด';
  const notes=[`${modeLabel}: ${lead.unit.name} ${leadValue} เคส`,`ตอบแล้ว ${answered}/${active.reduce((s,m)=>s+m.masks,0)} เคส · คงค้าง ${pending} เคส`];
  if(revisions)notes.push(`พบ ${revisions} หน่วยที่ยอดตอบกลับลดลงจากการปรับข้อมูล`);if(anomalies)notes.push(`⚠️ พบ ${anomalies} หน่วยที่ answered มากกว่า masks`);
  document.getElementById('unitResponseInsight').innerHTML=`<b>${DATA.labels[latestIdx]}:</b> ${notes.join(' · ')}`;
}
const ICD_CHAPTERS={Z:'ปัจจัยสุขภาพ/บริการ',U:'รหัสวัตถุประสงค์พิเศษ',M:'กล้ามเนื้อและกระดูก',K:'ระบบย่อยอาหาร/ช่องปาก',F:'จิตและพฤติกรรม',J:'ระบบหายใจ',E:'ต่อมไร้ท่อ/เมแทบอลิซึม',G:'ระบบประสาท',S:'การบาดเจ็บ',X:'สาเหตุภายนอก',L:'ผิวหนัง',R:'อาการและอาการแสดง'};
function renderICD(){
  const units=ICD10.units.filter(u=>state.dist==='all'||u.district===state.dist);
  const agg=new Map(),chapters=new Map();
  let total=0,hidden=0,reports=0;
  units.forEach(u=>{hidden+=u.hidden_code_count||0;reports+=u.reports||0;u.diagnoses.forEach(d=>{
    total+=d.count;const old=agg.get(d.code)||{code:d.code,label:d.label,count:0};old.count+=d.count;agg.set(d.code,old);
    const ch=d.code[0];chapters.set(ch,(chapters.get(ch)||0)+d.count);
  });});
  const ranked=[...agg.values()].sort((a,b)=>b.count-a.count||a.code.localeCompare(b.code));
  const z=chapters.get('Z')||0,uSpecial=chapters.get('U')||0;
  const zShare=total?Math.round(z/total*1000)/10:0;
  document.getElementById('icdKpis').innerHTML=`
    <div class="icd-kpi"><span class="lab">VISIBLE CODES</span><b class="val">${ranked.length}</b><small>รหัสไม่ซ้ำที่มองเห็น</small></div>
    <div class="icd-kpi"><span class="lab">DIAGNOSIS ITEMS</span><b class="val">${total}</b><small>รายการวินิจฉัยที่แสดง</small></div>
    <div class="icd-kpi"><span class="lab">SERVICE UNITS</span><b class="val">${units.length}</b><small>หน่วยในพื้นที่ที่เลือก</small></div>
    <div class="icd-kpi"><span class="lab">Z-CATEGORY</span><b class="val">${zShare}%</b><small>คัดกรอง/บริการสุขภาพ</small></div>`;
  const top=ranked.slice(0,10).map(d=>({name:`${d.code} · ${d.label}`,val:d.count,extra:'รายการ'}));
  hbar(document.getElementById('icdTopChart'),top);
  const chap=[...chapters.entries()].sort((a,b)=>b[1]-a[1]);
  const shown=chap.slice(0,4),other=chap.slice(4).reduce((s,x)=>s+x[1],0);
  const chapterLabels=shown.map(([c])=>`${c} · ${ICD_CHAPTERS[c]||'หมวดอื่น'}`),chapterVals=shown.map(x=>x[1]);
  if(other){chapterLabels.push('อื่นๆ');chapterVals.push(other);}
  doughnutChart(document.getElementById('icdChapterChart'),chapterLabels,chapterVals);
  document.getElementById('icdSourceNote').innerHTML=`⚠️ <b>ขอบเขตข้อมูล:</b> ถอดจากภาพวันที่ ${ICD10.snapshot_date} และนับเฉพาะรหัสที่มองเห็น · ${hidden?`มีอีก ${hidden} รหัสที่ภาพระบุแต่ไม่แสดงรายละเอียด จึงไม่ถูกนำมาคำนวณ`:'ไม่พบข้อความรหัสที่ซ่อน'} · จำนวนรายการอาจมากกว่า encounter เพราะหนึ่งครั้งรับบริการมีได้หลาย diagnosis`;
  document.querySelector('#icdTable tbody').innerHTML=units.slice().sort((a,b)=>b.diagnoses.reduce((s,d)=>s+d.count,0)-a.diagnoses.reduce((s,d)=>s+d.count,0)).map(u=>{
    const n=u.diagnoses.reduce((s,d)=>s+d.count,0);
    const codes=u.diagnoses.map(d=>`<span class="icd-code">${d.code} <b>${d.count}</b></span>`).join('');
    const detail=u.diagnoses.map(d=>`<span class="icd-mini"><b>${d.code}</b> — ${d.label}</span>`).join('');
    return `<tr><td>${u.name}<span class="icd-mini">รหัสหน่วย ${u.code}</span></td><td class="mut">${u.district}</td><td>${u.diagnoses.length}${u.hidden_code_count?` <span class="c-new">+${u.hidden_code_count} ซ่อน</span>`:''}</td><td class="num strong">${n}</td><td>${codes}${detail}</td></tr>`;
  }).join('');
  const top3=ranked.slice(0,3),top3Count=top3.reduce((s,d)=>s+d.count,0),top3Share=total?Math.round(top3Count/total*1000)/10:0;
  const unitRank=units.map(x=>({x,n:x.diagnoses.reduce((s,d)=>s+d.count,0)})).sort((a,b)=>b.n-a.n);
  const lead=unitRank[0],clinical=total-z-uSpecial,perReport=reports?Math.round(total/reports*100)/100:0;
  document.getElementById('icdInsights').innerHTML=`
    <div class="insight a"><b>1. ภาพรวมบริการเชิงป้องกัน:</b> กลุ่ม Z มี ${z}/${total} รายการ (${zShare}%) สะท้อนว่าข้อมูลชุดนี้เน้นการคัดกรอง การให้คำปรึกษา และการติดตาม มากกว่าภาระโรคที่ยืนยันแล้ว</div>
    <div class="insight"><b>2. รหัสหลัก:</b> ${top3.map(d=>`${d.code} ${d.count}`).join(' · ')} รวม ${top3Count} รายการ (${top3Share}%) โดย ${ranked[0]?.code||'-'} พบสูงสุด</div>
    <div class="insight g"><b>3. การกระจุกตัวรายหน่วย:</b> ${lead?`${lead.x.name} มี ${lead.n} รายการที่มองเห็น (${Math.round(lead.n/total*1000)/10}% ของพื้นที่ที่เลือก)`:'ไม่มีข้อมูล'} ควรอ่านควบคู่กับจำนวน encounter และรูปแบบงานคัดกรองของหน่วย</div>
    <div class="insight"><b>4. Clinical signals นอก Z/U:</b> พบ ${clinical} รายการ ครอบคลุมสุขภาพจิต ทางเดินหายใจ ช่องปาก กล้ามเนื้อและกระดูก ผิวหนัง และอาการทั่วไป เป็นสัญญาณสำหรับติดตาม ไม่ใช่อัตราป่วย</div>
    <div class="insight a"><b>5. ข้อควรระวัง:</b> อัตราที่เห็นอย่างน้อย ${perReport} diagnosis ต่อรายงาน และยังมี ${hidden} รหัสไม่เปิดเผย ห้ามตีความเป็น prevalence หรือจำนวนผู้ป่วยไม่ซ้ำโดยตรง ควรใช้ข้อมูลระดับ encounter/patient ยืนยันก่อนตัดสินใจเชิงนโยบาย</div>`;
}
function renderUnitTable(){
  let u=selUnits().slice();
  const k=state.sortKey,dir=state.sortDir,lastIdx=activeIdx().slice(-1)[0];
  const metric=x=>unitResponseMetrics(x,lastIdx,null);
  u.sort((a,b)=>{
    if(k==='name')return dir*a.name.localeCompare(b.name,'th');
    if(k==='dist')return dir*a.dist.localeCompare(b.dist,'th');
    if(k==='last')return dir*(a.masks[lastIdx]-b.masks[lastIdx]);
    if(k==='answered')return dir*(metric(a).answered-metric(b).answered);
    if(k==='pending')return dir*(metric(a).pending-metric(b).pending);
    if(k==='responseRate')return dir*((metric(a).rate??-1)-(metric(b).rate??-1));
    return 0;
  });
  const head=['หน่วยบริการ','อำเภอ',...activeIdx().map(i=>DATA.labels[i]),'ล่าสุด','ตอบกลับ','ยังไม่ตอบ','อัตราตอบกลับ','สถานะ','การดำเนินการ'].map((h,i)=>{
    const arr=state.sortKey===colName(i)?' <span class="arr">'+(state.sortDir>0?'▲':'▼')+'</span>':'';
    return '<th data-col="'+i+'">'+h+arr+'</th>';
  }).join('');
  document.querySelector('#unitTable thead').innerHTML='<tr>'+head+'</tr>';
  const rows=u.map(x=>{
    const idx=activeIdx();
    let cells='';
    idx.forEach(i=>{
      let txt,cls;
      if(i===idx[0]){txt=x.masks[i];cls='c-base';}
      else{const dm=x.masks[i]-(x.masks[i-1]||0);
        if(x.masks[i]&&!x.masks[i-1]){txt='+'+x.masks[i];cls='c-new';}
        else if(dm>0){txt='+'+dm;cls='c-up';}
        else if(dm<0){txt=''+dm;cls='c-down';}
        else{txt='0';cls='c-flat';}}
      cells+='<td class="num '+cls+'">'+txt+'</td>';
    });
    const response=metric(x),rate=response.rate===null?'—':Math.round(response.rate*10)/10+'%';
    // Build status badges
    const statusFields = [
      {key:'status_pending', label:'รอตรวจสอบ'},
      {key:'status_in_progress', label:'อยู่ระหว่างตรวจสอบ'},
      {key:'status_completed', label:'ตรวจเสร็จสิ้น'},
      {key:'status_no_error_found', label:'ไม่พบข้อผิดพลาด'},
      {key:'status_not_recorded', label:'ยังไม่บันทึก'}
    ];
    const actionFields = [
      {key:'action_none_yet', label:'ยังไม่ดำเนินการ'},
      {key:'action_data_corrected', label:'แก้ไขข้อมูลแล้ว'},
      {key:'action_other', label:'ดำเนินการอื่นๆ'},
      {key:'action_not_recorded', label:'ยังไม่บันทึก'}
    ];

    const statusHtml = statusFields.map(f => x[f.key] ? `<span class="badge badge-status" title="${f.label}">${x[f.key]}</span>` : '').join(' ');
    const actionHtml = actionFields.map(f => x[f.key] ? `<span class="badge badge-action" title="${f.label}">${x[f.key]}</span>` : '').join(' ');

    return '<tr><td>'+x.name+'</td><td class="mut">'+x.dist+'</td>'+cells+
      '<td class="num strong">'+response.masks+'</td>'+
      '<td class="num '+(response.answered>0?'c-up':'c-flat')+'">'+response.answered+'</td>'+
      '<td class="num '+(response.pending>0?'c-down':'c-flat')+'">'+response.pending+'</td>'+
      '<td class="num '+(response.rate===100?'c-up':response.rate===0?'c-down':'c-flat')+'">'+rate+'</td>'+
      '<td class="status-cell">'+statusHtml+'</td>'+
      '<td class="action-cell">'+actionHtml+'</td></tr>';
  }).join('');
  document.querySelector('#unitTable tbody').innerHTML=rows;
  document.querySelectorAll('#unitTable th').forEach(th=>{
    th.onclick=()=>{const i=+th.dataset.col;const name=colName(i);
      if(state.sortKey===name)state.sortDir*=-1;else{state.sortKey=name;state.sortDir=1;}
      renderUnitTable();};
  });
}
function colName(i){if(i===0)return 'name';if(i===1)return 'dist';
  const n=activeIdx().length;if(i-2<n)return 'day';if(i===n+2)return 'last';if(i===n+3)return 'answered';if(i===n+4)return 'pending';if(i===n+5)return 'responseRate';return 'last';}

// ---- daily increase report ----
function buildReportNav(){
  const nav=document.getElementById('reportNav');
  const idx=activeIdx();
  // ปุ่ม "ทุกวัน" + ปุ่มแต่ละวัน (ยกเว้นวันแรกที่เป็นฐาน)
  const mk=(label,dayI,on)=>{const b=document.createElement('span');b.className='pill'+(on?' on':'');b.textContent=label;
    b.onclick=()=>{state.reportDay=dayI;document.querySelectorAll('#reportNav .pill').forEach(p=>p.classList.remove('on'));b.classList.add('on');renderReport();};
    nav.appendChild(b);};
  mk('📆 ทุกวัน',-1,true);
  idx.slice(1).forEach(i=>mk(DATA.labels[i],i,false));
  state.reportDay=-1;
}
function renderReport(){
  const idx=activeIdx();
  const daySel=state.reportDay;
  const days=[daySel>=0?daySel:idx[idx.length-1]]; // ทุกวัน = วันสุดท้าย; หรือระบุวัน
  if(daySel<0) days.length=0, idx.slice(1).forEach(i=>days.push(i));
  const targetDays=daySel<0?idx.slice(1):[daySel];
  let html='';
  targetDays.forEach(di=>{
    const prev=di-1;
    const up=[],neu=[],down=[],statusChg=[];
    // Use filtered units (respects district, search, status, action filters)
    selUnits().forEach(u=>{
      const cur=u.masks[di], pv=(di>0)?(u.masks[prev]||0):0;
      if(di===0){if(cur>0)neu.push(u);return;}
      if(cur && !pv){neu.push(u);}
      else{const d=cur-pv; if(d>0)up.push([u,d]); else if(d<0)down.push([u,-d]);}
      // Check status/action changes
      if(di>0){
        const prevStatus=getPrimaryStatusAt(u, prev);
        const currStatus=getPrimaryStatusAt(u, di);
        const prevAction=getPrimaryActionAt(u, prev);
        const currAction=getPrimaryActionAt(u, di);
        if(prevStatus!==currStatus || prevAction!==currAction){
          statusChg.push({u, prevStatus, currStatus, prevAction, currAction});
        }
      }
    });
    up.sort((a,b)=>b[1]-a[1]);
    const dateLabel=DATA.labels[di];
    html+=`<div class="rep-day"><div class="rep-head">📅 ${dateLabel}</div>`;
    html+=repList('🟢 เพิ่มขึ้น',up.map(([u,d])=>`${u.name} <b>+${d}</b> (เป็น ${u.masks[di]})`),'c-up','ไม่มีหน่วยเพิ่มขึ้น');
    html+=repList('🟠 ใหม่',neu.map(u=>`${u.name} <b>+${u.masks[di]}</b> (ปรากฏครั้งแรก)`),'c-new','ไม่มีหน่วยใหม่');
    html+=repList('🔴 ลดลง',down.map(([u,d])=>`${u.name} <b>−${d}</b> (เหลือ ${u.masks[di]})`),'c-down','ไม่มีหน่วยลดลง');
    // Status changes
    html+=repList('🏷️ สถานะเปลี่ยน',statusChg.map(s=>`${s.u.name}: ${statusLabel(s.prevStatus)}→${statusLabel(s.currStatus)} ${actionLabel(s.prevAction)}→${actionLabel(s.currAction)}`),'c-new', 'ไม่มีสถานะเปลี่ยน');
    html+=`</div>`;
  });
  document.getElementById('dailyReport').innerHTML=html;
}
function getPrimaryStatusAt(unit, dayIdx){
  const fields=['status_pending','status_in_progress','status_completed','status_no_error_found','status_not_recorded'];
  let max=-1, primary='all';
  for(const f of fields){
    const arr=unit[f]; if(!arr) continue;
    const v=arr[dayIdx]||0; if(v>max){max=v; primary=f;}
  }
  return max>0?primary:'all';
}
function getPrimaryActionAt(unit, dayIdx){
  const fields=['action_none_yet','action_data_corrected','action_other','action_not_recorded'];
  let max=-1, primary='all';
  for(const f of fields){
    const arr=unit[f]; if(!arr) continue;
    const v=arr[dayIdx]||0; if(v>max){max=v; primary=f;}
  }
  return max>0?primary:'all';
}
function statusLabel(key){
  const map={all:'—',status_pending:'รอตรวจสอบ',status_in_progress:'อยู่ระหว่างตรวจสอบ',status_completed:'ตรวจเสร็จสิ้น',status_no_error_found:'ไม่พบข้อผิดพลาด',status_not_recorded:'ยังไม่บันทึก'};
  return map[key]||key;
}
function actionLabel(key){
  const map={all:'—',action_none_yet:'ยังไม่ดำเนินการ',action_data_corrected:'แก้ไขข้อมูลแล้ว',action_other:'ดำเนินการอื่นๆ',action_not_recorded:'ยังไม่บันทึก'};
  return map[key]||key;
}
function repList(title, items, cssClass, emptyMsg){
  if(!items || items.length===0){
    return `<div class="rep-sec"><span class="rep-badge ${cssClass}">${title}</span><span class="rep-item rep-empty">${emptyMsg}</span></div>`;
  }
  return `<div class="rep-sec"><span class="rep-badge ${cssClass}">${title}</span>${items.map(it=>`<span class="rep-item">${it}</span>`).join('')}</div>`;
}

// ---- controls ----
function buildControls(){
  const dp=document.getElementById('distPills');
  ['all',...DATA.districts].forEach(d=>{
    const b=document.createElement('span');b.className='pill'+(d==='all'?' on':'');
    b.textContent=d==='all'?'ทั้งหมด':d;b.dataset.d=d;
    b.onclick=()=>{state.dist=d;document.querySelectorAll('#distPills .pill').forEach(p=>p.classList.remove('on'));b.classList.add('on');renderAll();};
    dp.appendChild(b);
  });
  const dc=document.getElementById('dayChips');
  DATA.labels.forEach((l,i)=>{const b=document.createElement('span');b.className='chip on';b.textContent=l;b.dataset.i=i;
    b.onclick=()=>{const k=state.days.indexOf(i);if(k>=0){if(state.days.length>1){state.days.splice(k,1);b.classList.remove('on');}}else{state.days.push(i);b.classList.add('on');}
      renderAll();};
    dc.appendChild(b);
  });
  document.getElementById('unitSearch').oninput=e=>{state.search=e.target.value;renderAll();};
  document.querySelectorAll('[data-response-mode]').forEach(button=>{button.onclick=()=>{state.responseMode=button.dataset.responseMode;renderUnitResponse();};});
  // Status filter
  const sf=document.createElement('div');sf.className='controls';sf.innerHTML='<span class="filter-label">🏷️ สถานะ</span><span id="statusFilter"></span>';
  document.querySelector('.filterbar').appendChild(sf);
  const statusOptions=[['all','ทั้งหมด'],['status_pending','รอตรวจสอบ'],['status_in_progress','อยู่ระหว่างตรวจสอบ'],['status_completed','ตรวจเสร็จสิ้น'],['status_no_error_found','ไม่พบข้อผิดพลาด'],['status_not_recorded','ยังไม่บันทึก']];
  const sfc=document.getElementById('statusFilter');
  statusOptions.forEach(([v,label])=>{const b=document.createElement('span');b.className='pill'+(v==='all'?' on':'');b.textContent=label;b.dataset.v=v;
    b.onclick=()=>{state.statusFilter=v;document.querySelectorAll('#statusFilter .pill').forEach(p=>p.classList.remove('on'));b.classList.add('on');renderAll();};
    sfc.appendChild(b);
  });
  // Action filter
  const af=document.createElement('div');af.className='controls';af.innerHTML='<span class="filter-label">⚡ การดำเนินการ</span><span id="actionFilter"></span>';
  document.querySelector('.filterbar').appendChild(af);
  const actionOptions=[['all','ทั้งหมด'],['action_none_yet','ยังไม่ดำเนินการ'],['action_data_corrected','แก้ไขข้อมูลแล้ว'],['action_other','ดำเนินการอื่นๆ'],['action_not_recorded','ยังไม่บันทึก']];
  const afc=document.getElementById('actionFilter');
  actionOptions.forEach(([v,label])=>{const b=document.createElement('span');b.className='pill'+(v==='all'?' on':'');b.textContent=label;b.dataset.v=v;
    b.onclick=()=>{state.actionFilter=v;document.querySelectorAll('#actionFilter .pill').forEach(p=>p.classList.remove('on'));b.classList.add('on');renderAll();};
    afc.appendChild(b);
  });
  // stack legend
  document.getElementById('stackLegend').innerHTML=DATA.districts.map(d=>`<span style="color:${DIST_COLORS[d]||'#94a3b8'}">■ ${d}</span>`).join('');
  buildReportNav();
}
function renderAll(){renderKPI();renderProvince();renderTrend();renderNet();renderStack();renderPareto();renderMom();renderRatio();renderAns();renderUnitResponse();renderICD();renderUnitTable();renderReport();}
const responsiveController=new ResponsiveChartController({charts:CHARTS,rerender:renderAll});
buildControls();renderAll();responsiveController.start();
</script>
</body></html>"""

VENDOR = os.path.join(BASE_DIR, "vendor")
with open(os.path.join(VENDOR, "chart.umd.min.js"), encoding="utf-8") as f:
    chartjs_src = f.read()
with open(os.path.join(VENDOR, "chartjs-plugin-datalabels.min.js"), encoding="utf-8") as f:
    datalabels_src = f.read()
with open(os.path.join(BASE_DIR, "responsive_chart_controller.js"), encoding="utf-8") as f:
    responsive_controller_src = f.read()
with open(os.path.join(BASE_DIR, "icd10_summary.json"), encoding="utf-8") as f:
    icd10_data = json.load(f)
icd10_js = "const ICD10 = " + safe_json_for_script(icd10_data) + ";"

html = (TEMPLATE
        .replace("/*__CHARTJS__*/", chartjs_src)
        .replace("/*__DATALABELS__*/", datalabels_src)
        .replace("/*__RESPONSIVE_CONTROLLER__*/", responsive_controller_src)
        .replace("/*__DATA__*/", data_js)
        .replace("/*__PROVINCE__*/", province_js)
        .replace("/*__ICD10__*/", icd10_js))
OUT = os.environ.get("PHR_DASHBOARD_OUT", os.path.join(BASE_DIR, "index.html"))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("units:", len(unit_recs), "| districts:", districts, "| OUT:", OUT)

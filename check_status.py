import csv
with open('/Users/mamyboy/dashboard_phr/csv/phr_masks_hospital_20260820_231217.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        code = row['hospital_code']
        ans = int(row.get('answered', 0) or 0)
        sp = int(row.get('status_pending', 0) or 0)
        sip = int(row.get('status_in_progress', 0) or 0)
        sc = int(row.get('status_completed', 0) or 0)
        snef = int(row.get('status_no_error_found', 0) or 0)
        snr = int(row.get('status_not_recorded', 0) or 0)
        suc = int(row.get('status_unexpected_code', 0) or 0)
        total_status = sp + sip + sc + snef + snr + suc
        if total_status != ans:
            print(f'{code}: answered={ans}, status_sum={total_status} (pending={sp}, in_progress={sip}, completed={sc}, no_error={snef}, not_recorded={snr}, unexpected={suc})')
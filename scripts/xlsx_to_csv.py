"""Stream every sheet of an .xlsx into one CSV (low memory). Used once for the public demo data."""
import csv
import sys

from python_calamine import CalamineWorkbook



def _cell(v):
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ")
    if isinstance(v, float) and v.is_integer():
        return int(v)  # Excel stores codes like 85048 as 85048.0
    return v


src, dst = sys.argv[1], sys.argv[2]
wb = CalamineWorkbook.from_path(src)
n = 0
with open(dst, "w", newline="") as f:
    w = csv.writer(f)
    for i, name in enumerate(wb.sheet_names):
        rows = wb.get_sheet_by_name(name).iter_rows()
        header = next(rows)
        if i == 0:
            w.writerow(header)
        for r in rows:
            w.writerow([_cell(v) for v in r])
            n += 1
print(f"{n} rows from sheets {wb.sheet_names}")

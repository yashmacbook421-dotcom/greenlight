"""Snapshot the CEC Grid Support Inverter Lists (solar + battery) into a compact, pinned CSV.

    python -m scripts.refresh_cec_inverters [path/to/InvertersList.xlsx]

Without a path, downloads from the CEC. Writes equipment/cec_inverters.csv and
updates equipment/manifest.json with the source hash and the list's own
"Data has not changed since" date. Review the diff before committing.
"""

import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import openpyxl

URL = "https://solarequipment.energy.ca.gov/Home/DownloadtoExcel?filename=InvertersList"
OUT = Path(__file__).resolve().parents[1] / "app/domains/interconnection/equipment"
COLUMNS = ["list", "manufacturer", "model", "voltage_option", "hybrid", "ul1741_sb", "ul1741_sa",
           "max_continuous_output_kw", "nominal_vac"]


def main() -> None:
    data = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else urllib.request.urlopen(
        urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    rows, as_of = [], None
    for ws, list_name in ((wb["Solar_Inverters"], "solar"), (wb["Battery_Inverters"], "battery")):
        header_seen = False
        for row in ws.iter_rows(values_only=True):
            first = row[0]
            if isinstance(first, str) and first.startswith("Data has not changed since"):
                as_of = first.removeprefix("Data has not changed since").strip()
            if first == "Manufacturer Name":
                header_seen = True
                continue
            if not header_seen or first is None or row[1] is None:
                continue
            model = str(row[1]).strip()
            m = re.search(r"\{([^}]*)\}\s*$", model)
            rows.append({
                "list": list_name, "manufacturer": str(first).strip(), "model": re.sub(r"\s*\{[^}]*\}\s*$", "", model),
                "voltage_option": m.group(1) if m else "", "hybrid": row[2] or "", "ul1741_sb": row[3] or "",
                "ul1741_sa": row[4] or "", "max_continuous_output_kw": "" if row[11] is None else row[11],
                "nominal_vac": "" if row[12] is None else row[12],
            })
    with (OUT / "cec_inverters.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    (OUT / "manifest.json").write_text(json.dumps({
        "source": "California Energy Commission, Grid Support Inverter Lists (solar and battery)",
        "url": URL, "source_sha256": hashlib.sha256(data).hexdigest(), "list_data_as_of": as_of,
        "retrieved": date.today().isoformat(), "rows": len(rows),
        "use": "Proxy for PG&E Rule 21 Screen B 'Certified Equipment' (§L). The CEC list records UL 1741 SA/SB "
               "grid-support certification that California utilities rely on; it is not the tariff's own definition.",
    }, indent=1) + "\n")
    print(f"wrote {len(rows)} rows (list data as of {as_of})")


if __name__ == "__main__":
    main()

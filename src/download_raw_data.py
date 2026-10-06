"""Download the public ERCOT source files used in this project.

The script deliberately stores the original files under ``data/raw/``.  The
analysis pipeline, rather than this downloader, decides how to clean changing
yearly schemas.  All URLs point to ERCOT pages/files cited in the README.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

FILES = {
    # Historical DAM Load Zone and Hub Prices, report NP4-180-ER / 13060.
    "dam_prices_2021.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=814918746",
    "dam_prices_2022.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=886627599",
    "dam_prices_2023.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=969803138",
    "dam_prices_2024.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1065468714",
    "dam_prices_2025.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1177667469",
    "dam_prices_2026.zip": "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1282358736",
    # ERCOT Hourly Load Data Archives.
    "native_load_2021.zip": "https://www.ercot.com/files/docs/2021/11/12/Native_Load_2021.zip",
    "native_load_2022.zip": "https://www.ercot.com/files/docs/2022/02/08/Native_Load_2022.zip",
    "native_load_2023.zip": "https://www.ercot.com/files/docs/2023/02/09/Native_Load_2023.zip",
    "native_load_2024.zip": "https://www.ercot.com/files/docs/2024/02/06/Native_Load_2024.zip",
    "native_load_2025.zip": "https://www.ercot.com/files/docs/2025/02/11/Native_Load_2025.zip",
    "native_load_2026.zip": "https://www.ercot.com/files/docs/2026/02/10/Native_Load_2026.zip",
    # ERCOT Fuel Mix reports: one historical archive plus current annual reports.
    "fuel_mix_2007_2024.zip": "https://www.ercot.com/files/docs/2021/03/10/FuelMixReport_PreviousYears.zip",
    "fuel_mix_2025.xlsx": "https://www.ercot.com/files/docs/2025/02/07/IntGenbyFuel2025.xlsx",
    "fuel_mix_2026.xlsx": "https://www.ercot.com/files/docs/2026/02/09/IntGenbyFuel2026-1-.xlsx",
}


def download(name: str, url: str) -> None:
    destination = RAW_DIR / name
    if destination.exists() and destination.stat().st_size > 0:
        print(f"Already present: {name}")
        return
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=180) as response:  # nosec B310: fixed official HTTPS source
        content = response.read()
    if len(content) < 1_000:
        raise RuntimeError(f"Downloaded file is unexpectedly small: {name}")
    destination.write_bytes(content)
    print(f"Downloaded {name}: {len(content) / 1_000_000:.1f} MB")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        download(name, url)


if __name__ == "__main__":
    main()

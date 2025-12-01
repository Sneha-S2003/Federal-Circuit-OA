import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cafc.uscourts.gov/home/oral-argument/listen-to-oral-arguments/"
EPISODE_DIR = "episodes"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "CAFC-Oral-Arguments-Podcast-Bot/1.0"

os.makedirs(EPISODE_DIR, exist_ok=True)

START_YEAR = 2020
END_YEAR = 2025  # inclusive


def get_rows():
    resp = SESSION.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The arguments are in a table under "Oral Argument Recordings"
    # Each row looks like: [Argument Date] [Appeal Number] [Title (mp3)]
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        date_str = tds[0].get_text(strip=True)  # e.g. "11/10/2025"
        link = tds[2].find("a", href=True)
        if not link or ".mp3" not in link["href"].lower():
            continue

        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            continue

        rows.append((dt, link))

    return rows


def get_mp3_links_2020_2025():
    rows = get_rows()
    links = []
    for dt, link in rows:
        if dt.year < START_YEAR or dt.year > END_YEAR:
            continue

        href = link["href"]
        full_url = urljoin(BASE_URL, href)
        filename = full_url.split("?")[0].split("/")[-1]
        label = link.get_text(strip=True)

        # try docket from filename or label
        m = re.search(r"(\d{4}-\d{3,5})", filename + " " + label)
        docket = m.group(1) if m else filename.replace(".mp3", "")

        links.append(
            {
                "url": full_url,
                "filename": filename,
                "docket": docket,
                "label": label,
                "date": dt,
            }
        )
    print(f"Found {len(links)} mp3s between {START_YEAR} and {END_YEAR}.")
    return links


def download_if_needed(item):
    filename = item["filename"]
    url = item["url"]
    local_path = os.path.join(EPISODE_DIR, filename)

    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        print(f"Already have {filename} ({size} bytes)")
        return

    print(f"Downloading {filename} from {url}")
    resp = SESSION.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    size = os.path.getsize(local_path)
    print(f"Saved {filename} ({size} bytes)")


def main():
    links = get_mp3_links_2020_2025()
    for item in links:
        download_if_needed(item)


if __name__ == "__main__":
    main()

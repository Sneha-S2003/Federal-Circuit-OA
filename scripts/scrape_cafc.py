import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ARCHIVE_BASE = "https://www.cafc.uscourts.gov/category/oral-argument/page/{page}/"
EPISODE_DIR = "episodes"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "CAFC-Oral-Arguments-Podcast-Bot/1.0"

os.makedirs(EPISODE_DIR, exist_ok=True)

START_YEAR = 2020
END_YEAR = 2025  # inclusive
MAX_PAGES = 100  # the archive shows up to ~100 pages


def parse_date(text: str):
    """
    Try to parse dates like 'November 10, 2025'.
    Returns datetime or None.
    """
    text = text.strip()
    try:
        return datetime.strptime(text, "%B %d, %Y")
    except ValueError:
        return None


def get_links_from_page(page: int):
    """
    Scrape a single archive page and return list of dicts:
    { url, filename, docket, label, date }
    """
    url = ARCHIVE_BASE.format(page=page)
    print(f"Fetching archive page {page}: {url}")
    resp = SESSION.get(url, timeout=30)
    if resp.status_code == 404:
        print("Got 404, assuming no more pages.")
        return None  # signal to stop
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []

    # Each entry looks like:
    #   <h3>2023-2331: Oliva v. DVA</h3>
    #   <p>November 10, 2025</p>
    #   <p>Oral argument audio posted: Oliva v. DVA (mp3) ...</p>
    for h3 in soup.find_all("h3"):
        title_text = h3.get_text(strip=True)
        # look for the date in the next sibling <p>
        date_dt = None
        mp3_href = None

        for sib in h3.next_siblings:
            if getattr(sib, "name", None) == "p":
                # try to parse a date line first
                if not date_dt:
                    dt = parse_date(sib.get_text(" ", strip=True))
                    if dt:
                        date_dt = dt
                        continue
                # look for mp3 link
                a = sib.find("a", href=True)
                if a and ".mp3" in a["href"].lower():
                    mp3_href = a["href"]
                    break

        if not mp3_href or not date_dt:
            continue

        if date_dt.year < START_YEAR or date_dt.year > END_YEAR:
            continue

        full_url = urljoin(url, mp3_href)
        filename = full_url.split("?")[0].split("/")[-1]

        m = re.search(r"(\d{4}-\d{3,5})", title_text)
        docket = m.group(1) if m else filename.replace(".mp3", "")

        links.append(
            {
                "url": full_url,
                "filename": filename,
                "docket": docket,
                "label": title_text,
                "date": date_dt,
            }
        )

    print(f"Page {page}: found {len(links)} matches in {START_YEAR}-{END_YEAR}.")
    return links


def get_all_links_2020_2025():
    all_links = []
    seen = set()

    for page in range(1, MAX_PAGES + 1):
        page_links = get_links_from_page(page)
        if page_links is None:
            break  # hit a 404, no more pages

        for item in page_links:
            if item["filename"] in seen:
                continue
            seen.add(item["filename"])
            all_links.append(item)

    print(f"Total unique mp3s between {START_YEAR}-{END_YEAR}: {len(all_links)}")
    return all_links


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
    links = get_all_links_2020_2025()
    for item in links:
        download_if_needed(item)


if __name__ == "__main__":
    main()

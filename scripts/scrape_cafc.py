import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Archive listing pages like:
# https://www.cafc.uscourts.gov/category/oral-argument/page/1/
ARCHIVE_BASE = "https://www.cafc.uscourts.gov/category/oral-argument/page/{page}/"

EPISODE_DIR = "episodes"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "CAFC-Oral-Arguments-Podcast-Bot/1.0"

os.makedirs(EPISODE_DIR, exist_ok=True)

START_YEAR = 2020
END_YEAR = 2025          # inclusive
MAX_PAGES = 100          # archive shows up to Page 100


def parse_date_from_text(text: str):
    """
    Find a date like 'February 5, 2024' anywhere in the text.
    Returns datetime or None.
    """
    month_names = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    )
    pattern = r"(" + "|".join(month_names) + r")\s+\d{1,2},\s+\d{4}"
    m = re.search(pattern, text)
    if not m:
        return None
    date_str = m.group(0)
    try:
        return datetime.strptime(date_str, "%B %d, %Y")
    except ValueError:
        return None


def get_detail_links_from_archive(page: int):
    """
    For a given archive page, return list of (detail_url, title_text)
    where detail_url is the 'Read More' / case link.
    """
    url = ARCHIVE_BASE.format(page=page)
    print(f"Fetching archive page {page}: {url}")
    resp = SESSION.get(url, timeout=30)
    if resp.status_code == 404:
        print("Got 404, assuming no more archive pages.")
        return None  # signal: no more pages
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    detail_links = []

    # Each case appears as an <h3><a href="detail-page">2024-1531: Case Name</a></h3>
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue
        detail_url = urljoin(url, a["href"])
        title_text = a.get_text(strip=True)
        detail_links.append((detail_url, title_text))

    print(f"Page {page}: found {len(detail_links)} detail links.")
    return detail_links


def parse_detail_page(detail_url: str, title_text: str):
    """
    Open a detail page like:
      https://www.cafc.uscourts.gov/02-05-2024-2021-2348-lkq-...-audio-uploaded/
    Extract:
      - mp3 URL
      - docket
      - date
      - label (title_text)
    Returns dict or None if something is missing / out of year range.
    """
    print(f"  Fetching detail page: {detail_url}")
    resp = SESSION.get(detail_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the mp3 link on the page
    mp3_a = soup.find("a", href=lambda h: h and h.lower().endswith(".mp3"))
    if not mp3_a:
        print("    No .mp3 link found on this page.")
        return None

    mp3_url = urljoin(detail_url, mp3_a["href"])
    filename = mp3_url.split("?")[0].split("/")[-1]

    # Docket: something like 2021-2348, either in the H1 or title_text
    page_text = soup.get_text(" ", strip=True)
    docket_match = re.search(r"\b(\d{4}-\d{3,5})\b", page_text) or \
                   re.search(r"\b(\d{4}-\d{3,5})\b", title_text)
    docket = docket_match.group(1) if docket_match else filename.replace(".mp3", "")

    # Date: parse from the text (e.g. 'February 5, 2024')
    dt = parse_date_from_text(page_text)
    if not dt:
        print("    Could not find date on page; skipping.")
        return None

    if dt.year < START_YEAR or dt.year > END_YEAR:
        print(f"    Year {dt.year} out of range; skipping.")
        return None

    label = title_text

    return {
        "url": mp3_url,
        "filename": filename,
        "docket": docket,
        "label": label,
        "date": dt,
    }


def get_all_links_2020_2025():
    """
    Walk archive pages, follow each detail link, and collect MP3 metadata
    for arguments between START_YEAR and END_YEAR.
    """
    all_items = []
    seen_filenames = set()

    for page in range(1, MAX_PAGES + 1):
        detail_links = get_detail_links_from_archive(page)
        if detail_links is None:
            break  # hit 404 -> no more pages

        for detail_url, title_text in detail_links:
            item = parse_detail_page(detail_url, title_text)
            if not item:
                continue
            fn = item["filename"]
            if fn in seen_filenames:
                continue
            seen_filenames.add(fn)
            all_items.append(item)

    print(f"Total unique mp3s between {START_YEAR}-{END_YEAR}: {len(all_items)}")
    return all_items


def download_if_needed(item):
    filename = item["filename"]
    url = item["url"]
    local_path = os.path.join(EPISODE_DIR, filename)

    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        print(f"Already have {filename} ({size} bytes)")
        return

    print(f"Downloading {filename} from {url}")
    resp = SESSION.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    size = os.path.getsize(local_path)
    print(f"Saved {filename} ({size} bytes)")


def main():
    items = get_all_links_2020_2025()
    for item in items:
        download_if_needed(item)


if __name__ == "__main__":
    main()

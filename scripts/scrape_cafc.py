import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cafc.uscourts.gov/home/oral-argument/listen-to-oral-arguments/"
EPISODE_DIR = "episodes"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "CAFC-Oral-Arguments-Podcast-Bot/1.0"

os.makedirs(EPISODE_DIR, exist_ok=True)


def get_mp3_links():
    """
    Scrape the CAFC 'Listen to Oral Arguments' page and return a list
    of dicts with keys: url, filename, docket (best-effort), label.
    """
    print(f"Fetching {BASE_URL}")
    resp = SESSION.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".mp3" not in href.lower():
            continue

        # Make absolute URL
        full_url = urljoin(BASE_URL, href)

        # Strip query params for filename
        filename = full_url.split("?")[0].split("/")[-1]

        # Try to extract docket from filename or link text
        text = a.get_text(strip=True)
        candidate_string = filename + " " + text
        m = re.search(r"\b(\d{4}-\d{3,5})\b", candidate_string)
        docket = m.group(1) if m else filename.replace(".mp3", "")

        label = text or docket

        links.append(
            {
                "url": full_url,
                "filename": filename,
                "docket": docket,
                "label": label,
            }
        )

    # De-duplicate by filename
    seen = set()
    unique_links = []
    for item in links:
        if item["filename"] in seen:
            continue
        seen.add(item["filename"])
        unique_links.append(item)

    print(f"Found {len(unique_links)} mp3 links.")
    return unique_links


def download_if_needed(item):
    """
    Download mp3 into episodes/ if not present.
    Returns (local_path, file_size_bytes).
    """
    filename = item["filename"]
    url = item["url"]
    local_path = os.path.join(EPISODE_DIR, filename)

    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        print(f"Already have {filename} ({size} bytes)")
        return local_path, size

    print(f"Downloading {filename} from {url}")
    resp = SESSION.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    size = os.path.getsize(local_path)
    print(f"Saved {filename} ({size} bytes)")
    return local_path, size


def main():
    links = get_mp3_links()
    for item in links:
        download_if_needed(item)


if __name__ == "__main__":
    main()


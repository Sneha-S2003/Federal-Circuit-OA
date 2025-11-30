import os
import re
from datetime import datetime
from email.utils import format_datetime

EPISODE_DIR = "episodes"
PUBLIC_BASE = "https://sneha-s2003.github.io/Federal-Circuit-OA"


def extract_docket_and_date(filename: str):
    """
    Try to extract a docket and date from the filename.
    e.g., 2019-1161_04-01-2020.mp3
    """
    base = filename.rsplit(".", 1)[0]

    # Docket like 2019-1161
    docket_match = re.search(r"(\d{4}-\d{3,5})", base)
    docket = docket_match.group(1) if docket_match else base

    # Date like 04-01-2020
    date_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", base)
    if date_match:
        month, day, year = date_match.groups()
        dt = datetime(int(year), int(month), int(day))
    else:
        # Fall back to "now" if no date in filename
        dt = datetime.utcnow()

    return docket, dt


def make_item(filename: str) -> str:
    """
    Build an <item> xml string for one mp3 file in episodes/.
    """
    file_path = os.path.join(EPISODE_DIR, filename)
    size = os.path.getsize(file_path)
    docket, dt = extract_docket_and_date(filename)

    pubdate = format_datetime(dt)
    title = f"{docket} – Oral Argument"
    description = f"Oral argument audio for docket {docket}."

    enclosure_url = f"{PUBLIC_BASE}/episodes/{filename}"

    item_xml = f"""
    <item>
      <title>{title}</title>
      <enclosure url="{enclosure_url}"
                 length="{size}"
                 type="audio/mpeg" />
      <guid isPermaLink="false">{docket}</guid>
      <pubDate>{pubdate}</pubDate>
      <description>{description}</description>
      <itunes:explicit>no</itunes:explicit>
    </item>
"""
    return item_xml


def generate_feed():
    # Collect items in a deterministic order (e.g. sorted by filename)
    files = [
        f
        for f in os.listdir(EPISODE_DIR)
        if f.lower().endswith(".mp3")
    ]
    files.sort()

    items_xml = "".join(make_item(f) for f in files)

    channel_xml = f"""<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>U.S. Court of Appeals Federal Circuit - Oral Arguments</title>
    <link>https://cafc.uscourts.gov</link>
    <language>en-us</language>
    <description>
      A growing archive of oral arguments before the U.S. Court of Appeals for the Federal Circuit, made accessible in a podcast-friendly format. Each episode features the official courtroom audio as released by the Court.
    </description>

    <itunes:author>Sneha S</itunes:author>
    <itunes:owner>
      <itunes:name>Sneha S</itunes:name>
      <itunes:email>snehasridhar@gmail.com</itunes:email>
    </itunes:owner>
    <itunes:image href="{PUBLIC_BASE}/oral.png" />
    <itunes:explicit>no</itunes:explicit>
{items_xml}
  </channel>
</rss>
"""

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(channel_xml.strip() + "\n")
    print("Wrote feed.xml with", len(files), "episodes.")


if __name__ == "__main__":
    os.makedirs(EPISODE_DIR, exist_ok=True)
    generate_feed()


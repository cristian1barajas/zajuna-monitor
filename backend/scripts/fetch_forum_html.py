"""Temporary script to fetch forum HTML pages from Zajuna for parser development.

Usage:
    cd backend
    .venv/Scripts/python.exe scripts/fetch_forum_html.py

Fetches 3 HTML files:
1. Forum index page (/mod/forum/index.php?id=COURSE_ID)
2. Forum view page (/mod/forum/view.php?id=CMID)
3. Forum discussion page (/mod/forum/discuss.php?d=ID) — auto-discovered from view page

Saves them to docs/html-samples/ for analysis and test fixture creation.
"""
import re
import sys
from pathlib import Path

# Add backend/ to path so `src.*` imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth.manager import AuthManager
from src.client.zajuna import ZajunaClient
from src.config import ZajunaConfig

# --- Config ---
COURSE_ID = 89967       # ficha 3388998
FORUM_CMID = 5967147    # from user-provided URL

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "html-samples"

DISCUSSION_LINK_PATTERN = re.compile(r"discuss\.php\?d=(\d+)")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Authenticating with Zajuna...")
    config = ZajunaConfig()
    auth = AuthManager(config)
    client = ZajunaClient(auth, config)
    auth.login()
    print("Authenticated OK\n")

    # 1. Forum index page
    print(f"Fetching forum index for course {COURSE_ID}...")
    forum_index_path = f"/zajuna/mod/forum/index.php?id={COURSE_ID}"
    forum_index_html = client._request("GET", forum_index_path)
    out1 = OUTPUT_DIR / "forum_index.html"
    out1.write_text(forum_index_html, encoding="utf-8")
    print(f"  Saved: {out1} ({len(forum_index_html)} chars)\n")

    # 2. Forum view page
    print(f"Fetching forum view for cmid {FORUM_CMID}...")
    forum_view_path = f"/zajuna/mod/forum/view.php?id={FORUM_CMID}"
    forum_view_html = client._request("GET", forum_view_path)
    out2 = OUTPUT_DIR / "forum_view.html"
    out2.write_text(forum_view_html, encoding="utf-8")
    print(f"  Saved: {out2} ({len(forum_view_html)} chars)\n")

    # 3. Also fetch the other forum the user showed in screenshots (with ungraded posts)
    FORUM_CMID_2 = 5963979  # From user's screenshot
    print(f"Fetching second forum view for cmid {FORUM_CMID_2}...")
    forum_view2_path = f"/zajuna/mod/forum/view.php?id={FORUM_CMID_2}"
    forum_view2_html = client._request("GET", forum_view2_path)

    # Find discussions with replies (more likely to have ungraded posts)
    disc2_ids = list(dict.fromkeys(DISCUSSION_LINK_PATTERN.findall(forum_view2_html)))
    print(f"  Found {len(disc2_ids)} discussions in second forum")

    # Fetch the discussion the user showed (d=5545198) or first available
    target_disc = "5545198" if "5545198" in disc2_ids else disc2_ids[0] if disc2_ids else None
    if target_disc:
        print(f"Fetching discussion d={target_disc} (from user's screenshot)...")
        disc_path = f"/zajuna/mod/forum/discuss.php?d={target_disc}"
        disc_html = client._request("GET", disc_path)
        out3 = OUTPUT_DIR / "forum_discussion.html"
        out3.write_text(disc_html, encoding="utf-8")
        print(f"  Saved: {out3} ({len(disc_html)} chars)")

        # Count posts and rating forms
        import re as _re
        post_count = len(_re.findall(r'class="postratingform"', disc_html))
        graded = len(_re.findall(r'class="ratingaggregate">\d+<', disc_html))
        print(f"  Posts with rating forms: {post_count}")
        print(f"  Posts with numeric grade: {graded}")
        print(f"  Likely ungraded: {post_count - graded}\n")
    else:
        print("  ERROR: No discussions found in second forum\n")

    print("Done! Files saved to docs/html-samples/")


if __name__ == "__main__":
    main()

"""Parser for Zajuna Moodle Forum view and discussion pages.

- parse_forum_discussions: Parses /mod/forum/view.php?f={forum_id}
  to extract the list of discussion IDs.

- parse_forum_posts_grading: Parses /mod/forum/discuss.php?d={discussion_id}
  to count graded vs ungraded posts.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.parsers.grader import ParseError

logger = logging.getLogger(__name__)

DISCUSSION_ID_PATTERN = re.compile(r"discuss\.php\?d=(\d+)")


@dataclass
class ForumDiscussion:
    """A single discussion in a forum."""

    discussion_id: int
    title: str


@dataclass
class ForumGradingInfo:
    """Grading summary for a single forum discussion."""

    discussion_id: int
    total_posts: int      # Posts with a rating form
    graded_posts: int     # Posts with a numeric grade
    ungraded_posts: int   # Posts without a grade (empty aggregate)


def parse_forum_discussions(html: str, forum_id: int) -> list[ForumDiscussion]:
    """Parse forum view page to extract discussion list.

    The view page uses <tr class="discussion" data-discussionid="..."> rows
    with discussion links in <a href="discuss.php?d=..."> elements.

    Args:
        html: Raw HTML from /mod/forum/view.php?f={forum_id}
        forum_id: The forum instance ID (for error messages).

    Returns:
        List of ForumDiscussion with discussion_id and title.

    Raises:
        ParseError: If no discussions are found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Try the modern table structure first (data-discussionid attribute)
    rows = soup.find_all("tr", class_="discussion")

    if rows:
        return _parse_discussion_rows(rows)

    # Fallback: find discuss.php links directly
    links = soup.find_all("a", href=DISCUSSION_ID_PATTERN)
    if not links:
        raise ParseError(
            f"No discussions found in forum {forum_id}. "
            "The forum may be empty or the page structure is unexpected."
        )

    return _parse_discussion_links(links)


def _parse_discussion_rows(rows) -> list[ForumDiscussion]:
    """Parse discussion rows with data-discussionid attributes."""
    discussions: list[ForumDiscussion] = []
    seen_ids: set[int] = set()

    for row in rows:
        disc_id_str = row.get("data-discussionid")
        if not disc_id_str:
            continue

        disc_id = int(disc_id_str)
        if disc_id in seen_ids:
            continue
        seen_ids.add(disc_id)

        # Title is in the topic column
        topic_link = row.find("a", class_="w-100")
        if not topic_link:
            topic_link = row.find("th", class_="topic")

        title = topic_link.get_text(strip=True) if topic_link else f"Discussion {disc_id}"

        discussions.append(ForumDiscussion(discussion_id=disc_id, title=title))

    logger.debug("Extracted %d discussions from rows", len(discussions))
    return discussions


def _parse_discussion_links(links) -> list[ForumDiscussion]:
    """Fallback: parse discussion links directly."""
    discussions: list[ForumDiscussion] = []
    seen_ids: set[int] = set()

    for link in links:
        href = link.get("href", "")
        match = DISCUSSION_ID_PATTERN.search(href)
        if not match:
            continue

        disc_id = int(match.group(1))
        if disc_id in seen_ids:
            continue
        seen_ids.add(disc_id)

        title = link.get_text(strip=True) or f"Discussion {disc_id}"
        discussions.append(ForumDiscussion(discussion_id=disc_id, title=title))

    logger.debug("Extracted %d discussions from links", len(discussions))
    return discussions


def parse_forum_posts_grading(html: str, discussion_id: int) -> ForumGradingInfo:
    """Parse a forum discussion page to count graded vs ungraded posts.

    Each post with a rating form has:
    - <form class="postratingform"> containing a rating form
    - <span class="ratingaggregate">VALUE</span>
      - Graded: VALUE is a number (e.g., "100")
      - Ungraded: VALUE is empty string ""
    - <span class="ratingcount">
      - Graded: "(1)" or similar
      - Ungraded: "-"

    Args:
        html: Raw HTML from /mod/forum/discuss.php?d={discussion_id}
        discussion_id: The discussion ID (for error messages).

    Returns:
        ForumGradingInfo with counts of graded vs ungraded posts.

    Raises:
        ParseError: If the page structure is unexpected.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find all rating forms
    rating_forms = soup.find_all("form", class_="postratingform")

    if not rating_forms:
        # No rating forms = no gradeable posts (might be a non-graded forum)
        logger.debug(
            "No rating forms found in discussion %d", discussion_id
        )
        return ForumGradingInfo(
            discussion_id=discussion_id,
            total_posts=0,
            graded_posts=0,
            ungraded_posts=0,
        )

    graded = 0
    ungraded = 0

    for form in rating_forms:
        aggregate_span = form.find("span", class_="ratingaggregate")

        if aggregate_span:
            value = aggregate_span.get_text(strip=True)
            if value and value not in ("-", ""):
                # Has a numeric value = graded
                graded += 1
            else:
                # Empty or "-" = ungraded
                ungraded += 1
        else:
            # No aggregate span = ungraded
            ungraded += 1

    total = graded + ungraded

    logger.debug(
        "Discussion %d: %d posts, %d graded, %d ungraded",
        discussion_id, total, graded, ungraded,
    )

    return ForumGradingInfo(
        discussion_id=discussion_id,
        total_posts=total,
        graded_posts=graded,
        ungraded_posts=ungraded,
    )

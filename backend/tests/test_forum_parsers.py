"""Tests for forum index and forum detail parsers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from src.parsers.forum_detail import (
    ForumDiscussion,
    ForumGradingInfo,
    parse_forum_discussions,
    parse_forum_posts_grading,
)
from src.parsers.forum_index import (
    ForumEntry,
    match_forums_to_evidences,
    parse_forum_index,
)
from src.parsers.grader import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class FakeEvidence:
    item_id: int
    name: str


# ── Forum Index Parser ──────────────────────────────────────────────


class TestForumIndexParser:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (FIXTURES / "forum_index_sample.html").read_text(encoding="utf-8")
        self.forums = parse_forum_index(self.html)

    def test_parses_all_forums(self):
        # 1 general + 3 learning = 4 total
        assert len(self.forums) == 4

    def test_extracts_forum_ids(self):
        ids = {f.forum_id for f in self.forums}
        assert 565687 in ids   # ANUNCIOS
        assert 565694 in ids   # Foro temático
        assert 565695 in ids   # Foro Especificación

    def test_extracts_names(self):
        names = [f.name for f in self.forums]
        assert "ANUNCIOS" in names
        assert any("Fuentes de requisitos" in n for n in names)

    def test_first_forum(self):
        f = self.forums[0]
        assert f.name == "ANUNCIOS"
        assert f.forum_id == 565687

    def test_returns_forum_entry_dataclass(self):
        assert isinstance(self.forums[0], ForumEntry)

    def test_no_duplicate_forum_ids(self):
        ids = [f.forum_id for f in self.forums]
        assert len(ids) == len(set(ids))

    def test_excludes_numeric_only_text(self):
        """Discussion count links (e.g., '12', '21') should be excluded."""
        names = [f.name for f in self.forums]
        for name in names:
            assert not name.isdigit()

    def test_empty_html_raises_parse_error(self):
        with pytest.raises(ParseError):
            parse_forum_index("<html><body></body></html>")


# ── Forum Index Matching ────────────────────────────────────────────


class TestMatchForumsToEvidences:
    def test_exact_match(self):
        forums = [ForumEntry(name="Foro temático - Fuentes", forum_id=100)]
        evidences = [FakeEvidence(item_id=5, name="Foro temático - Fuentes")]
        result = match_forums_to_evidences(forums, evidences)
        assert result[0]["item_id"] == 5
        assert result[0]["module_type"] == "forum"

    def test_substring_match(self):
        forums = [ForumEntry(name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA2-EV02.", forum_id=100)]
        evidences = [FakeEvidence(item_id=5, name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA2-EV02. calificación")]
        result = match_forums_to_evidences(forums, evidences)
        assert result[0]["item_id"] == 5

    def test_no_match_returns_none(self):
        forums = [ForumEntry(name="Foro social", forum_id=100)]
        evidences = [FakeEvidence(item_id=5, name="Taller de programación")]
        result = match_forums_to_evidences(forums, evidences)
        assert result[0]["item_id"] is None

    def test_same_guide_aa1_and_aa2_do_not_collide(self):
        """Forums of AA1 and AA2 share a 30-char prefix; the GA code must decide."""
        forums = [
            ForumEntry(name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA1-EV02.", forum_id=100),
            ForumEntry(name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA2-EV02.", forum_id=200),
        ]
        evidences = [
            FakeEvidence(item_id=11, name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA1-EV02. calificación"),
            FakeEvidence(item_id=22, name="Foro temático - Fuentes de requisitos.  GA1-220501092-AA2-EV02. calificación"),
        ]
        result = match_forums_to_evidences(forums, evidences)
        assert [r["item_id"] for r in result] == [11, 22]

    def test_module_type_is_forum(self):
        forums = [ForumEntry(name="Test", forum_id=100)]
        result = match_forums_to_evidences(forums, [])
        assert result[0]["module_type"] == "forum"

    def test_cmid_is_forum_id(self):
        forums = [ForumEntry(name="Test", forum_id=565694)]
        result = match_forums_to_evidences(forums, [])
        assert result[0]["cmid"] == 565694


# ── Forum View (Discussion List) Parser ─────────────────────────────


class TestForumDiscussions:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (FIXTURES / "forum_view_sample.html").read_text(encoding="utf-8")
        self.discussions = parse_forum_discussions(self.html, forum_id=565694)

    def test_parses_all_discussions(self):
        assert len(self.discussions) == 3

    def test_extracts_discussion_ids(self):
        ids = {d.discussion_id for d in self.discussions}
        assert ids == {5545198, 5530088, 5490212}

    def test_extracts_titles(self):
        titles = [d.title for d in self.discussions]
        assert "Fuentes de requisitos Gloria Peña" in titles
        assert "Fuentes de requisitos Monica Prueba" in titles

    def test_returns_discussion_dataclass(self):
        assert isinstance(self.discussions[0], ForumDiscussion)

    def test_no_duplicate_ids(self):
        ids = [d.discussion_id for d in self.discussions]
        assert len(ids) == len(set(ids))

    def test_empty_html_raises_parse_error(self):
        with pytest.raises(ParseError):
            parse_forum_discussions("<html><body></body></html>", forum_id=0)


# ── Forum Discussion (Post Grading) Parser ──────────────────────────


class TestForumPostsGrading:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = (FIXTURES / "forum_discussion_sample.html").read_text(encoding="utf-8")
        self.info = parse_forum_posts_grading(self.html, discussion_id=5545198)

    def test_total_posts(self):
        assert self.info.total_posts == 3

    def test_graded_posts(self):
        assert self.info.graded_posts == 2  # Posts with score 100 and 80

    def test_ungraded_posts(self):
        assert self.info.ungraded_posts == 1  # Post with empty aggregate

    def test_discussion_id(self):
        assert self.info.discussion_id == 5545198

    def test_returns_grading_info_dataclass(self):
        assert isinstance(self.info, ForumGradingInfo)

    def test_total_equals_graded_plus_ungraded(self):
        assert self.info.total_posts == self.info.graded_posts + self.info.ungraded_posts

    def test_no_rating_forms_returns_zero(self):
        info = parse_forum_posts_grading(
            "<html><body><p>No posts here</p></body></html>",
            discussion_id=0,
        )
        assert info.total_posts == 0
        assert info.graded_posts == 0
        assert info.ungraded_posts == 0

    def test_all_graded(self):
        html = """
        <form class="postratingform">
            <span class="ratingaggregate">100</span>
        </form>
        <form class="postratingform">
            <span class="ratingaggregate">80</span>
        </form>
        """
        info = parse_forum_posts_grading(html, discussion_id=0)
        assert info.graded_posts == 2
        assert info.ungraded_posts == 0

    def test_all_ungraded(self):
        html = """
        <form class="postratingform">
            <span class="ratingaggregate"></span>
        </form>
        <form class="postratingform">
            <span class="ratingaggregate">-</span>
        </form>
        """
        info = parse_forum_posts_grading(html, discussion_id=0)
        assert info.graded_posts == 0
        assert info.ungraded_posts == 2

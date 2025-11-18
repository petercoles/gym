import asyncio
from pathlib import Path
import sys

import pytest
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gym_booking_bot import GymBookingBot


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "test_data" / "class_calendar.html"


@pytest.fixture
def bot(monkeypatch: pytest.MonkeyPatch) -> GymBookingBot:
    monkeypatch.setenv("GYM_URL", "https://example.com/classes")
    monkeypatch.setenv("PETER_USERNAME", "test-user")
    monkeypatch.setenv("PETER_PASSWORD", "test-pass")
    monkeypatch.setenv("HEADLESS", "true")
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    return GymBookingBot(user_name="peter")


async def _locate_matches(bot: GymBookingBot, day_label: str, instructor: str, time: str):
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    calendar = soup.select_one("#classCalendarDesktop")
    assert calendar is not None, "Calendar root should exist in fixture HTML"
    fake_root = _FakeElement(calendar)
    return await bot._locate_matching_classes(fake_root, day_label, instructor, time)


class _FakeElement:
    """Minimal async-compatible wrapper to mimic Playwright's element API using BeautifulSoup."""

    def __init__(self, element):
        self.element = element

    async def query_selector_all(self, selector: str):
        return [_FakeElement(el) for el in self.element.select(selector)]

    async def query_selector(self, selector: str):
        result = self.element.select_one(selector)
        return _FakeElement(result) if result else None

    async def inner_text(self):
        return self.element.get_text(strip=False)

    async def text_content(self):
        return self.element.get_text(strip=False)


def test_locates_marina_pilates_class(bot: GymBookingBot):
    matches, matched_label = asyncio.run(
        _locate_matches(bot, "Wed 26 Nov", "Marina", "12:00")
    )
    assert matched_label.lower().startswith("wed 26 nov")
    assert len(matches) == 1

    container_text = matches[0]["text"]
    assert "Pilates" in container_text
    assert "Marina" in container_text
    assert "12:00" in container_text


def test_no_terry_class_at_noon(bot: GymBookingBot):
    matches, _ = asyncio.run(_locate_matches(bot, "Wed 26 Nov", "Terry", "12:00"))
    assert matches == []

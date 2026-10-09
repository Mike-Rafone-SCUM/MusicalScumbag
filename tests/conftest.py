"""Keep automatic background lyric lookup offline in the test suite."""
import pytest


@pytest.fixture(autouse=True)
def offline_auto_lyrics(monkeypatch):
    from musical_scumme import auto_lyrics
    monkeypatch.setattr(auto_lyrics, "search_lyrics", lambda *args, **kwargs: [])

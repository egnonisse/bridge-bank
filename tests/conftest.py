"""Helpers partagés pour les tests."""
from datetime import datetime, timedelta

import pytest

from src.models import HistoryBar


@pytest.fixture
def make_bars():
    """Fabrique une liste de HistoryBar à partir de closes (et volumes optionnels)."""

    def _make(closes, volumes=None):
        start = datetime(2026, 1, 1)
        vols = volumes or [100] * len(closes)
        return [
            HistoryBar(
                date=start + timedelta(days=i),
                open=c,
                high=c,
                low=c,
                close=c,
                volume=vols[i],
            )
            for i, c in enumerate(closes)
        ]

    return _make

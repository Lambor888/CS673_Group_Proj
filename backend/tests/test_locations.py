from types import SimpleNamespace

import pytest

from app.modules.location import service
from app.modules.rounds.service import SinglePlayerGame


def test_every_location_is_valid():
    names = [spot["name"] for spot in service.LOCATIONS]
    assert len(names) == len(set(names)) >= 50
    for spot in service.LOCATIONS:
        assert spot["country"]
        assert -90 <= spot["lat"] <= 90 and -180 <= spot["lng"] <= 180


def test_no_repeats_until_every_location_is_used(monkeypatch):
    monkeypatch.setattr(service, "lookup_location",
                        lambda lat, lng: service.Location(pano_id=f"{lat},{lng}", lat=lat, lng=lng))
    used = set()
    for _ in service.LOCATIONS:
        used.add(service.generate_location(used).pano_id)
    assert len(used) == len(service.LOCATIONS)
    with pytest.raises(service.LocationError, match="No new"):
        service.generate_location(used)


def test_game_excludes_every_earlier_round():
    seen = []

    def make_location(used_panos):
        seen.append(set(used_panos))
        return SimpleNamespace(pano_id=f"pano{len(seen)}", lat=0.0, lng=0.0)

    game = SinglePlayerGame.start(1, make_location)
    for number in range(1, 5):
        game.current.finished = True
        game.start_next(number, make_location)
    assert seen[-1] == {"pano1", "pano2", "pano3", "pano4"}

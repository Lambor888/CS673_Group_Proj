"""In-memory capital practice; scoring reuses the single-player formula.

One session per user, one server worker. No profile/history writes.
"""
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID, uuid4

from app.modules.location.service import CapitalLocation, generate_capital_location
from app.modules.rounds.service import ROUND_SECONDS
from app.scoring import haversine_distance, single_player_round_score


class CapitalGameError(Exception):
    pass


@dataclass
class CapitalRound:
    number: int
    location: CapitalLocation
    id: UUID = field(default_factory=uuid4)
    started_at: float = field(default_factory=monotonic)
    finished: bool = False
    score: int = 0
    distance_km: float | None = None
    guess: dict[str, float] | None = None

    def seconds_left(self) -> float:
        return max(0, ROUND_SECONDS - (monotonic() - self.started_at))

    def refresh(self) -> None:
        if self.seconds_left() <= 0:
            self.finished = True


@dataclass
class CapitalGame:
    current: CapitalRound
    total_score: int = 0
    used_countries: set[str] = field(default_factory=set)

    @classmethod
    def start(cls):
        location = generate_capital_location()
        return cls(CapitalRound(1, location), used_countries={location.code})

    def next_round(self, previous_id: UUID) -> None:
        self.current.refresh()
        if previous_id != self.current.id:
            raise CapitalGameError('Round changed. Refresh before continuing.')
        if not self.current.finished:
            raise CapitalGameError('Finish the current round first.')
        location = generate_capital_location(self.used_countries)
        if location.code in self.used_countries:
            self.used_countries.clear()  # All countries used: begin a new cycle.
        self.used_countries.add(location.code)
        self.current = CapitalRound(self.current.number + 1, location)

    def submit(self, round_id: UUID, lat: float, lng: float) -> None:
        current = self.current
        if round_id != current.id:
            raise CapitalGameError('Round changed. Refresh before submitting.')
        current.refresh()
        if current.guess is not None:
            return  # Retrying a submission must not award points twice.
        if current.finished:
            raise CapitalGameError('Time is up for this round.')
        distance = min(haversine_distance(lat, lng, capital.lat, capital.lng)
                       for capital in current.location.capitals)
        current.distance_km = round(distance, 3)
        current.score = single_player_round_score(distance)
        current.guess = {'lat': lat, 'lng': lng}
        current.finished = True
        self.total_score += current.score

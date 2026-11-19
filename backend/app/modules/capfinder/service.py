"""In-memory capital practice; scoring reuses the single-player formula.

One session per user, one server worker. No profile/history writes.
"""
from dataclasses import dataclass, field
import random
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

from app.modules.location.service import CapitalLocation, generate_capital_location
from app.modules.location.country import CountryView, lookup_country
from app.modules.rounds.service import ROUND_SECONDS
from app.scoring import haversine_distance, single_player_round_score

CapitalMode = Literal['map', 'text']


def choose_mode() -> CapitalMode:
    """Only the server chooses a mode, once when generating each new round."""
    return random.choice(('map', 'text'))


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
    country_view: CountryView | None = None
    submitted_answer: str | None = None
    correct: bool | None = None
    mode: CapitalMode = 'map'

    @classmethod
    def generate(cls, number: int, used_countries=()):
        mode = choose_mode()
        location = generate_capital_location(used_countries)
        view = lookup_country(location.code) if mode == 'text' else None
        return cls(number, location, mode=mode, country_view=view)

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
        current = CapitalRound.generate(1)
        return cls(current, used_countries={current.location.code})

    def next_round(self, previous_id: UUID) -> None:
        self.current.refresh()
        if previous_id != self.current.id:
            raise CapitalGameError('Round changed. Refresh before continuing.')
        if not self.current.finished:
            raise CapitalGameError('Finish the current round first.')
        next_round = CapitalRound.generate(self.current.number + 1, self.used_countries)
        location = next_round.location
        if location.code in self.used_countries:
            self.used_countries.clear()  # All countries used: begin a new cycle.
        self.used_countries.add(location.code)
        self.current = next_round

    def submit(self, round_id: UUID, lat: float, lng: float) -> None:
        if self.current.mode != 'map':
            raise CapitalGameError('Submit a capital name in this mode.')
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

    def submit_answer(self, round_id: UUID, answer: str) -> None:
        if self.current.mode != 'text':
            raise CapitalGameError('Select a location in this mode.')
        current = self.current
        if round_id != current.id:
            raise CapitalGameError('Round changed. Refresh before submitting.')
        current.refresh()
        if current.submitted_answer is not None:
            return  # Network retries cannot change the result or award points twice.
        if current.finished:
            raise CapitalGameError('Time is up for this round.')
        answer = answer.strip()
        if not answer:
            raise CapitalGameError('Enter a capital name.')
        capital = next((capital for capital in current.location.capitals
                        if capital.name.strip().casefold() == answer.casefold()), None)
        current.correct = capital is not None
        if capital is not None:
            # Reuse the same distance and scoring functions as map/single-player mode.
            distance = haversine_distance(capital.lat, capital.lng, capital.lat, capital.lng)
            current.distance_km = round(distance, 3)
            current.score = single_player_round_score(distance)
        current.submitted_answer = answer
        current.finished = True
        self.total_score += current.score

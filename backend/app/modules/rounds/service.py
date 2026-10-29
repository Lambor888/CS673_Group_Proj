"""Round logic for single-player and lobby games.

Pure Python on purpose (no FastAPI, no database) so it is easy to unit test.
This file decides WHEN a round starts and ends and WHO is still playing.
All point maths lives in app/scoring.py; this file only calls it.
"""
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable

from app.scoring import (
    SINGLE_PLAYER_ROUNDS,
    apply_penalties,
    is_lobby_game_over,
    lobby_round_penalties,
    lobby_winner,
    new_lobby_points,
    players_alive,
    round_multiplier,
    single_player_round_score,
    single_player_total,
)

# ---- Tunable settings -------------------------------------------------------
ROUND_SECONDS = 60            # time a player has to guess each round
MIN_LOBBY_PLAYERS = 2


class GameError(Exception):
    """A rule was broken (guess too late, next round too early, ...). The router turns it into HTTP 409."""


@dataclass
class PlayerGuess:
    lat: float
    lng: float
    distance_km: float            # distance from the true location


@dataclass
class GameRound:
    number: int                    # 1-based
    location: Any                  # a location.service.Location (needs .lat .lng .pano_id)
    players: set[int]              # user ids expected to guess this round
    seconds: float = ROUND_SECONDS
    started_at: float = field(default_factory=lambda: monotonic())
    guesses: dict[int, PlayerGuess] = field(default_factory=dict)
    finished: bool = False
    scored: bool = False           # set once the game has applied this round's points
    scores: dict[int, int] = field(default_factory=dict)       # single player: points earned
    penalties: dict[int, int] = field(default_factory=dict)    # lobby: points lost

    @property
    def multiplier(self) -> float:
        return round_multiplier(self.number)

    def seconds_left(self) -> float:
        return max(0.0, self.seconds - (monotonic() - self.started_at))

    def refresh(self) -> bool:
        """Close the round if everyone has guessed or the timer ran out.

        Called lazily whenever someone asks for state or guesses, so no background timer thread is needed.
        Returns True only on the call that closes the round.
        """
        if self.finished:
            return False
        if self.players <= set(self.guesses) or self.seconds_left() <= 0:
            self.finished = True
            return True
        return False

    def submit(self, player_id: int, guess: PlayerGuess) -> PlayerGuess:
        if player_id in self.guesses:
            return self.guesses[player_id]  # safe to retry
        self.refresh()
        if self.finished:
            raise GameError("Time is up for this round.")
        if player_id not in self.players:
            raise GameError("You are not playing in this round.")
        self.guesses[player_id] = guess
        self.refresh()  # the last guess closes the round immediately
        return guess

    def results(self) -> dict[int, PlayerGuess | None]:
        """Per player: their guess, or None if they ran out of time."""
        return {pid: self.guesses.get(pid) for pid in sorted(self.players)}


MakeLocation = Callable[[Any], Any]  # takes the previous pano_id (or None), returns a new Location


def _previous_pano(rounds: list[GameRound]) -> str | None:
    return getattr(rounds[-1].location, "pano_id", None) if rounds else None


# ---- Single player ----------------------------------------------------------
@dataclass
class SinglePlayerGame:
    user_id: int
    total_rounds: int = SINGLE_PLAYER_ROUNDS
    rounds: list[GameRound] = field(default_factory=list)

    @property
    def current(self) -> GameRound:
        return self.rounds[-1]

    @property
    def over(self) -> bool:
        return self.current.finished and self.current.number >= self.total_rounds

    @property
    def round_scores(self) -> list[int]:
        """Points earned in each finished round, in order."""
        return [r.scores.get(self.user_id, 0) for r in self.rounds if r.scored]

    @property
    def total_score(self) -> int:
        return single_player_total(self.round_scores)

    def refresh(self) -> None:
        self.current.refresh()
        self._settle()

    def _settle(self) -> None:
        """Once a round is closed, award its points (0 if the timer ran out)."""
        current = self.current
        if not current.finished or current.scored:
            return
        current.scored = True
        guess = current.guesses.get(self.user_id)
        current.scores = {self.user_id: single_player_round_score(guess.distance_km) if guess else 0}

    def guess(self, user_id: int, guess: PlayerGuess) -> PlayerGuess:
        self.refresh()
        result = self.current.submit(user_id, guess)
        self.refresh()
        return result

    def start_next(self, previous_round: int, make_location: MakeLocation) -> GameRound:
        """Begin round `previous_round + 1`. Repeating the same request returns the round already created."""
        self.refresh()
        if self.current.number > previous_round:
            return self.current
        if self.current.number != previous_round:
            raise GameError("Round mismatch. Reload the page.")
        if not self.current.finished:
            raise GameError("Finish the current round first.")
        if self.over:
            raise GameError("The game is over.")
        return self._add_round(make_location)

    def _add_round(self, make_location: MakeLocation) -> GameRound:
        location = make_location(_previous_pano(self.rounds))
        new_round = GameRound(number=len(self.rounds) + 1, location=location, players={self.user_id})
        self.rounds.append(new_round)
        return new_round

    @classmethod
    def start(cls, user_id: int, make_location: MakeLocation) -> "SinglePlayerGame":
        game = cls(user_id=user_id)
        game._add_round(make_location)
        return game


# ---- Lobby ------------------------------------------------------------------
@dataclass
class LobbyGame:
    lobby_id: Any
    points: dict[int, int]         # player id -> points left; 0 means eliminated
    rounds: list[GameRound] = field(default_factory=list)

    @property
    def active(self) -> set[int]:
        return set(players_alive(self.points))

    @property
    def eliminated(self) -> set[int]:
        return set(self.points) - self.active

    @property
    def over(self) -> bool:
        return is_lobby_game_over(self.points)

    @property
    def winner(self) -> int | None:
        return lobby_winner(self.points) if self.over else None

    @property
    def current(self) -> GameRound:
        return self.rounds[-1]

    def refresh(self) -> None:
        """Close the round if it is due and, exactly once per round, take points off the players."""
        self.current.refresh()
        self._settle()

    def _settle(self) -> None:
        current = self.current
        if not current.finished or current.scored:
            return
        current.scored = True
        guesses = {}
        for pid in current.players:
            guess = current.guesses.get(pid)
            guesses[pid] = (guess.lat, guess.lng) if guess else None
        penalties = lobby_round_penalties(guesses, current.location.lat, current.location.lng, current.number)
        new_points = apply_penalties(self.points, penalties)
        if not players_alive(new_points):
            # Only possible when nobody guessed and the penalty would wipe out every
            # player at once. There would be no winner, so the round does not count.
            penalties = {pid: 0 for pid in penalties}
        else:
            self.points = new_points
        current.penalties = penalties

    def guess(self, user_id: int, guess: PlayerGuess) -> PlayerGuess:
        self.refresh()
        if self.over:
            raise GameError("The game is over.")
        result = self.current.submit(user_id, guess)
        self.refresh()
        return result

    def start_next(self, previous_round: int, make_location: MakeLocation) -> GameRound:
        """Begin round `previous_round + 1`. Any player may call it; repeats return the existing round."""
        self.refresh()
        if self.current.number > previous_round:
            return self.current
        if self.current.number != previous_round:
            raise GameError("Round mismatch. Reload the page.")
        if not self.current.finished:
            raise GameError("The current round is still running.")
        if self.over:
            raise GameError("The game is over.")
        return self._add_round(make_location)

    def _add_round(self, make_location: MakeLocation) -> GameRound:
        location = make_location(_previous_pano(self.rounds))
        new_round = GameRound(number=len(self.rounds) + 1, location=location, players=self.active)
        self.rounds.append(new_round)
        return new_round

    @classmethod
    def start(cls, lobby_id: Any, player_ids: set[int], make_location: MakeLocation) -> "LobbyGame":
        if len(player_ids) < MIN_LOBBY_PLAYERS:
            raise GameError(f"At least {MIN_LOBBY_PLAYERS} players are needed to start.")
        game = cls(lobby_id=lobby_id, points=new_lobby_points(sorted(player_ids)))
        game._add_round(make_location)
        return game

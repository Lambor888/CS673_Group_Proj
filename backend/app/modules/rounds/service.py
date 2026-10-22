"""Round logic for single-player and lobby games.
"""
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable

# ---- Tunable settings -------------------------------------------------------
ROUND_SECONDS = 60            # time a player has to guess each round
SINGLE_PLAYER_ROUNDS = 5      # single-player games are exactly this long
MULTIPLIER_START_ROUND = 4    # lobby: first round whose multiplier is above 1x
MULTIPLIER_STEP = 0.5         # lobby: how much the multiplier grows each round after that
MIN_LOBBY_PLAYERS = 2


class GameError(Exception):
    """A rule was broken (guess too late, next round too early, ...). The router turns it into HTTP 409."""


def round_multiplier(round_number: int) -> float:
    """Lobby damage multiplier. 1.0 for early rounds, then grows every round (4 -> 1.5, 5 -> 2.0, ...).

    It never stops growing, which is what guarantees a lobby game eventually ends.
    """
    if round_number < MULTIPLIER_START_ROUND:
        return 1.0
    return 1.0 + MULTIPLIER_STEP * (round_number - MULTIPLIER_START_ROUND + 1)


@dataclass
class PlayerGuess:
    lat: float
    lng: float
    distance_km: float


@dataclass
class GameRound:
    number: int                    # 1-based
    location: Any                  # a location.service.Location; this file never inspects it
    players: set[int]              # user ids expected to guess this round
    seconds: float = ROUND_SECONDS
    started_at: float = field(default_factory=lambda: monotonic())
    guesses: dict[int, PlayerGuess] = field(default_factory=dict)
    finished: bool = False

    @property
    def multiplier(self) -> float:
        return round_multiplier(self.number)

    def seconds_left(self) -> float:
        return max(0.0, self.seconds - (monotonic() - self.started_at))

    def refresh(self) -> bool:
        """Close the round if everyone has guessed or the timer ran out.
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
        """Per player: their guess, or None if they ran out of time. This is the scoring module's input."""
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

    def refresh(self) -> None:
        self.current.refresh()

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
def no_elimination(game: "LobbyGame", finished_round: GameRound) -> set[int]:
    """Default hook: nobody is ever eliminated (so a lobby game never ends).
    """
    return set()


round_end_hook: Callable[["LobbyGame", GameRound], set[int]] = no_elimination


@dataclass
class LobbyGame:
    lobby_id: Any
    active: set[int]
    eliminated: set[int] = field(default_factory=set)
    rounds: list[GameRound] = field(default_factory=list)
    _handled_round: int = 0  # last round number whose end-of-round hook has run

    @property
    def current(self) -> GameRound:
        return self.rounds[-1]

    @property
    def over(self) -> bool:
        return len(self.active) <= 1

    @property
    def winner(self) -> int | None:
        return next(iter(self.active)) if len(self.active) == 1 else None

    def refresh(self) -> None:
        """Close the round if due and, exactly once per round, let scoring decide who is out."""
        self.current.refresh()
        if self.current.finished and self._handled_round < self.current.number:
            self._handled_round = self.current.number
            self.eliminate(round_end_hook(self, self.current))

    def eliminate(self, user_ids: set[int]) -> None:
        user_ids = set(user_ids) & self.active
        if user_ids == self.active:
            raise ValueError("Cannot eliminate every remaining player.")
        self.active -= user_ids
        self.eliminated |= user_ids

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
        new_round = GameRound(number=len(self.rounds) + 1, location=location, players=set(self.active))
        self.rounds.append(new_round)
        return new_round

    @classmethod
    def start(cls, lobby_id: Any, player_ids: set[int], make_location: MakeLocation) -> "LobbyGame":
        if len(player_ids) < MIN_LOBBY_PLAYERS:
            raise GameError(f"At least {MIN_LOBBY_PLAYERS} players are needed to start.")
        game = cls(lobby_id=lobby_id, active=set(player_ids))
        game._add_round(make_location)
        return game

import math

# For Single player
MAX_ROUND_SCORE = 5000        # max possible score for each round
PERFECT_RADIUS_KM = 25        # perfect score
SCORE_DECAY_KM = 1500         # bigger number = score drops more slowly?
SINGLE_PLAYER_ROUNDS = 5      # number of rounds in a single player game

# Lobby game
STARTING_POINTS = 10000       # every player starts with this
PENALTY_PER_KM = 1.0          # points lost per km away from the closest guess
NO_GUESS_PENALTY_KM = 2000    # used when a player's timer runs out with no guess
MULTIPLIER_START_ROUND = 5    # penalties start growing from this round
MULTIPLIER_STEP = 0.25        # +25% penalty for every round after that


#Base function getting the distance between two lat/lon points
def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    a = min(1.0, max(0.0, a))  # Avoid floating-point errors at antipodal points.
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# For Single player game: points go UP, the closer the guess the better
def single_player_round_score(distance_km: float) -> int:
    if distance_km <= PERFECT_RADIUS_KM:
        return MAX_ROUND_SCORE  #5000
    extra = distance_km - PERFECT_RADIUS_KM
    return round(MAX_ROUND_SCORE * math.exp(-extra / SCORE_DECAY_KM))    
          #(125 far, so extra - 100. thats 0.067 (100/1500), exp(-0.067) ~ 0.935, so score drops slightly, score = 4678)


def single_player_total(round_scores: list[int]) -> int:
    return sum(round_scores)


# Lobby game: everyone starts at STARTING_POINTS = 10,000 and points go DOWN
# Keys everywhere are player ids (Player.p_id, same keys as Lobby.players)
def new_lobby_points(player_ids) -> dict[int, int]:
    return {pid: STARTING_POINTS for pid in player_ids}


def round_multiplier(round_number: int) -> float:      #makes each round hurt more, after round 5 by 0.25 per round.
    if round_number < MULTIPLIER_START_ROUND:
        return 1.0
    return 1.0 + MULTIPLIER_STEP * (round_number - MULTIPLIER_START_ROUND + 1)    # e.g., round 6: 1.0 + 0.25 * (6 - 5 + 1) = 1.5


def lobby_round_penalties(guesses: dict, true_lat: float, true_lng: float,
                          round_number: int = 1) -> dict[int, int]:
    """
    guesses: {player_id: (lat, lng)} or {player_id: None} if they did not guess.
    The closest guess loses nothing. Everyone else loses points based on the
    distance between their guess and the closest guess, times the round multiplier.
    Returns {player_id: points_to_lose}.
    """
    distance_to_truth = {
        pid: haversine_distance(g[0], g[1], true_lat, true_lng)
        for pid, g in guesses.items() if g is not None
    }
    multiplier = round_multiplier(round_number)

    if not distance_to_truth:  # nobody guessed
        return {pid: round(NO_GUESS_PENALTY_KM * PENALTY_PER_KM * multiplier)
                for pid in guesses}

    best_id = min(distance_to_truth, key=lambda pid: (distance_to_truth[pid], pid))
    best_lat, best_lng = guesses[best_id]

    penalties = {}
    for pid, g in guesses.items():
        if pid == best_id:
            penalties[pid] = 0
            continue
        if g is None:
            km = NO_GUESS_PENALTY_KM
        else:
            km = haversine_distance(g[0], g[1], best_lat, best_lng)
        penalties[pid] = round(km * PENALTY_PER_KM * multiplier)
    return penalties


def apply_penalties(points: dict[int, int], penalties: dict[int, int]) -> dict[int, int]:   #for 0, loses nothing, and subtracts from points)
    return {pid: max(0, p - penalties.get(pid, 0)) for pid, p in points.items()}  


def players_alive(points: dict[int, int]) -> list[int]:
    return [pid for pid, p in points.items() if p > 0]    # returns ids of those with more than 0 points left, (no negative).


def is_lobby_game_over(points: dict[int, int]) -> bool:   # returns True if only one or zero players have points left.
    return len(players_alive(points)) <= 1


def lobby_winner(points: dict[int, int]) -> int | None:   # returns the player id with the most points, or None if nobody has points or it is a tie.
    ranked = sorted(points.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] == 0:
        return None
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]
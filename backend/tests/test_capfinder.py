from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.capfinder import router, service
from app.modules.location.service import CAPITALS, CapitalLocation, generate_capital_location
from app.modules.profile.models import GameHistory, RoundResult
from app.scoring import MAX_ROUND_SCORE, haversine_distance, single_player_round_score
from tests.test_lobby_api import login_user


@pytest.fixture(autouse=True)
def fresh_game(monkeypatch):
    monkeypatch.setattr(router, 'games', {})
    monkeypatch.setattr(service, 'generate_capital_location', lambda used=(): CapitalLocation(
        code='FR', country='France', capitals=[{'name': 'Paris', 'lat': 48.8566, 'lng': 2.3522}]))


def start(client, headers, previous=None):
    return client.post('/capfinder/round', headers=headers, json={'previous_round_id': previous})


def guess(client, headers, round_id, lat=48.8566, lng=2.3522):
    return client.post(f'/capfinder/round/{round_id}/guess', headers=headers, json={'lat': lat, 'lng': lng})


def test_dataset_coverage_and_cycles():
    assert len(CAPITALS) == len({c.code for c in CAPITALS}) == 195
    assert {'GW', 'VA', 'PS'} <= {c.code for c in CAPITALS}
    assert all(c.capitals for c in CAPITALS)
    for c in CAPITALS:
        for p in c.capitals:
            assert -90 <= p.lat <= 90 and -180 <= p.lng <= 180
    used = {c.code for c in CAPITALS if c.code != 'US'}
    assert generate_capital_location(used).code == 'US'
    used.add('US')
    assert generate_capital_location(used).code in used


def test_login_required(client):
    assert start(client, {}).status_code == 401
    assert client.get('/capfinder').status_code == 401
    assert guess(client, {}, uuid4()).status_code == 401


def test_hidden_answer_and_resume(client):
    _, headers = login_user(client, 'capital1')
    assert client.get('/capfinder', headers=headers).status_code == 404
    response = start(client, headers)
    data = response.json()
    assert response.status_code == 200 and data['country'] == 'France'
    assert data['number'] == 1 and data['total_score'] == 0
    assert 0 < data['seconds_left'] <= 60
    assert not data['finished'] and data['guess'] is None
    assert 'Paris' not in response.text and '48.8566' not in response.text
    assert 'capitals' not in data and 'answer' not in data
    assert start(client, headers).json()['round_id'] == data['round_id']
    assert client.get('/capfinder', headers=headers).json()['round_id'] == data['round_id']
    assert start(client, headers, data['round_id']).status_code == 409


def test_unlimited_rounds_scores_and_no_database_writes(client, db_session):
    _, headers = login_user(client, 'capital2')
    data = start(client, headers).json()
    for number in range(1, 9):
        assert data['number'] == number
        submitted = guess(client, headers, data['round_id']).json()
        assert submitted['finished'] and submitted['score'] == MAX_ROUND_SCORE
        assert submitted['total_score'] == number * MAX_ROUND_SCORE
        retry = guess(client, headers, data['round_id'], 0, 0).json()
        assert retry == submitted
        next_state = start(client, headers, data['round_id']).json()
        assert next_state['number'] == number + 1
        assert start(client, headers, data['round_id']).status_code == 409
        assert guess(client, headers, data['round_id']).status_code == 409
        data = next_state
    assert db_session.scalar(select(func.count()).select_from(RoundResult)) == 0
    assert db_session.scalar(select(func.count()).select_from(GameHistory)) == 0


def test_timeout_and_user_isolation(client):
    user_id, headers = login_user(client, 'capital3')
    _, other = login_user(client, 'capital4')
    data = start(client, headers).json()
    other_state = start(client, other).json()
    assert data['round_id'] != other_state['round_id']
    assert guess(client, other, data['round_id']).status_code == 409
    router.games[user_id].current.started_at -= 61
    timed_out = client.get('/capfinder', headers=headers).json()
    assert timed_out['finished'] and timed_out['score'] == 0
    assert timed_out['distance_km'] is None and timed_out['total_score'] == 0
    assert guess(client, headers, data['round_id']).status_code == 409
    assert start(client, headers, data['round_id']).json()['number'] == 2
    assert not client.get('/capfinder', headers=other).json()['finished']


def test_distance_formula_and_multiple_capitals(client, monkeypatch):
    south_africa = next(c for c in CAPITALS if c.code == 'ZA')
    monkeypatch.setattr(service, 'generate_capital_location', lambda used=(): south_africa)
    _, headers = login_user(client, 'capital5')
    data = start(client, headers).json()
    cape_town = next(c for c in south_africa.capitals if c.name == 'Cape Town')
    result = guess(client, headers, data['round_id'], cape_town.lat, cape_town.lng).json()
    assert result['score'] == 5000 and result['distance_km'] == 0
    data = start(client, headers, data['round_id']).json()
    distance = min(haversine_distance(0, 0, c.lat, c.lng) for c in south_africa.capitals)
    result = guess(client, headers, data['round_id'], 0, 0).json()
    assert result['score'] == single_player_round_score(distance)
    assert result['distance_km'] == round(distance, 3)


@pytest.mark.parametrize('body', [{'lat': 91, 'lng': 0}, {'lat': 0, 'lng': 181},
                                {'lat': 0, 'lng': 0, 'score': 5000}])
def test_invalid_input(client, body):
    _, headers = login_user(client, 'capital6')
    data = start(client, headers).json()
    assert client.post(f"/capfinder/round/{data['round_id']}/guess", headers=headers, json=body).status_code == 422

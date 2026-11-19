from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.capfinder import router, service
from app.modules.location.service import CAPITALS, CapitalLocation, generate_capital_location
from app.modules.location.country import CountryView
from app.modules.profile.models import GameHistory, RoundResult
from app.scoring import MAX_ROUND_SCORE, haversine_distance, single_player_round_score
from tests.test_lobby_api import login_user


@pytest.fixture(autouse=True)
def fresh_game(monkeypatch):
    monkeypatch.setattr(router, 'games', {})
    monkeypatch.setattr(service, 'choose_mode', lambda: 'map')
    monkeypatch.setattr(service, 'lookup_country', lambda code: CountryView(
        place_id=f'country-{code}', bounds={'north': 51, 'south': 41, 'east': 10, 'west': -5}))
    monkeypatch.setattr(service, 'generate_capital_location', lambda used=(): CapitalLocation(
        code='FR', country='France', capitals=[{'name': 'Paris', 'lat': 48.8566, 'lng': 2.3522}]))


def start(client, headers, previous=None):
    return client.post('/capfinder/round', headers=headers, json={'previous_round_id': previous})


def guess(client, headers, round_id, lat=48.8566, lng=2.3522):
    return client.post(f'/capfinder/round/{round_id}/guess', headers=headers, json={'lat': lat, 'lng': lng})


def test_dataset_coverage_and_cycles():
    assert len(CAPITALS) == len({c.code for c in CAPITALS}) == 100
    assert {'NZ', 'NO', 'CH', 'SG', 'IS', 'US', 'CN', 'ZA'} <= {c.code for c in CAPITALS}
    assert not {'GW', 'VA', 'NR', 'TV'} & {c.code for c in CAPITALS}
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


@pytest.fixture
def text_mode(monkeypatch, fresh_game):
    monkeypatch.setattr(service, 'choose_mode', lambda: 'text')


def answer(client, headers, round_id, value):
    return client.post(f'/capfinder/round/{round_id}/answer', headers=headers, json={'answer': value})


@pytest.mark.usefixtures('text_mode')
def test_text_country_id_hidden_answer_and_resume(client):
    _, headers = login_user(client, 'text1')
    response = start(client, headers)
    assert response.status_code == 200
    data = response.json()
    assert data['mode'] == 'text' and data['country_place_id'] == 'country-FR'
    assert data['country_bounds']['north'] == 51
    assert data['submitted_answer'] is None and data['correct'] is None
    assert 'Paris' not in response.text and '48.8566' not in response.text
    assert data['guess'] is None
    assert start(client, headers).json()['round_id'] == data['round_id']
    resumed = client.get('/capfinder', headers=headers).json()
    assert resumed['round_id'] == data['round_id'] and resumed['mode'] == 'text'
    assert guess(client, headers, data['round_id']).status_code == 409


@pytest.mark.usefixtures('text_mode')
def test_text_case_insensitive_score_reuses_distance_and_is_idempotent(client, monkeypatch):
    calls = []
    def distance(*coordinates):
        calls.append(coordinates)
        return haversine_distance(*coordinates)
    monkeypatch.setattr(service, 'haversine_distance', distance)
    _, headers = login_user(client, 'text2')
    data = start(client, headers).json()
    result = answer(client, headers, data['round_id'], '  pArIs  ').json()
    assert result['correct'] and result['finished']
    assert result['score'] == result['total_score'] == MAX_ROUND_SCORE
    assert result['distance_km'] == 0 and result['guess'] is None
    assert calls == [(48.8566, 2.3522, 48.8566, 2.3522)]
    assert answer(client, headers, data['round_id'], 'London').json() == result
    assert len(calls) == 1


@pytest.mark.usefixtures('text_mode')
def test_text_wrong_answer_ends_round_and_cannot_be_replaced(client):
    _, headers = login_user(client, 'text3')
    data = start(client, headers).json()
    result = answer(client, headers, data['round_id'], 'London').json()
    assert result['finished'] and result['correct'] is False
    assert result['score'] == result['total_score'] == 0
    assert result['distance_km'] is None
    assert answer(client, headers, data['round_id'], 'Paris').json() == result


@pytest.mark.usefixtures('text_mode')
def test_text_timeout_and_other_user_cannot_submit(client):
    user_id, headers = login_user(client, 'text4')
    _, other = login_user(client, 'text5')
    data = start(client, headers).json()
    start(client, other)
    assert answer(client, other, data['round_id'], 'Paris').status_code == 409
    router.games[user_id].current.started_at -= 61
    state = client.get('/capfinder', headers=headers).json()
    assert state['finished'] and state['score'] == 0 and state['correct'] is None
    assert answer(client, headers, data['round_id'], 'Paris').status_code == 409
    assert start(client, headers, data['round_id']).json()['number'] == 2


@pytest.mark.usefixtures('text_mode')
def test_text_multi_capital_unlimited_rounds_and_no_history(client, monkeypatch, db_session):
    south_africa = next(c for c in CAPITALS if c.code == 'ZA')
    monkeypatch.setattr(service, 'generate_capital_location', lambda used=(): south_africa)
    _, headers = login_user(client, 'text6')
    data = start(client, headers).json()
    for number in range(1, 8):
        capital = south_africa.capitals[(number - 1) % len(south_africa.capitals)]
        result = answer(client, headers, data['round_id'], capital.name.upper()).json()
        assert result['total_score'] == number * MAX_ROUND_SCORE
        data = start(client, headers, data['round_id']).json()
        assert data['number'] == number + 1 and data['submitted_answer'] is None
    assert db_session.scalar(select(func.count()).select_from(RoundResult)) == 0
    assert db_session.scalar(select(func.count()).select_from(GameHistory)) == 0


@pytest.mark.parametrize('value', ['', '  ', 123, None, 'x' * 201])
@pytest.mark.usefixtures('text_mode')
def test_invalid_text_answer_does_not_end_round(client, value):
    _, headers = login_user(client, 'text7')
    data = start(client, headers).json()
    assert answer(client, headers, data['round_id'], value).status_code == 422
    assert not client.get('/capfinder', headers=headers).json()['finished']


@pytest.mark.usefixtures('text_mode')
def test_text_auth_and_score_injection(client):
    assert start(client, {}).status_code == 401
    assert client.get('/capfinder').status_code == 401
    assert answer(client, {}, uuid4(), 'Paris').status_code == 401
    _, headers = login_user(client, 'text8')
    data = start(client, headers).json()
    assert client.post(f"/capfinder/round/{data['round_id']}/answer", headers=headers,
                       json={'answer': 'Paris', 'score': 5000}).status_code == 422


@pytest.mark.usefixtures('text_mode')
def test_lookup_failure_preserves_finished_round_and_score(client, monkeypatch):
    from app.modules.location.service import LocationError
    _, headers = login_user(client, 'text9')
    data = start(client, headers).json()
    answer(client, headers, data['round_id'], 'Paris')
    def unavailable(code):
        raise LocationError('Enable Geocoding API.')
    monkeypatch.setattr(service, 'lookup_country', unavailable)
    assert start(client, headers, data['round_id']).status_code == 503
    assert client.get('/capfinder', headers=headers).json()['round_id'] == data['round_id']
    assert start(client, headers).status_code == 200
    _, other = login_user(client, 'text10')
    assert start(client, other).status_code == 503
    assert client.get('/capfinder', headers=other).status_code == 404


def test_modes_change_only_on_new_round_and_share_score(client, monkeypatch):
    choices = iter(['text', 'map', 'text'])
    chosen = []
    def choose():
        mode = next(choices)
        chosen.append(mode)
        return mode
    monkeypatch.setattr(service, 'choose_mode', choose)
    _, headers = login_user(client, 'mixed1')
    first = start(client, headers).json()
    assert first['mode'] == 'text'
    # Resume/poll and an early-next request must not reroll a playable round.
    assert start(client, headers).json()['round_id'] == first['round_id']
    assert client.get('/capfinder', headers=headers).json()['mode'] == 'text'
    assert start(client, headers, first['round_id']).status_code == 409
    assert chosen == ['text']
    assert guess(client, headers, first['round_id']).status_code == 409
    result = answer(client, headers, first['round_id'], 'pArIs').json()
    assert result['score'] == MAX_ROUND_SCORE
    second = start(client, headers, first['round_id']).json()
    assert second['mode'] == 'map' and second['number'] == 2
    assert second['total_score'] == MAX_ROUND_SCORE
    assert second['country_place_id'] is None and second['country_bounds'] is None
    assert second['submitted_answer'] is None and second['correct'] is None
    assert answer(client, headers, second['round_id'], 'Paris').status_code == 409
    assert guess(client, headers, second['round_id']).json()['total_score'] == 2 * MAX_ROUND_SCORE
    third = start(client, headers, second['round_id']).json()
    assert third['mode'] == 'text' and third['number'] == 3
    assert third['guess'] is None and third['country_place_id'] == 'country-FR'
    assert third['total_score'] == 2 * MAX_ROUND_SCORE
    assert start(client, headers, first['round_id']).status_code == 409
    assert chosen == ['text', 'map', 'text']


def test_client_cannot_select_mode_or_use_old_mode_routes(client):
    _, headers = login_user(client, 'mixed2')
    for requested_mode in ('map', 'text'):
        assert client.post('/capfinder/round', headers=headers,
                           json={'mode': requested_mode}).status_code == 422
    # The server's fixture chooses map; a URL parameter cannot force text.
    response = client.post('/capfinder/round?mode=text', headers=headers, json={})
    data = response.json()
    assert data['mode'] == 'map'
    assert client.get('/capfinder?mode=text', headers=headers).json()['round_id'] == data['round_id']
    assert client.post('/capfinder/text/round', headers=headers, json={}).status_code == 404
    assert client.get('/capfinder/text', headers=headers).status_code == 404
    assert answer(client, headers, data['round_id'], 'Paris').status_code == 409
    state = client.get('/capfinder', headers=headers).json()
    assert state['total_score'] == 0 and not state['finished']

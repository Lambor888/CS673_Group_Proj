from types import SimpleNamespace
from unittest.mock import MagicMock
import json

import pytest

from app.main import app
from app.modules.auth.deps import get_current_user
from app.modules.location import service
from app.modules.singlePlayer import router as game


@pytest.fixture(autouse=True)
def reset_rounds():
    game.rounds.clear()
    yield
    game.rounds.clear()


def authenticate(user_id=1):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)


def test_round_guess_next_and_retries(client, monkeypatch):
    authenticate()
    locations = iter([
        service.Location(pano_id='first', lat=0, lng=0),
        service.Location(pano_id='second', lat=20, lng=30),
    ])
    calls = []
    def generate(exclude=None):
        calls.append(exclude)
        return next(locations)
    monkeypatch.setattr(game, 'generate_location', generate)
    first = client.post('/singleplayer/round', json={}).json()
    assert client.post('/singleplayer/round', json={}).json() == first
    next_body = {'previous_round_id': first['round_id']}
    assert client.post('/singleplayer/round', json=next_body).status_code == 409
    path = f"/singleplayer/round/{first['round_id']}/guess"
    assert client.post(path, json={'lat': 100, 'lng': 0}).status_code == 422
    assert client.post(path, json={'lat': 0, 'lng': 1, 'answer': 0}).status_code == 422
    authenticate(2)
    assert client.post(path, json={'lat': 0, 'lng': 1}).status_code == 404
    authenticate()
    result = client.post(path, json={'lat': 0, 'lng': 1}).json()
    assert result['distance_km'] == pytest.approx(111.195, abs=0.001)
    assert client.post(path, json={'lat': 50, 'lng': 80}).json() == result
    assert client.post('/singleplayer/round', json={}).json()['result'] == result
    second = client.post('/singleplayer/round', json=next_body).json()
    assert second['round_id'] != first['round_id']
    assert second['result'] is None
    assert client.post('/singleplayer/round', json=next_body).json() == second
    assert client.post(path, json={'lat': 0, 'lng': 1}).status_code == 404
    assert calls == [None, 'first']


def test_authentication_required(client):
    assert client.post('/singleplayer/round', json={}).status_code == 401


def test_location_failure_preserves_completed_round(client, monkeypatch):
    authenticate()
    game.rounds[1] = game.Round(location=service.Location(pano_id='old', lat=0, lng=0),
                                result=game.Result(distance_km=0, guess=game.Guess(lat=0, lng=0)))
    previous = game.rounds[1]
    def fail(_):
        raise service.LocationError('Google unavailable')
    monkeypatch.setattr(game, 'generate_location', fail)
    response = client.post('/singleplayer/round', json={'previous_round_id': str(previous.id)})
    assert response.status_code == 503
    assert game.rounds[1] is previous


@pytest.mark.parametrize('status', ['ZERO_RESULTS', 'REQUEST_DENIED', 'OK'])
def test_google_metadata(monkeypatch, status):
    monkeypatch.setattr(service.settings, 'google_maps_api_key', 'test-only')
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({
        'status': status, 'pano_id': 'verified', 'location': {'lat': 12.3, 'lng': 45.6},
        'copyright': '© 2026 Google',
    })
    monkeypatch.setattr(service, 'urlopen', lambda *args, **kwargs: response)
    if status == 'REQUEST_DENIED':
        with pytest.raises(service.LocationError, match='denied'):
            service.lookup_location(0, 0)
    else:
        location = service.lookup_location(0, 0)
        if status == 'ZERO_RESULTS':
            assert location is None
        else:
            assert (location.lat, location.lng) == (12.3, 45.6)


def test_location_retry_limit_and_exclusion(monkeypatch):
    calls = []
    def lookup(lat, lng):
        calls.append((lat, lng))
        return service.Location(pano_id='same', lat=lat, lng=lng)
    monkeypatch.setattr(service, 'lookup_location', lookup)
    with pytest.raises(service.LocationError, match='No new'):
        service.generate_location('same')
    assert len(calls) == 4


def test_missing_server_key(monkeypatch):
    monkeypatch.setattr(service.settings, 'google_maps_api_key', '')
    with pytest.raises(service.LocationError, match='GOOGLE_MAPS_API_KEY'):
        service.lookup_location(0, 0)


@pytest.mark.parametrize('attribution,accepted', [
    ('© 2026 Google', True), ('© Google', True),
    ('© Jeff Wu', False), ('', False), (None, False),
    ('© Google Contributor', False),
])
def test_metadata_filters_contributor_imagery(monkeypatch, attribution, accepted):
    monkeypatch.setattr(service.settings, 'google_maps_api_key', 'test-only')
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({
        'status': 'OK', 'pano_id': 'candidate',
        'location': {'lat': 40.758, 'lng': -73.9855},
        'copyright': attribution,
    })
    monkeypatch.setattr(service, 'urlopen', lambda *args, **kwargs: response)
    assert (service.lookup_location(40.758, -73.9855) is not None) == accepted


def test_generation_skips_rejected_candidate(monkeypatch):
    valid = service.Location(pano_id='google-panorama', lat=1, lng=2)
    responses = iter([None, valid])
    monkeypatch.setattr(service, 'lookup_location', lambda *args: next(responses))
    assert service.generate_location() == valid

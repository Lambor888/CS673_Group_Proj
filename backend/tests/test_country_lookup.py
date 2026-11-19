import io
import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from app.modules.location import country
from app.modules.location.service import LocationError


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(country, 'country_cache', {})
    monkeypatch.setattr(country.settings, 'google_maps_api_key', 'test-secret')


def response_data():
    return {'status': 'OK', 'results': [{
        'types': ['country', 'political'], 'place_id': 'country-FR',
        'address_components': [{'short_name': 'FR', 'types': ['country', 'political']}],
        'geometry': {'viewport': {'northeast': {'lat': 51, 'lng': 10},
                                  'southwest': {'lat': 41, 'lng': -5}}},
    }]}


def test_country_request_and_cache_expiration(monkeypatch):
    calls = []
    clock = [100.0]
    monkeypatch.setattr(country, 'monotonic', lambda: clock[0])
    def request(url, timeout):
        query = parse_qs(urlparse(url).query)
        assert query['components'] == ['country:FR'] and timeout == 4
        calls.append(url)
        return io.StringIO(json.dumps(response_data()))
    monkeypatch.setattr(country, 'urlopen', request)
    result = country.lookup_country('fr')
    assert result.place_id == 'country-FR' and result.bounds.west == -5
    assert country.lookup_country('FR') == result and len(calls) == 1
    clock[0] += country.CACHE_SECONDS + 1
    country.lookup_country('FR')
    assert len(calls) == 2


@pytest.mark.parametrize('change', ['city', 'wrong_country', 'bad_bounds', 'missing_id'])
def test_reject_unusable_results(monkeypatch, change):
    data = response_data()
    row = data['results'][0]
    if change == 'city':
        row['types'] = ['locality']
    elif change == 'wrong_country':
        row['address_components'][0]['short_name'] = 'GB'
    elif change == 'bad_bounds':
        row['geometry']['viewport']['northeast']['lat'] = 999
    else:
        del row['place_id']
    monkeypatch.setattr(country, 'urlopen', lambda *a, **kw: io.StringIO(json.dumps(data)))
    with pytest.raises(LocationError):
        country.lookup_country('FR')
    assert not country.country_cache


def test_api_denial_and_network_error_never_expose_key(monkeypatch):
    data = {'status': 'REQUEST_DENIED', 'error_message': 'test-secret'}
    monkeypatch.setattr(country, 'urlopen', lambda *a, **kw: io.StringIO(json.dumps(data)))
    with pytest.raises(LocationError, match='Geocoding API') as error:
        country.lookup_country('FR')
    assert 'test-secret' not in str(error.value)
    def offline(*a, **kw):
        raise URLError('url?key=test-secret')
    monkeypatch.setattr(country, 'urlopen', offline)
    with pytest.raises(LocationError) as error:
        country.lookup_country('FR')
    assert 'test-secret' not in str(error.value)

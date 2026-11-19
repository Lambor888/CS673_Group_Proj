"""Resolve country IDs/display bounds for Google's COUNTRY feature layer."""
import json
import re
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import settings
from app.modules.location.service import LocationError


class CountryBounds(BaseModel):
    model_config = ConfigDict(frozen=True)
    north: float = Field(ge=-90, le=90, allow_inf_nan=False)
    south: float = Field(ge=-90, le=90, allow_inf_nan=False)
    east: float = Field(ge=-180, le=180, allow_inf_nan=False)
    west: float = Field(ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode='after')
    def nonempty(self):
        if self.north <= self.south or self.east == self.west:
            raise ValueError('Country bounds must have nonzero area.')
        return self


class CountryView(BaseModel):
    model_config = ConfigDict(frozen=True)
    place_id: str = Field(min_length=1)
    bounds: CountryBounds


# In-memory, bounded to ISO country codes. Coordinates expire after one day.
country_cache: dict[str, tuple[float, CountryView]] = {}
CACHE_SECONDS = 24 * 60 * 60


def lookup_country(code: str) -> CountryView:
    code = code.strip().upper()
    if not re.fullmatch(r'[A-Z]{2}', code):
        raise LocationError('Invalid country code.')
    cached = country_cache.get(code)
    if cached and monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    country_cache.pop(code, None)
    key = settings.google_maps_api_key.strip()
    if not key:
        raise LocationError('Configure GOOGLE_MAPS_API_KEY in backend/.env for capital name mode.')
    query = urlencode({'components': f'country:{code}', 'language': 'en', 'key': key})
    try:
        with urlopen('https://maps.googleapis.com/maps/api/geocode/json?' + query, timeout=4) as response:
            data = json.load(response)
    except (URLError, TimeoutError, OSError, ValueError):
        # The request URL and Google's raw error may contain credentials.
        raise LocationError('Unable to reach Google Geocoding. Please try again.') from None
    if not isinstance(data, dict):
        raise LocationError('Google returned invalid country data.')
    if data.get('status') != 'OK':
        messages = {
            'REQUEST_DENIED': 'Enable Geocoding API and allow it on the backend Google API key.',
            'OVER_QUERY_LIMIT': 'Google Geocoding request limit reached. Please try later.',
            'ZERO_RESULTS': 'Google could not find this country. Please try again.',
        }
        raise LocationError(messages.get(data.get('status'), 'Google country lookup failed. Please try again.'))
    try:
        for result in data['results']:
            # Reject a city/address result or a country other than the one requested.
            if 'country' not in result.get('types', []):
                continue
            if not any('country' in item.get('types', []) and item.get('short_name') == code
                       for item in result.get('address_components', [])):
                continue
            viewport = result['geometry']['viewport']
            view = CountryView(place_id=result['place_id'], bounds=CountryBounds(
                north=viewport['northeast']['lat'], east=viewport['northeast']['lng'],
                south=viewport['southwest']['lat'], west=viewport['southwest']['lng']))
            country_cache[code] = (monotonic(), view)
            return view
    except (KeyError, TypeError, AttributeError, ValidationError):
        raise LocationError('Google returned invalid country data.') from None
    raise LocationError('Google could not find a matching country boundary. Please try again.')

import json
import random
import re
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import BaseModel, Field, ValidationError

from app.config import settings


class LocationError(Exception):
    pass


class Location(BaseModel):
    pano_id: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


# Pre-loaded dataset: one spot per line in locations.json, each on official Google Street View.
LOCATIONS = json.loads((Path(__file__).parent / "locations.json").read_text(encoding="utf-8"))


def lookup_location(lat: float, lng: float) -> Location | None:
    key = settings.google_maps_api_key.strip()
    if not key:
        raise LocationError("Configure GOOGLE_MAPS_API_KEY in backend/.env before starting a round.")
    query = urlencode({"location": f"{lat},{lng}", "key": key, "radius": 200, "source": "outdoor"})
    try:
        with urlopen("https://maps.googleapis.com/maps/api/streetview/metadata?" + query, timeout=4) as response:
            data = json.load(response)
    except (URLError, TimeoutError, OSError, ValueError):
        # Never expose the request URL: it contains the server API key.
        raise LocationError("Unable to reach Google Street View. Please try again.") from None
    if not isinstance(data, dict):
        raise LocationError("Google returned invalid street-view metadata.")
    status = data.get("status")
    if status in ("ZERO_RESULTS", "NOT_FOUND"):
        return None
    if status != "OK":
        messages = {
            "REQUEST_DENIED": "Google denied the request. Check the server key and enable Street View Static API.",
            "OVER_QUERY_LIMIT": "Google Street View request limit reached. Please try later.",
        }
        raise LocationError(messages.get(status, "Google Street View is unavailable. Please try again."))
    # Metadata may select contributor panoramas even for outdoor requests.
    # Accept only unambiguous Google attribution; this does not guarantee tile availability.
    attribution = data.get("copyright", "")
    if not isinstance(attribution, str) or not re.fullmatch(
        r"(?:©\s*)?(?:\d{4}\s+)?Google", attribution.strip(), re.IGNORECASE
    ):
        return None
    try:
        return Location(pano_id=data["pano_id"], lat=data["location"]["lat"], lng=data["location"]["lng"])
    except (KeyError, TypeError, ValidationError):
        raise LocationError("Google returned invalid street-view metadata.") from None


def generate_location(used_panos=()) -> Location:
    """Pick a random spot from locations.json that this game has not shown yet."""
    for spot in random.sample(LOCATIONS, len(LOCATIONS)):
        location = lookup_location(spot["lat"], spot["lng"])
        if location is not None and location.pano_id not in used_panos:
            return location
    raise LocationError("No new street view found. Please try again.")

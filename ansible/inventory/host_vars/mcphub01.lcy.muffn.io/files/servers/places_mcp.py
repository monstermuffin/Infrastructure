# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "mcp==1.30.0",
#   "httpx==0.28.1",
# ]
# ///
"""Minimal Google Maps MCP server for voice assistants.

Two tools, each one Google API call, returning short plain-text answers:
  find_place   Places API (New) Text Search with today's hours worked out
  travel_time  Routes API computeRoutes from home (or a given origin)

Env: GOOGLE_MAPS_API_KEY, HOME_LAT, HOME_LNG, optional PLACES_TZ.
"""

import math
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from mcp.server.fastmcp import FastMCP

API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]
HOME = (float(os.environ["HOME_LAT"]), float(os.environ["HOME_LNG"]))
TZ = ZoneInfo(os.environ.get("PLACES_TZ", "Europe/London"))
TIMEOUT = httpx.Timeout(6.0)
CACHE_TTL = 600
SEARCH_RADIUS_M = 8000.0

# Enterprise tier (hours, phone); no Atmosphere fields such as reviews.
PLACE_FIELDS = ",".join(
    f"places.{f}"
    for f in (
        "displayName",
        "formattedAddress",
        "location",
        "businessStatus",
        "nationalPhoneNumber",
        "currentOpeningHours.openNow",
        "currentOpeningHours.nextOpenTime",
        "currentOpeningHours.nextCloseTime",
        "currentOpeningHours.weekdayDescriptions",
    )
)
ROUTE_FIELDS = "routes.duration,routes.distanceMeters"
TRAVEL_MODES = {
    "driving": "DRIVE",
    "walking": "WALK",
    "cycling": "BICYCLE",
    "transit": "TRANSIT",
}

mcp = FastMCP("places")
_cache: dict[tuple, tuple[float, str]] = {}


def _cached(key: tuple) -> str | None:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    return None


def _store(key: tuple, value: str) -> str:
    _cache[key] = (time.monotonic(), value)
    return value


def _api_error(resp: httpx.Response) -> str:
    if resp.status_code == 429:
        return "Google Maps daily limit has been reached, try again tomorrow."
    return f"Google Maps request failed (HTTP {resp.status_code})."


def _miles_from_home(loc: dict) -> float:
    lat1, lng1 = map(math.radians, HOME)
    lat2, lng2 = math.radians(loc["latitude"]), math.radians(loc["longitude"])
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def _local(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ)


def _when(dt: datetime, now: datetime) -> str:
    clock = dt.strftime("%H:%M")
    days = (dt.date() - now.date()).days
    if days == 1 and clock == "00:00":
        return "at midnight tonight"
    if days == 0:
        return f"today at {clock}"
    if days == 1:
        return f"tomorrow at {clock}"
    return f"{dt.strftime('%A')} at {clock}"


def _describe(place: dict, now: datetime) -> str:
    name = place.get("displayName", {}).get("text", "Unknown place")
    parts = [f"{name}, {place.get('formattedAddress', 'address unknown')}"]
    if loc := place.get("location"):
        parts.append(f"{_miles_from_home(loc):.1f} miles from home")

    status = place.get("businessStatus")
    hours = place.get("currentOpeningHours")
    if status == "CLOSED_PERMANENTLY":
        parts.append("permanently closed")
    elif status == "CLOSED_TEMPORARILY":
        parts.append("temporarily closed")
    elif not hours:
        parts.append("no opening hours listed")
    else:
        if hours.get("openNow"):
            state = "open now"
            if close := hours.get("nextCloseTime"):
                state += f", closes {_when(_local(close), now)}"
        else:
            state = "closed now"
            if opens := hours.get("nextOpenTime"):
                state += f", opens {_when(_local(opens), now)}"
        parts.append(state)
        today = now.strftime("%A")
        for line in hours.get("weekdayDescriptions", []):
            if line.startswith(today):
                parts.append(f"today's hours {line.split(': ', 1)[-1]}")
                break

    if phone := place.get("nationalPhoneNumber"):
        parts.append(f"phone {phone}")
    return "; ".join(parts) + "."


@mcp.tool()
async def find_place(query: str, open_now_only: bool = False) -> str:
    """Find shops, supermarkets, restaurants, pubs, pharmacies and other places,
    and get whether they are open now, when they open or close, today's hours,
    address, distance from home and phone number. Results are biased towards
    home, so for "near me" just describe the place (e.g. "big Tesco", "pharmacy").
    Include an area name in the query for places elsewhere (e.g. "Sainsbury's Balham").
    Set open_now_only to true to only return places that are open right now."""
    query = query.strip()
    key = ("find", query.lower(), open_now_only)
    if cached := _cached(key):
        return cached

    body = {
        "textQuery": query,
        "pageSize": 3,
        "languageCode": "en-GB",
        "regionCode": "GB",
        "locationBias": {
            "circle": {
                "center": {"latitude": HOME[0], "longitude": HOME[1]},
                "radius": SEARCH_RADIUS_M,
            }
        },
    }
    if open_now_only:
        body["openNow"] = True

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://places.googleapis.com/v1/places:searchText",
            json=body,
            headers={"X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": PLACE_FIELDS},
        )
    if resp.status_code != 200:
        return _api_error(resp)

    places = resp.json().get("places", [])
    if not places:
        return _store(key, f"Google Maps found nothing for '{query}'.")
    now = datetime.now(TZ)
    lines = [f"Source: Google Maps. Current time {now.strftime('%A %H:%M')}."]
    lines += [f"{i}. {_describe(p, now)}" for i, p in enumerate(places, 1)]
    return _store(key, "\n".join(lines))


@mcp.tool()
async def travel_time(destination: str, mode: str = "driving", origin: str = "") -> str:
    """Get how long it takes to travel somewhere and how far it is, starting from
    home unless an origin is given. mode is one of: driving, walking, cycling, transit.
    Driving times include current traffic."""
    travel_mode = TRAVEL_MODES.get(mode.strip().lower())
    if not travel_mode:
        return f"Unknown mode '{mode}'. Use driving, walking, cycling or transit."
    key = ("route", destination.strip().lower(), travel_mode, origin.strip().lower())
    if cached := _cached(key):
        return cached

    start = (
        {"address": origin}
        if origin.strip()
        else {"location": {"latLng": {"latitude": HOME[0], "longitude": HOME[1]}}}
    )
    body = {
        "origin": start,
        "destination": {"address": destination},
        "travelMode": travel_mode,
        "languageCode": "en-GB",
        "regionCode": "GB",
        "units": "IMPERIAL",
    }
    if travel_mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            json=body,
            headers={"X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": ROUTE_FIELDS},
        )
    if resp.status_code != 200:
        return _api_error(resp)

    routes = resp.json().get("routes", [])
    if not routes:
        return _store(key, f"Google Maps found no {mode} route to '{destination}'.")
    route = routes[0]
    minutes = round(int(route["duration"].rstrip("s")) / 60)
    miles = route.get("distanceMeters", 0) / 1609.344
    start_name = origin.strip() or "home"
    return _store(
        key,
        f"Source: Google Maps. {mode.capitalize()} from {start_name} to {destination}: "
        f"about {minutes} minutes, {miles:.1f} miles.",
    )


if __name__ == "__main__":
    mcp.run()

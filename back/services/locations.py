from __future__ import annotations

import re
from typing import Any

from clients.kiwi import get_kiwi_client


async def resolve_location(user_input: str) -> str:
    if not user_input:
        return ""
    cleaned = user_input.strip()
    if re.match(r"^[A-Z]{3}$", cleaned):
        return cleaned
    if re.match(r"^[A-Z]{2}$", cleaned):
        return cleaned
    client = get_kiwi_client()
    locations = await client.locations_query(cleaned, limit=1)
    if locations:
        loc = locations[0]
        return loc.get("code") or loc.get("id", cleaned)
    return cleaned


async def resolve_location_full(user_input: str) -> dict[str, Any]:
    if not user_input:
        return {}
    cleaned = user_input.strip()
    client = get_kiwi_client()
    if re.match(r"^[A-Z]{3}$", cleaned):
        locations = await client.locations_query(cleaned, limit=1)
        if locations:
            return locations[0]
        return {"code": cleaned, "id": cleaned}
    if re.match(r"^[A-Z]{2}$", cleaned):
        return {"code": cleaned, "id": cleaned, "type": "country"}
    locations = await client.locations_query(cleaned, limit=1)
    if locations:
        return locations[0]
    return {"code": cleaned, "id": cleaned}


async def get_nearby_airports(code: str, radius_km: int = 250) -> list[dict]:
    client = get_kiwi_client()
    locations = await client.locations_query(code, limit=1)
    if not locations:
        return []
    loc = locations[0]
    lat = loc.get("location", {}).get("lat")
    lon = loc.get("location", {}).get("lon")
    if lat is None or lon is None:
        return []
    airports = await client.locations_radius(lat, lon, radius_km, location_types="airport")
    return airports


async def search_locations(query: str, limit: int = 10) -> list[dict]:
    client = get_kiwi_client()
    locations = await client.locations_query(query, limit=limit)
    results = []
    for loc in locations:
        results.append({
            "id": loc.get("id", ""),
            "name": loc.get("name", ""),
            "code": loc.get("code", ""),
            "city": loc.get("city", {}).get("name", "") if isinstance(loc.get("city"), dict) else loc.get("name", ""),
            "country": loc.get("country", {}).get("name", "") if isinstance(loc.get("country"), dict) else "",
            "country_code": loc.get("country", {}).get("code", "") if isinstance(loc.get("country"), dict) else "",
            "type": loc.get("type", ""),
            "lat": loc.get("location", {}).get("lat", 0),
            "lon": loc.get("location", {}).get("lon", 0),
        })
    return results

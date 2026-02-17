from __future__ import annotations

import asyncio
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy


class NearbyAirportStrategy(BaseStrategy):
    name = "nearby_airport"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()

        # Find nearby airports to origin and destination
        nearby_origin_task = get_nearby_airports(params["fly_from"], radius_km=250)
        nearby_dest_task = get_nearby_airports(params["fly_to"], radius_km=250)
        nearby_origin, nearby_dest = await asyncio.gather(nearby_origin_task, nearby_dest_task)

        origin_codes = list(dict.fromkeys(
            [params["fly_from"]] +
            [a.get("code", "") for a in nearby_origin if a.get("code")]
        ))[:6]
        dest_codes = list(dict.fromkeys(
            [params["fly_to"]] +
            [a.get("code", "") for a in nearby_dest if a.get("code")]
        ))[:6]

        # Search from each origin to each dest (use comma-separated for efficiency)
        fly_from_str = ",".join(origin_codes)
        fly_to_str = ",".join(dest_codes)

        search_params: dict[str, Any] = {
            "fly_from": fly_from_str,
            "fly_to": fly_to_str,
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 500,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        if params.get("flight_type") != "oneway":
            if params.get("return_from"):
                search_params["return_from"] = params["return_from"]
            if params.get("return_to"):
                search_params["return_to"] = params["return_to"]
            if params.get("nights_in_dst_from") is not None:
                search_params["nights_in_dst_from"] = params["nights_in_dst_from"]
                search_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        data = await client.search(search_params)

        results: list[FlightResult] = []
        for item in data.get("data", []):
            fly_from = item.get("flyFrom", "")
            fly_to = item.get("flyTo", "")
            is_alt = fly_from != params["fly_from"] or fly_to != params["fly_to"]
            flight = self.parse_flight(item, strategy="nearby_airport")
            if is_alt:
                flight.strategy_explanation = (
                    f"From {fly_from} to {fly_to} — "
                    f"alternative airports near your route. €{item.get('price', 0)}"
                )
            else:
                flight.strategy_explanation = (
                    f"Direct: {fly_from}→{fly_to} — €{item.get('price', 0)}"
                )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:30]

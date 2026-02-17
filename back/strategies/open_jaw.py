from __future__ import annotations

import asyncio
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy


class OpenJawStrategy(BaseStrategy):
    name = "open_jaw"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []
        if params.get("flight_type") == "oneway":
            return []

        client = get_kiwi_client()

        # Get standard round-trip price
        std_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 1,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        if params.get("return_from"):
            std_params["return_from"] = params["return_from"]
        if params.get("return_to"):
            std_params["return_to"] = params["return_to"]
        if params.get("nights_in_dst_from") is not None:
            std_params["nights_in_dst_from"] = params["nights_in_dst_from"]
            std_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        std_data = await client.search(std_params)
        std_results = std_data.get("data", [])
        if not std_results:
            return []
        std_price = std_results[0].get("price", 0)
        if std_price == 0:
            return []

        # Find nearby airports to destination
        nearby = await get_nearby_airports(params["fly_to"], radius_km=250)
        nearby_codes = [
            a.get("code", "") for a in nearby
            if a.get("code") and a.get("code") != params["fly_to"]
        ][:8]

        if not nearby_codes:
            return []

        # Build return date
        return_from = params.get("return_from", params["date_from"])
        return_to = params.get("return_to", params["date_to"])

        # Search multi-city for each nearby airport
        tasks = []
        for alt_code in nearby_codes:
            body: dict[str, Any] = {
                "requests": [
                    {
                        "fly_from": params["fly_from"],
                        "fly_to": params["fly_to"],
                        "date_from": params["date_from"],
                        "date_to": params["date_to"],
                        "adults": params.get("adults", 1),
                        "selected_cabins": params.get("selected_cabins", "M"),
                    },
                    {
                        "fly_from": alt_code,
                        "fly_to": params["fly_from"],
                        "date_from": return_from,
                        "date_to": return_to,
                        "adults": params.get("adults", 1),
                        "selected_cabins": params.get("selected_cabins", "M"),
                    },
                ],
                "curr": "EUR",
                "limit": 100,
            }
            tasks.append(client.search_multi(body))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[FlightResult] = []
        for i, res in enumerate(all_results):
            if isinstance(res, Exception) or not res:
                continue
            alt_code = nearby_codes[i]
            for item in res:
                price = item.get("price", 0)
                if price >= std_price:
                    continue
                flight = self.parse_flight(item, strategy="open_jaw")
                savings = round((1 - price / std_price) * 100, 1)
                flight.savings_pct = savings
                flight.savings_vs = std_price
                flight.strategy_explanation = (
                    f"Fly {params['fly_from']}→{params['fly_to']}, "
                    f"return from {alt_code}→{params['fly_from']}. "
                    f"Save {savings}% vs standard round-trip (€{std_price})"
                )
                results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:15]

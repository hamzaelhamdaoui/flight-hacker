from __future__ import annotations

from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


class ThrowawayStrategy(BaseStrategy):
    name = "throwaway"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if params.get("flight_type") != "oneway":
            return []
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()

        # Get one-way price
        oneway_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 5,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        oneway_data = await client.search(oneway_params)
        oneway_results = oneway_data.get("data", [])
        if not oneway_results:
            return []
        oneway_price = oneway_results[0].get("price", 0)
        if oneway_price == 0:
            return []

        # Search round-trip (throw away the return)
        rt_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "nights_in_dst_from": 1,
            "nights_in_dst_to": 14,
            "curr": "EUR",
            "sort": "price",
            "limit": 20,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        rt_data = await client.search(rt_params)

        results: list[FlightResult] = []
        for item in rt_data.get("data", []):
            price = item.get("price", 0)
            if price >= oneway_price:
                continue
            flight = self.parse_flight(item, strategy="throwaway")
            savings = round((1 - price / oneway_price) * 100, 1)
            flight.savings_pct = savings
            flight.savings_vs = oneway_price
            flight.strategy_explanation = (
                f"Book round-trip for €{price} instead of one-way for €{oneway_price}. "
                f"Skip the return flight. Save {savings}%"
            )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:10]

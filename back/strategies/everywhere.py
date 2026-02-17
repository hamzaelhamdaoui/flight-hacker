from __future__ import annotations

from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


class EverywhereStrategy(BaseStrategy):
    name = "everywhere"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        client = get_kiwi_client()
        search_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": params.get("limit", 100),
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
            "one_for_city": 1,
        }
        if params.get("max_price"):
            search_params["price_to"] = params["max_price"]
        if params.get("flight_type") == "oneway" or not params.get("fly_to"):
            pass  # one_for_city only works on one-way
        else:
            search_params.pop("one_for_city", None)

        if params.get("nights_in_dst_from") is not None:
            search_params["nights_in_dst_from"] = params["nights_in_dst_from"]
            search_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        data = await client.search(search_params)
        results = []
        # For round-trip (where one_for_city can't be used), manually
        # deduplicate by cityCodeTo — keep only cheapest per city.
        is_round = "one_for_city" not in search_params
        seen_cities: dict[str, int] = {}  # cityCode → cheapest price

        for item in data.get("data", []):
            city_code = item.get("cityCodeTo", "")
            price = item.get("price", 0)
            if is_round and city_code:
                if city_code in seen_cities:
                    if price >= seen_cities[city_code]:
                        continue
                seen_cities[city_code] = price

            flight = self.parse_flight(item, strategy="everywhere")
            flight.strategy_explanation = (
                f"Cheapest flight to {item.get('cityTo', 'unknown')} "
                f"({item.get('countryTo', {}).get('name', '')}) — €{item.get('price', 0)}"
            )
            results.append(flight)

        if is_round:
            # Remove duplicates — keep only the cheapest per city
            best: dict[str, FlightResult] = {}
            for flight in results:
                key = flight.city_code_to or flight.city_to
                if key not in best or flight.price < best[key].price:
                    best[key] = flight
            results = list(best.values())
            results.sort(key=lambda r: r.price)

        return results

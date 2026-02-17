from __future__ import annotations

from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


class HiddenCityStrategy(BaseStrategy):
    name = "hidden_city"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        destination = params["fly_to"]

        # Step 1: Get direct price for baseline
        direct_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": destination,
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 1,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        if params.get("flight_type") != "oneway":
            if params.get("return_from"):
                direct_params["return_from"] = params["return_from"]
            if params.get("return_to"):
                direct_params["return_to"] = params["return_to"]
            if params.get("nights_in_dst_from") is not None:
                direct_params["nights_in_dst_from"] = params["nights_in_dst_from"]
                direct_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        direct_data = await client.search(direct_params)
        direct_results = direct_data.get("data", [])
        if not direct_results:
            return []
        direct_price = direct_results[0].get("price", 0)
        if direct_price == 0:
            return []

        # Step 2: Search origin → everywhere with stopovers, one-way
        # The everywhere search with limit=200 is sufficient — no need for
        # separate top_destinations searches which waste rate-limited API calls.
        everywhere_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 200,
            "max_stopovers": 2,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        try:
            everywhere_data = await client.search(everywhere_params)
        except Exception:
            return []

        items = everywhere_data.get("data", []) if isinstance(everywhere_data, dict) else []

        results: list[FlightResult] = []
        seen_ids: set[str] = set()
        dest_upper = destination.upper()

        for item in items:
            if item.get("id") in seen_ids:
                continue
            price = item.get("price", 0)
            if price >= direct_price:
                continue
            # Check if any intermediate segment stops at our destination
            route = item.get("route", [])
            has_dest_stop = False
            for seg in route:
                if (seg.get("cityCodeTo", "").upper() == dest_upper
                        or seg.get("flyTo", "").upper() == dest_upper
                        or seg.get("cityCodeFrom", "").upper() == dest_upper
                        or seg.get("flyFrom", "").upper() == dest_upper):
                    has_dest_stop = True
                    break
            if not has_dest_stop:
                continue
            seen_ids.add(item["id"])
            flight = self.parse_flight(item, strategy="hidden_city")
            savings = round((1 - price / direct_price) * 100, 1)
            flight.savings_pct = savings
            flight.savings_vs = direct_price
            flight.strategy_explanation = (
                f"Book through to {item.get('cityTo', 'final destination')} "
                f"but get off at {destination}. Save {savings}% vs direct (€{direct_price})"
            )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:20]

from __future__ import annotations

import asyncio
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


class MixedCarrierStrategy(BaseStrategy):
    name = "mixed_carrier"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        base: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 50,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        if params.get("flight_type") != "oneway":
            if params.get("return_from"):
                base["return_from"] = params["return_from"]
            if params.get("return_to"):
                base["return_to"] = params["return_to"]
            if params.get("nights_in_dst_from") is not None:
                base["nights_in_dst_from"] = params["nights_in_dst_from"]
                base["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        # Search with VI enabled
        vi_params = {**base, "enable_vi": "true"}
        # Search with VI disabled for comparison
        no_vi_params = {**base, "enable_vi": "false"}

        vi_data, no_vi_data = await asyncio.gather(
            client.search(vi_params),
            client.search(no_vi_params),
            return_exceptions=True,
        )

        if isinstance(vi_data, Exception):
            return []

        no_vi_price = 0
        if not isinstance(no_vi_data, Exception):
            no_vi_items = no_vi_data.get("data", [])
            if no_vi_items:
                no_vi_price = no_vi_items[0].get("price", 0)

        results: list[FlightResult] = []
        for item in vi_data.get("data", []):
            if not item.get("virtual_interlining"):
                continue
            price = item.get("price", 0)
            flight = self.parse_flight(item, strategy="mixed_carrier")
            if no_vi_price and price < no_vi_price:
                savings = round((1 - price / no_vi_price) * 100, 1)
                flight.savings_pct = savings
                flight.savings_vs = no_vi_price
                flight.strategy_explanation = (
                    f"Virtual interlining combines carriers that don't normally sell together. "
                    f"€{price} vs €{no_vi_price} non-VI. Save {savings}%"
                )
            else:
                flight.strategy_explanation = (
                    "Virtual interlining — mixed carriers combined by Kiwi for a better price."
                )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:20]

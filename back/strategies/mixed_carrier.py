from __future__ import annotations

import logging
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class MixedCarrierStrategy(BaseStrategy):
    name = "mixed_carrier"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        search_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 500,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
            "enable_vi": "true",
        }

        if params.get("flight_type") != "oneway":
            if params.get("return_from"):
                search_params["return_from"] = params["return_from"]
            if params.get("return_to"):
                search_params["return_to"] = params["return_to"]
            if params.get("nights_in_dst_from") is not None:
                search_params["nights_in_dst_from"] = params["nights_in_dst_from"]
                search_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        if params.get("max_price") is not None:
            search_params["price_to"] = params["max_price"]

        logger.info(f"[mixed_carrier] search_params: {search_params}")
        data = await client.search(search_params)

        total_raw = len(data.get("data", []))
        vi_count = sum(1 for item in data.get("data", []) if item.get("virtual_interlining"))
        logger.info(f"[mixed_carrier] raw results: {total_raw}, with VI: {vi_count}")

        results: list[FlightResult] = []
        for item in data.get("data", []):
            flight = self.parse_flight(item, strategy="mixed_carrier")
            if item.get("virtual_interlining"):
                flight.strategy_explanation = (
                    "Virtual interlining — mixed carriers combined by Kiwi for a better price."
                )
            else:
                flight.strategy_explanation = (
                    "Found via mixed carrier search with virtual interlining enabled."
                )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:30]

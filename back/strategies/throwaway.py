from __future__ import annotations

import asyncio
import logging
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger("throwaway")


class ThrowawayStrategy(BaseStrategy):
    name = "throwaway"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        """Throwaway ticketing: buy a round-trip and skip the return leg.
        
        Only useful for one-way searches where RT < OW.
        For round-trip explore, this strategy is skipped.
        """
        if not params.get("fly_to"):
            return []

        # Only makes sense for one-way
        if params.get("flight_type") == "round":
            return []

        client = get_kiwi_client()
        origin = params["fly_from"]
        destination = params["fly_to"]
        budget = params.get("max_price")

        # Step 1: Get cheapest one-way price as baseline
        ow_params: dict[str, Any] = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 5,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        if budget:
            ow_params["price_to"] = budget

        ow_data = await client.search(ow_params)
        ow_items = ow_data.get("data", [])
        if not ow_items:
            return []
        ow_price = ow_items[0].get("price", 0)
        if ow_price == 0:
            return []

        logger.info(f"Throwaway {origin}→{destination}: OW baseline €{ow_price}")

        # Step 2: Search round-trips with short stays (1-5 nights)
        # If RT < OW, user books RT and skips the return
        rt_params: dict[str, Any] = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "nights_in_dst_from": "1",
            "nights_in_dst_to": "7",
            "curr": "EUR",
            "sort": "price",
            "limit": 20,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }
        # RT must be cheaper than OW to be useful
        rt_params["price_to"] = ow_price - 1

        rt_data = await client.search(rt_params)
        rt_items = rt_data.get("data", [])

        results: list[FlightResult] = []
        for item in rt_items:
            price = item.get("price", 0)
            if price >= ow_price:
                continue
            if budget and price > budget:
                continue

            flight = self.parse_flight(item, strategy="throwaway")
            savings = round((1 - price / ow_price) * 100, 1)
            flight.savings_pct = savings
            flight.savings_vs = ow_price
            flight.strategy_explanation = (
                f"Book round-trip €{price} instead of one-way €{ow_price} — "
                f"skip the return leg. Save {savings}% (€{ow_price - price})"
            )
            results.append(flight)

        results.sort(key=lambda r: r.price)
        logger.info(f"Throwaway {origin}→{destination}: {len(results)} results cheaper than OW €{ow_price}")
        return results[:10]

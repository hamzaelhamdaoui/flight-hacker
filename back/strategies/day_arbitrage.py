from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _analyze_day_prices(items: list[dict]) -> tuple[dict[int, float], int | None]:
    """Group prices by day-of-week, return averages and cheapest day index."""
    day_prices: dict[int, list[int]] = defaultdict(list)
    for item in items:
        dep = item.get("local_departure", "")
        if dep:
            try:
                dt = datetime.fromisoformat(dep.replace("Z", "+00:00"))
                dow = dt.weekday()
                day_prices[dow].append(item.get("price", 0))
            except (ValueError, TypeError):
                pass
    if not day_prices:
        return {}, None
    day_avgs: dict[int, float] = {}
    for dow, prices in day_prices.items():
        day_avgs[dow] = sum(prices) / len(prices) if prices else 0
    cheapest = min(day_avgs, key=lambda d: day_avgs[d])
    return day_avgs, cheapest


class DayArbitrageStrategy(BaseStrategy):
    name = "day_arbitrage"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        is_round = params.get("flight_type") != "oneway"

        # Search outbound one-way with one_per_date to get price per departure day
        outbound_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 200,
            "one_per_date": 1,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        tasks = [client.search(outbound_params)]

        # If round trip, also search inbound
        if is_round:
            return_from = params.get("return_from", params["date_from"])
            return_to = params.get("return_to", params["date_to"])
            inbound_params: dict[str, Any] = {
                "fly_from": params["fly_to"],
                "fly_to": params["fly_from"],
                "date_from": return_from,
                "date_to": return_to,
                "curr": "EUR",
                "sort": "price",
                "limit": 200,
                "one_per_date": 1,
                "adults": params.get("adults", 1),
                "selected_cabins": params.get("selected_cabins", "M"),
            }
            tasks.append(client.search(inbound_params))

        all_data = await asyncio.gather(*tasks, return_exceptions=True)

        outbound_data = all_data[0] if not isinstance(all_data[0], Exception) else {"data": []}
        outbound_items = outbound_data.get("data", [])

        out_avgs, cheapest_out = _analyze_day_prices(outbound_items)
        if cheapest_out is None:
            return []

        # Build explanation
        out_summary = ", ".join(
            f"{DAY_NAMES[d]} avg €{out_avgs[d]:.0f}"
            for d in sorted(out_avgs.keys())
        )

        # Analyze inbound if round-trip
        in_summary = ""
        cheapest_in = None
        if is_round and len(all_data) > 1:
            inbound_data = all_data[1] if not isinstance(all_data[1], Exception) else {"data": []}
            inbound_items = inbound_data.get("data", [])
            in_avgs, cheapest_in = _analyze_day_prices(inbound_items)
            if in_avgs:
                in_summary = ". Return: " + ", ".join(
                    f"{DAY_NAMES[d]} avg €{in_avgs[d]:.0f}"
                    for d in sorted(in_avgs.keys())
                )

        # Build combined explanation
        explanation_base = f"Cheapest outbound day: {DAY_NAMES[cheapest_out]}. Outbound: {out_summary}"
        if cheapest_in is not None:
            explanation_base += f". Cheapest return day: {DAY_NAMES[cheapest_in]}{in_summary}"

        # Return actual flights from the cheapest outbound day(s)
        results: list[FlightResult] = []
        for item in outbound_items:
            dep = item.get("local_departure", "")
            if dep:
                try:
                    dt = datetime.fromisoformat(dep.replace("Z", "+00:00"))
                    if dt.weekday() == cheapest_out:
                        flight = self.parse_flight(item, strategy="day_arbitrage")
                        flight.strategy_explanation = explanation_base
                        results.append(flight)
                except (ValueError, TypeError):
                    pass

        results.sort(key=lambda r: r.price)
        return results[:20]

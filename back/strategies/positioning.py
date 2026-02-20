from __future__ import annotations

import asyncio
import logging
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger("positioning")

# Alternate airports reachable by train/bus/car from major Spanish origins
POSITIONING_MAP: dict[str, list[str]] = {
    "MAD": ["BCN", "LIS", "AGP", "SVQ", "VLC", "BIO", "OPO", "PMI"],
    "BCN": ["MAD", "LIS", "AGP", "VLC", "PMI", "GRO", "REU"],
    "AGP": ["MAD", "BCN", "SVQ", "GRX", "LIS"],
    "SVQ": ["MAD", "BCN", "AGP", "LIS", "FAO", "XRY"],
    "VLC": ["MAD", "BCN", "AGP", "ALC", "PMI"],
    "BIO": ["MAD", "BCN", "SDR", "VIT"],
    "LIS": ["MAD", "BCN", "OPO", "AGP", "FAO", "SVQ"],
    "OPO": ["MAD", "BCN", "LIS", "FAO"],
}

DEFAULT_POSITIONING = ["BCN", "MAD", "LIS", "AGP", "OPO", "SVQ"]


class PositioningStrategy(BaseStrategy):
    name = "positioning"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        origin = params["fly_from"].upper()
        destination = params["fly_to"]
        budget = params.get("max_price")
        nights_from = params.get("nights_in_dst_from", 6)
        nights_to = params.get("nights_in_dst_to", 17)

        alt_airports = POSITIONING_MAP.get(origin, DEFAULT_POSITIONING)
        alt_airports = [a for a in alt_airports if a.upper() != origin and a.upper() != destination.upper()]

        if not alt_airports:
            return []

        results: list[FlightResult] = []
        seen: set[str] = set()

        # Round-trip from each alt airport to destination
        for i in range(0, len(alt_airports), 3):
            batch = alt_airports[i:i + 3]
            coros = []
            for alt in batch:
                rt_params: dict[str, Any] = {
                    "fly_from": alt,
                    "fly_to": destination,
                    "date_from": params["date_from"],
                    "date_to": params["date_to"],
                    "curr": "EUR",
                    "sort": "price",
                    "limit": 10,
                    "adults": params.get("adults", 1),
                    "selected_cabins": params.get("selected_cabins", "M"),
                    "nights_in_dst_from": str(nights_from),
                    "nights_in_dst_to": str(nights_to),
                }
                if budget:
                    rt_params["price_to"] = budget
                coros.append(client.search(rt_params))

            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for j, alt in enumerate(batch):
                data = batch_results[j]
                if isinstance(data, Exception):
                    continue
                items = data.get("data", [])
                if not items:
                    continue

                for item in items[:5]:
                    price = item.get("price", 0)
                    if not price or (budget and price > budget):
                        continue

                    key = f"{alt}_{price}_{item.get('id', '')}"
                    if key in seen:
                        continue
                    seen.add(key)

                    flight = self.parse_flight(item, strategy="positioning")
                    flight.fly_from = alt
                    flight.city_code_from = alt
                    flight.strategy_explanation = (
                        f"✈️ Fly from {alt} instead of {origin}: €{price} round-trip"
                    )
                    results.append(flight)

                logger.info(f"Positioning {alt}→{destination}: cheapest €{items[0].get('price', '?')}")

            await asyncio.sleep(2)

        results.sort(key=lambda r: r.price)
        logger.info(f"Positioning total: {len(results)} results for {origin}→{destination}")
        return results[:30]

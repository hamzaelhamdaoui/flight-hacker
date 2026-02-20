from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy
from strategies.positioning import POSITIONING_MAP, DEFAULT_POSITIONING
from strategies.open_jaw import REGIONAL_CITIES, _get_continent

logger = logging.getLogger("double_open_jaw")

FMT = "%d/%m/%Y"


class DoubleOpenJawStrategy(BaseStrategy):
    name = "double_open_jaw"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        origin = params["fly_from"].upper()
        destination = params["fly_to"].upper()
        budget = params.get("max_price")
        nights_from = params.get("nights_in_dst_from", 6)
        nights_to = params.get("nights_in_dst_to", 17)

        try:
            d_from = datetime.strptime(params["date_from"], FMT)
            d_to = datetime.strptime(params["date_to"], FMT)
            ret_from = (d_from + timedelta(days=nights_from)).strftime(FMT)
            ret_to = (d_to + timedelta(days=nights_to)).strftime(FMT)
        except (ValueError, TypeError):
            return []

        # Return-to airports: nearby Spanish airports from positioning map
        return_to_airports = POSITIONING_MAP.get(origin, DEFAULT_POSITIONING)
        return_to_airports = [a for a in return_to_airports if a != origin][:5]

        # Return-from cities: nearby + same continent
        dest_continent = _get_continent(destination)
        try:
            nearby = await get_nearby_airports(params["fly_to"], radius_km=500)
            nearby_codes = [
                a.get("code", "").upper() for a in nearby
                if a.get("code") and a.get("code").upper() != destination
                and a.get("code").upper() != origin
            ][:10]
        except Exception:
            nearby_codes = []

        regional = []
        if dest_continent:
            regional = [
                c for c in REGIONAL_CITIES.get(dest_continent, [])
                if c != destination and c != origin
            ][:15]

        return_from_cities = list(dict.fromkeys(nearby_codes + regional))  # dedup preserving order

        if not return_from_cities or not return_to_airports:
            return []

        # Build all combinations: return_from × return_to
        combos = []
        for ret_from_city in return_from_cities:
            for ret_to_airport in return_to_airports:
                combos.append((ret_from_city, ret_to_airport))

        logger.info(
            f"Double open jaw {origin}→{destination}: "
            f"{len(return_from_cities)} return-from × {len(return_to_airports)} return-to = {len(combos)} combos"
        )

        results: list[FlightResult] = []
        seen: set[str] = set()

        # Search in batches of 3
        for i in range(0, len(combos), 3):
            batch = combos[i:i + 3]
            coros = []

            for ret_from_city, ret_to_airport in batch:
                body: dict[str, Any] = {
                    "requests": [
                        {
                            "fly_from": origin,
                            "fly_to": destination,
                            "date_from": params["date_from"],
                            "date_to": params["date_to"],
                            "adults": params.get("adults", 1),
                            "selected_cabins": params.get("selected_cabins", "M"),
                        },
                        {
                            "fly_from": ret_from_city,
                            "fly_to": ret_to_airport,
                            "date_from": ret_from,
                            "date_to": ret_to,
                            "adults": params.get("adults", 1),
                            "selected_cabins": params.get("selected_cabins", "M"),
                        },
                    ],
                    "curr": "EUR",
                    "limit": 5,
                    "sort": "price",
                }
                if budget:
                    body["price_to"] = budget
                coros.append(client.search_multi(body))

            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for j, (ret_from_city, ret_to_airport) in enumerate(batch):
                data = batch_results[j]
                if isinstance(data, Exception):
                    continue

                items = data if isinstance(data, list) else []
                if not items:
                    continue

                for item in items[:3]:
                    price = item.get("price", 0)
                    if not price or (budget and price > budget):
                        continue

                    key = f"{ret_from_city}_{ret_to_airport}_{price}_{item.get('id', '')}"
                    if key in seen:
                        continue
                    seen.add(key)

                    route = item.get("route", [])
                    dep_date = route[0].get("local_departure", "")[:10] if route else "?"
                    ret_date = route[-1].get("local_arrival", "")[:10] if route else "?"

                    nights = 0
                    if len(route) >= 2:
                        try:
                            leg1_arr = route[0].get("local_arrival", "")[:10]
                            leg2_dep = route[-1].get("local_departure", "")[:10]
                            if leg1_arr and leg2_dep:
                                nights = (datetime.fromisoformat(leg2_dep) - datetime.fromisoformat(leg1_arr)).days
                        except (ValueError, TypeError):
                            pass

                    flight = self.parse_flight(item, strategy="double_open_jaw")
                    flight.price = price
                    flight.nights_in_dest = nights
                    flight.city_code_to = destination
                    flight.strategy_explanation = (
                        f"Double open jaw: {origin}→{destination}, "
                        f"return {ret_from_city}→{ret_to_airport} "
                        f"€{price} ({dep_date}→{ret_date}, ~{nights}n)"
                    )
                    results.append(flight)

            await asyncio.sleep(2)

        results.sort(key=lambda r: r.price)
        logger.info(f"Double open jaw total: {len(results)} results for {origin}→{destination}")
        return results[:30]

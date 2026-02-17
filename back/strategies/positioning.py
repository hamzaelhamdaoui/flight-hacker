from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy

MIN_CONNECTION_HOURS = 2
MAX_CONNECTION_HOURS = 8


def _parse_local_time(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class PositioningStrategy(BaseStrategy):
    name = "positioning"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()

        # Get direct price
        direct_params: dict[str, Any] = {
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

        # Find nearby airports to origin (400km for positioning)
        nearby = await get_nearby_airports(params["fly_from"], radius_km=400)
        alt_origins = [
            a.get("code", "") for a in nearby
            if a.get("code") and a.get("code") != params["fly_from"]
        ][:8]

        if not alt_origins:
            return []

        # Build all coroutines first, then gather them all at once
        pos_coros = []
        main_coros = []
        alt_codes = []

        for alt_code in alt_origins:
            # Positioning: origin → alt (one-way)
            pos_params: dict[str, Any] = {
                "fly_from": params["fly_from"],
                "fly_to": alt_code,
                "date_from": params["date_from"],
                "date_to": params["date_to"],
                "curr": "EUR",
                "sort": "price",
                "limit": 50,
                "adults": params.get("adults", 1),
            }
            # Main flight: alt → dest
            main_params: dict[str, Any] = {
                "fly_from": alt_code,
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
                    main_params["return_from"] = params["return_from"]
                if params.get("return_to"):
                    main_params["return_to"] = params["return_to"]
                if params.get("nights_in_dst_from") is not None:
                    main_params["nights_in_dst_from"] = params["nights_in_dst_from"]
                    main_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

            alt_codes.append(alt_code)
            pos_coros.append(client.search(pos_params))
            main_coros.append(client.search(main_params))

        # Gather ALL at once
        all_coros = pos_coros + main_coros
        all_results = await asyncio.gather(*all_coros, return_exceptions=True)

        n = len(alt_codes)
        pos_results = all_results[:n]
        main_results = all_results[n:]

        results: list[FlightResult] = []

        for i, alt_code in enumerate(alt_codes):
            pos_data = pos_results[i]
            main_data = main_results[i]
            if isinstance(pos_data, Exception) or isinstance(main_data, Exception):
                continue

            pos_items = pos_data.get("data", [])
            main_items = main_data.get("data", [])
            if not pos_items or not main_items:
                continue

            # Find time-valid combinations: positioning arrives → main departs (2-8h gap)
            for pos_flight in pos_items:
                pos_arrival = _parse_local_time(pos_flight.get("local_arrival", ""))
                if not pos_arrival:
                    continue
                for main_flight in main_items:
                    main_departure = _parse_local_time(main_flight.get("local_departure", ""))
                    if not main_departure:
                        continue
                    gap = (main_departure - pos_arrival).total_seconds() / 3600
                    if not (MIN_CONNECTION_HOURS <= gap <= MAX_CONNECTION_HOURS):
                        continue

                    pos_price = pos_flight.get("price", 0)
                    main_price = main_flight.get("price", 0)
                    combined = pos_price + main_price

                    if combined >= direct_price - 30:
                        continue

                    pos_airlines = pos_flight.get("airlines", [])
                    pos_airline = pos_airlines[0] if pos_airlines else ""
                    pos_route = pos_flight.get("route", [])
                    pos_fn = ""
                    if pos_route:
                        fn = pos_route[0].get("flight_no", "")
                        if fn:
                            pos_fn = f" {pos_airline}{fn}"

                    flight = self.parse_flight(main_flight, strategy="positioning")
                    flight.price = combined
                    savings = round((1 - combined / direct_price) * 100, 1)
                    flight.savings_pct = savings
                    flight.savings_vs = direct_price
                    flight.strategy_explanation = (
                        f"Position to {alt_code}: "
                        f"{params['fly_from']}→{alt_code} ({pos_airline}{pos_fn}, "
                        f"arrives {pos_flight.get('local_arrival', '')[:16]}, €{pos_price}) | "
                        f"Main: {alt_code}→{params['fly_to']} "
                        f"(departs {main_flight.get('local_departure', '')[:16]}, €{main_price}). "
                        f"Total €{combined} vs direct €{direct_price}. Save {savings}%"
                    )
                    results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:10]

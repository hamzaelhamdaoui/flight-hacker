from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger("split_ticket")

FALLBACK_HUBS = ["IST", "DXB", "FRA", "AMS", "LHR"]

MIN_CONNECTION_HOURS = 3
MAX_CONNECTION_HOURS = 12


def _parse_local_time(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _find_valid_combos(
    leg1_items: list[dict],
    leg2_items: list[dict],
    min_hours: float = MIN_CONNECTION_HOURS,
    max_hours: float = MAX_CONNECTION_HOURS,
) -> list[tuple[dict, dict]]:
    """Find leg1/leg2 combos where leg2 departs 3-12h after leg1 arrives."""
    combos = []
    for l1 in leg1_items:
        l1_arrival = _parse_local_time(l1.get("local_arrival", ""))
        if not l1_arrival:
            continue
        for l2 in leg2_items:
            l2_departure = _parse_local_time(l2.get("local_departure", ""))
            if not l2_departure:
                continue
            gap = (l2_departure - l1_arrival).total_seconds() / 3600
            if min_hours <= gap <= max_hours:
                combos.append((l1, l2))
    return combos


class SplitTicketStrategy(BaseStrategy):
    name = "split_ticket"

    async def _get_hubs(self, origin: str, destination: str) -> list[str]:
        """Get dynamic hubs from top destinations, merged with fallback mega-hubs."""
        client = get_kiwi_client()
        try:
            top_dests = await client.locations_topdestinations(origin, limit=15)
            dynamic_hubs = [
                d.get("code", "") for d in top_dests
                if d.get("code") and d.get("code") not in (origin, destination)
            ]
        except Exception:
            dynamic_hubs = []

        # Merge with fallback hubs, preserving order (dynamic first)
        seen: set[str] = set()
        hubs: list[str] = []
        for h in dynamic_hubs + FALLBACK_HUBS:
            if h and h not in seen and h not in (origin, destination):
                seen.add(h)
                hubs.append(h)
        return hubs[:12]

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

        # Get dynamic hubs
        hub_list = await self._get_hubs(params["fly_from"], params["fly_to"])
        if not hub_list:
            return []

        # Build all coroutines first, then gather them all at once
        hub_coros: list[tuple[str, Any, Any]] = []
        leg1_coros = []
        leg2_coros = []
        hub_names = []

        for hub in hub_list:
            leg1_params: dict[str, Any] = {
                "fly_from": params["fly_from"],
                "fly_to": hub,
                "date_from": params["date_from"],
                "date_to": params["date_to"],
                "curr": "EUR",
                "sort": "price",
                "limit": 5,
                "adults": params.get("adults", 1),
                "selected_cabins": params.get("selected_cabins", "M"),
            }
            leg2_params: dict[str, Any] = {
                "fly_from": hub,
                "fly_to": params["fly_to"],
                "date_from": params["date_from"],
                "date_to": params["date_to"],
                "curr": "EUR",
                "sort": "price",
                "limit": 5,
                "adults": params.get("adults", 1),
                "selected_cabins": params.get("selected_cabins", "M"),
            }
            hub_names.append(hub)
            leg1_coros.append(client.search(leg1_params))
            leg2_coros.append(client.search(leg2_params))

        # Gather ALL searches at once (truly parallel)
        all_coros = leg1_coros + leg2_coros
        all_results = await asyncio.gather(*all_coros, return_exceptions=True)

        n = len(hub_names)
        leg1_results = all_results[:n]
        leg2_results = all_results[n:]

        results: list[FlightResult] = []

        for i, hub in enumerate(hub_names):
            l1_data = leg1_results[i]
            l2_data = leg2_results[i]
            if isinstance(l1_data, Exception) or isinstance(l2_data, Exception):
                continue
            leg1_items = l1_data.get("data", [])
            leg2_items = l2_data.get("data", [])
            if not leg1_items or not leg2_items:
                continue

            # Find time-valid combinations
            valid_combos = _find_valid_combos(leg1_items, leg2_items)
            if not valid_combos:
                continue

            for l1, l2 in valid_combos:
                combined = l1.get("price", 0) + l2.get("price", 0)
                threshold = direct_price * 0.9  # Must be at least 10% cheaper
                if combined >= threshold:
                    continue

                l1_arrival = l1.get("local_arrival", "")
                l2_departure = l2.get("local_departure", "")
                l1_airline = l1.get("airlines", [""])[0] if l1.get("airlines") else ""
                l2_airline = l2.get("airlines", [""])[0] if l2.get("airlines") else ""

                flight = self.parse_flight(l1, strategy="split_ticket")
                flight.price = combined
                savings = round((1 - combined / direct_price) * 100, 1)
                flight.savings_pct = savings
                flight.savings_vs = direct_price
                flight.strategy_explanation = (
                    f"Split via {hub}: "
                    f"Leg 1: {params['fly_from']}→{hub} ({l1_airline}, "
                    f"arrives {l1_arrival[:16]}, €{l1.get('price', 0)}) | "
                    f"Leg 2: {hub}→{params['fly_to']} ({l2_airline}, "
                    f"departs {l2_departure[:16]}, €{l2.get('price', 0)}) = €{combined}. "
                    f"Direct is €{direct_price}. Save {savings}%"
                )
                results.append(flight)

        results.sort(key=lambda r: r.price)
        # TODO (v1.5): For round-trip, also split the return leg via the same hub
        # (dest→hub + hub→origin) and compare total split round-trip vs direct.
        return results[:10]

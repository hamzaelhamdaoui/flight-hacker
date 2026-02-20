from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger("split_ticket")

# Major connection hubs reachable cheaply from Spain
HUBS = ["IST", "DXB", "DOH", "FRA", "AMS", "LHR", "CDG", "MUC", "ZRH", "HEL", "WAW", "VIE"]

FMT = "%d/%m/%Y"


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


class SplitTicketStrategy(BaseStrategy):
    name = "split_ticket"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        origin = params["fly_from"]
        destination = params["fly_to"]
        budget = params.get("max_price")
        nights_from = params.get("nights_in_dst_from", 6)
        nights_to = params.get("nights_in_dst_to", 17)

        hubs = [h for h in HUBS if h.upper() not in (origin.upper(), destination.upper())]

        # Step 1: Search MAD↔hub round-trips (these define the travel window)
        # nights_in_dst = total trip length (time spent away from home, at/via hub)
        # Batch in groups of 3 to avoid 429s
        rt1_all = []
        rt1_hubs = []
        for i in range(0, len(hubs), 3):
            batch = hubs[i:i + 3]
            coros = []
            for hub in batch:
                rt1_params: dict[str, Any] = {
                    "fly_from": origin,
                    "fly_to": hub,
                    "date_from": params["date_from"],
                    "date_to": params["date_to"],
                    "curr": "EUR",
                    "sort": "price",
                    "limit": 5,
                    "adults": params.get("adults", 1),
                    "selected_cabins": params.get("selected_cabins", "M"),
                    "nights_in_dst_from": str(nights_from),
                    "nights_in_dst_to": str(nights_to),
                }
                if budget:
                    rt1_params["price_to"] = int(budget * 0.5)
                coros.append(client.search(rt1_params))
                rt1_hubs.append(hub)
            batch_results = await asyncio.gather(*coros, return_exceptions=True)
            rt1_all.extend(batch_results)
            await asyncio.sleep(2)

        # Step 2: For each hub with results, extract travel windows and search hub↔dest
        results: list[FlightResult] = []
        seen: set[str] = set()

        for idx, hub in enumerate(rt1_hubs):
            rt1_data = rt1_all[idx]
            if isinstance(rt1_data, Exception):
                continue
            rt1_items = rt1_data.get("data", [])
            if not rt1_items:
                continue

            # For each MAD↔hub itinerary, find the outbound arrival and return departure
            # to define the window for hub↔dest booking
            rt2_coros = []
            rt1_refs = []  # keep reference to which rt1 item each rt2 corresponds to

            for r1 in rt1_items[:3]:
                r1_price = r1.get("price", 0)
                if not r1_price:
                    continue
                if budget and r1_price > budget * 0.4:
                    continue

                route = r1.get("route", [])
                if not route:
                    continue

                # Find when we arrive at hub (last outbound segment arrival)
                outbound_segs = [s for s in route if s.get("return", 0) == 0]
                return_segs = [s for s in route if s.get("return", 0) == 1]

                if not outbound_segs or not return_segs:
                    continue

                arrive_hub = _parse_dt(outbound_segs[-1].get("local_arrival", ""))
                depart_hub_home = _parse_dt(return_segs[0].get("local_departure", ""))

                if not arrive_hub or not depart_hub_home:
                    continue

                # Hub↔dest booking window:
                # Depart hub: day after arriving (give 1 day buffer)
                # Return to hub: day before returning home
                hub_depart_earliest = (arrive_hub + timedelta(hours=12)).strftime(FMT)
                hub_return_latest = (depart_hub_home - timedelta(hours=12)).strftime(FMT)

                # Calculate available nights at destination
                available_days = (depart_hub_home - arrive_hub).days - 1
                if available_days < 3:
                    continue  # Not enough time for a meaningful trip

                dest_nights_min = max(3, available_days - 2)  # leave some buffer
                dest_nights_max = available_days

                rt2_params: dict[str, Any] = {
                    "fly_from": hub,
                    "fly_to": destination,
                    "date_from": hub_depart_earliest,
                    "date_to": hub_depart_earliest,  # Pin to first available day
                    "curr": "EUR",
                    "sort": "price",
                    "limit": 5,
                    "adults": params.get("adults", 1),
                    "selected_cabins": params.get("selected_cabins", "M"),
                    "nights_in_dst_from": str(dest_nights_min),
                    "nights_in_dst_to": str(dest_nights_max),
                }
                remaining = budget - r1_price if budget else None
                if remaining:
                    rt2_params["price_to"] = remaining

                rt2_coros.append(client.search(rt2_params))
                rt1_refs.append(r1)

            if not rt2_coros:
                continue

            # Run rt2 searches sequentially to avoid 429s
            rt2_all = []
            for coro in rt2_coros:
                try:
                    res = await coro
                    rt2_all.append(res)
                except Exception as e:
                    rt2_all.append(e)
                await asyncio.sleep(1)

            for j, rt2_data in enumerate(rt2_all):
                if isinstance(rt2_data, Exception):
                    continue
                rt2_items = rt2_data.get("data", [])
                if not rt2_items:
                    continue

                r1 = rt1_refs[j]
                r1_price = r1.get("price", 0)
                r1_link = r1.get("deep_link", "")

                for r2 in rt2_items[:3]:
                    r2_price = r2.get("price", 0)
                    if not r2_price:
                        continue

                    combined = r1_price + r2_price
                    if budget and combined > budget:
                        continue

                    key = f"{hub}_{r1_price}_{r2_price}_{r2.get('id','')}"
                    if key in seen:
                        continue
                    seen.add(key)

                    r2_link = r2.get("deep_link", "")

                    flight = self.parse_flight(r2, strategy="split_ticket")
                    flight.price = combined
                    flight.fly_from = origin
                    flight.city_from = r1.get("cityFrom", origin)
                    flight.city_code_from = r1.get("cityCodeFrom", origin)
                    flight.country_from = r1.get("countryFrom", {})

                    # Both deep links
                    flight.deep_link = f"{r1_link}|{r2_link}"

                    # Get actual dates for explanation
                    r1_dep = r1.get("local_departure", "")[:10]
                    r1_ret = ""
                    r1_return_segs = [s for s in r1.get("route", []) if s.get("return", 0) == 1]
                    if r1_return_segs:
                        r1_ret = r1_return_segs[-1].get("local_arrival", "")[:10]

                    r2_dep = r2.get("local_departure", "")[:10]
                    r2_ret = ""
                    r2_return_segs = [s for s in r2.get("route", []) if s.get("return", 0) == 1]
                    if r2_return_segs:
                        r2_ret = r2_return_segs[-1].get("local_arrival", "")[:10]

                    flight.strategy_explanation = (
                        f"2 bookings via {hub}: "
                        f"① {origin}↔{hub} €{r1_price} ({r1_dep}→{r1_ret}) + "
                        f"② {hub}↔{destination} €{r2_price} ({r2_dep}→{r2_ret}) = €{combined}"
                    )
                    results.append(flight)

            logger.info(f"Split via {hub}: {len(rt1_items)} windows, {sum(1 for r in rt2_all if not isinstance(r, Exception))} rt2 searches")
            await asyncio.sleep(1)

        results.sort(key=lambda r: r.price)
        logger.info(f"Split ticket total: {len(results)} valid combos for {origin}→{destination}")
        return results[:20]

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy

logger = logging.getLogger("open_jaw")

FMT = "%d/%m/%Y"

# Regional cities by continent — also used by double_open_jaw
REGIONAL_CITIES: dict[str, list[str]] = {
    "europe": [
        "ROM", "PAR", "LON", "BCN", "AMS", "BER", "PRG", "VIE", "BUD", "WAW",
        "ATH", "LIS", "DUB", "CPH", "OSL", "HEL", "IST", "MIL", "FRA", "MUC",
        "BRU", "ZUR", "GVA", "STO", "EDI", "MAD", "SVQ", "OPO", "NCE",
    ],
    "africa": [
        "CMN", "RAK", "TNG", "FEZ", "TUN", "CAI", "CPT", "JNB", "NBO", "DAR",
        "ADD", "LOS", "ACC", "DKR", "MRU",
    ],
    "asia": [
        "BKK", "SGN", "HAN", "TYO", "KIX", "ICN", "DEL", "BOM", "BLR",
        "DPS", "CGK", "KUL", "SIN", "MNL", "CMB", "TLV", "TBS", "EVN",
        "AMM", "DOH", "DXB", "AUH", "RUH", "JED", "HKT", "PNH", "DAD",
        "PEK", "PVG", "HKG", "TPE", "CEB", "GMP", "REP", "VTE",
    ],
    "americas": [
        "JFK", "LAX", "MIA", "CHI", "SFO", "BOS", "YYZ", "MEX", "CUN",
        "BOG", "LIM", "SCL", "EZE", "GRU", "RIO", "HAV", "SJO", "PTY",
    ],
    "oceania": [
        "SYD", "MEL", "BNE", "PER", "AKL", "WLG", "NAN",
    ],
}

_CITY_TO_CONTINENT: dict[str, str] = {}
for _cont, _cities in REGIONAL_CITIES.items():
    for _c in _cities:
        _CITY_TO_CONTINENT[_c] = _cont


def _get_continent(city_code: str) -> str:
    return _CITY_TO_CONTINENT.get(city_code.upper(), "")


class OpenJawStrategy(BaseStrategy):
    name = "open_jaw"

    async def _get_alt_return_cities(self, destination: str, origin: str) -> list[str]:
        """Get nearby airports within 500km of destination for open-jaw return."""
        dest_upper = destination.upper()
        origin_upper = origin.upper()

        try:
            nearby = await get_nearby_airports(destination, radius_km=500)
            codes = [
                a.get("code", "").upper() for a in nearby
                if a.get("code") and a.get("code").upper() != dest_upper
                and a.get("code").upper() != origin_upper
            ][:10]
        except Exception:
            codes = []

        logger.info(f"Open jaw alt cities for {destination}: {len(codes)} nearby airports")
        return codes

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()
        origin = params["fly_from"]
        destination = params["fly_to"]
        budget = params.get("max_price")
        nights_from = params.get("nights_in_dst_from", 6)
        nights_to = params.get("nights_in_dst_to", 17)

        # Calculate return date range
        try:
            d_from = datetime.strptime(params["date_from"], FMT)
            d_to = datetime.strptime(params["date_to"], FMT)
            ret_from = (d_from + timedelta(days=nights_from)).strftime(FMT)
            ret_to = (d_to + timedelta(days=nights_to)).strftime(FMT)
        except (ValueError, TypeError):
            return []

        alt_cities = await self._get_alt_return_cities(destination, origin)
        if not alt_cities:
            return []

        results: list[FlightResult] = []
        seen: set[str] = set()

        # Search open jaw: origin→destination + alt→origin via flights_multi
        for i in range(0, len(alt_cities), 3):
            batch = alt_cities[i:i + 3]
            coros = []

            for alt in batch:
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
                            "fly_from": alt,
                            "fly_to": origin,
                            "date_from": ret_from,
                            "date_to": ret_to,
                            "adults": params.get("adults", 1),
                            "selected_cabins": params.get("selected_cabins", "M"),
                        },
                    ],
                    "curr": "EUR",
                    "limit": 10,
                    "sort": "price",
                }
                if budget:
                    body["price_to"] = budget
                coros.append(client.search_multi(body))

            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for j, alt in enumerate(batch):
                data = batch_results[j]
                if isinstance(data, Exception):
                    logger.warning(f"Open jaw {origin}→{destination}, return {alt}→{origin}: {data}")
                    continue

                items = data if isinstance(data, list) else []
                if not items:
                    continue

                for item in items[:5]:
                    price = item.get("price", 0)
                    if not price or (budget and price > budget):
                        continue

                    item_id = item.get("id", "")
                    key = f"{alt}_{price}_{item_id}"
                    if key in seen:
                        continue
                    seen.add(key)

                    # flights_multi doesn't have top-level flyFrom/flyTo
                    # Extract from the route sub-objects
                    route_legs = item.get("route", [])

                    flight = self.parse_flight(item, strategy="open_jaw")

                    # Fix missing top-level fields from route
                    if route_legs:
                        first_leg = route_legs[0]
                        last_leg = route_legs[-1]
                        if not flight.fly_from:
                            flight.fly_from = first_leg.get("flyFrom", origin)
                        if not flight.fly_to:
                            flight.fly_to = first_leg.get("flyTo", destination)
                        if not flight.city_from:
                            flight.city_from = first_leg.get("cityFrom", "")
                        if not flight.city_to:
                            flight.city_to = first_leg.get("cityTo", "")
                        if not flight.city_code_from:
                            flight.city_code_from = first_leg.get("cityCodeFrom", origin)
                        if not flight.city_code_to:
                            flight.city_code_to = first_leg.get("cityCodeTo", destination)
                        if not flight.country_from:
                            flight.country_from = first_leg.get("countryFrom", {})
                        if not flight.country_to:
                            flight.country_to = first_leg.get("countryTo", {})
                        if not flight.local_departure:
                            flight.local_departure = first_leg.get("local_departure", "")
                        if not flight.local_arrival:
                            flight.local_arrival = last_leg.get("local_arrival", "")

                    # Calculate nights between outbound arrival and return departure
                    nights = 0
                    if len(route_legs) >= 2:
                        try:
                            # Find last outbound leg and first return leg
                            out_legs = [r for r in route_legs if r.get("flyTo", "").upper() in (destination.upper(), "") or route_legs.index(r) == 0]
                            leg1_arr = route_legs[0].get("local_arrival", "")[:10]
                            leg2_dep = route_legs[-1].get("local_departure", "")[:10]
                            if leg1_arr and leg2_dep:
                                dt1 = datetime.fromisoformat(leg1_arr)
                                dt2 = datetime.fromisoformat(leg2_dep)
                                nights = max(0, (dt2 - dt1).days)
                        except (ValueError, TypeError):
                            pass

                    flight.price = price
                    flight.nights_in_dest = nights
                    # Ensure destination info is correct (not the return city)
                    flight.city_code_to = destination.upper()
                    flight.strategy_explanation = (
                        f"Open jaw: {origin}→{destination}, return from {alt}→{origin} — €{price}"
                    )
                    results.append(flight)

                logger.info(f"Open jaw return from {alt}: {len(items)} results, cheapest €{items[0].get('price','?')}")

            await asyncio.sleep(2)

        results.sort(key=lambda r: r.price)
        logger.info(f"Open jaw total: {len(results)} results for {origin}→{destination}")
        return results[:30]

from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import date, timedelta
from typing import Any

from api.schemas import FlightResult, SearchRequest
from services.locations import resolve_location
from strategies.standard import StandardStrategy
from strategies.hidden_city import HiddenCityStrategy
from strategies.throwaway import ThrowawayStrategy
from strategies.open_jaw import OpenJawStrategy
from strategies.double_open_jaw import DoubleOpenJawStrategy
from strategies.back_to_back import BackToBackStrategy
from strategies.split_ticket import SplitTicketStrategy
from strategies.positioning import PositioningStrategy
from strategies.everywhere import EverywhereStrategy
from strategies.day_arbitrage import DayArbitrageStrategy
from strategies.nearby_airport import NearbyAirportStrategy
from strategies.mixed_carrier import MixedCarrierStrategy

logger = logging.getLogger("search_service")

STRATEGY_MAP = {
    "standard": StandardStrategy,
    "hidden_city": HiddenCityStrategy,
    "throwaway": ThrowawayStrategy,
    "open_jaw": OpenJawStrategy,
    "double_open_jaw": DoubleOpenJawStrategy,
    "back_to_back": BackToBackStrategy,
    "split_ticket": SplitTicketStrategy,
    "positioning": PositioningStrategy,
    "everywhere": EverywhereStrategy,
    "day_arbitrage": DayArbitrageStrategy,
    "nearby_airport": NearbyAirportStrategy,
    "mixed_carrier": MixedCarrierStrategy,
}

ALL_STRATEGIES = list(STRATEGY_MAP.keys())


def _format_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _build_search_params(req: SearchRequest, origin_code: str, dest_code: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "fly_from": origin_code,
        "adults": req.adults,
        "selected_cabins": req.selected_cabins,
        "flight_type": req.flight_type,
    }
    if dest_code:
        params["fly_to"] = dest_code
    if req.max_price:
        params["max_price"] = req.max_price

    today = date.today()

    if req.date_mode == "exact":
        params["date_from"] = req.date_from or _format_date(today + timedelta(days=7))
        params["date_to"] = req.date_to or params["date_from"]
        if req.flight_type == "round":
            params["return_from"] = req.return_from or ""
            params["return_to"] = req.return_to or ""
            if not params["return_from"]:
                params.pop("return_from", None)
                params.pop("return_to", None)
                params["nights_in_dst_from"] = req.nights_min
                params["nights_in_dst_to"] = req.nights_max

    elif req.date_mode == "range":
        params["date_from"] = req.date_from or _format_date(today + timedelta(days=7))
        params["date_to"] = req.date_to or _format_date(today + timedelta(days=60))
        if req.flight_type == "round":
            params["nights_in_dst_from"] = req.nights_min
            params["nights_in_dst_to"] = req.nights_max

    elif req.date_mode == "month":
        year = req.year or today.year
        month = req.month or today.month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        if first_day < today:
            first_day = today
        params["date_from"] = _format_date(first_day)
        params["date_to"] = _format_date(last_day)
        if req.flight_type == "round":
            params["nights_in_dst_from"] = req.nights_min
            params["nights_in_dst_to"] = req.nights_max

    elif req.date_mode == "cheapest":
        params["date_from"] = _format_date(today + timedelta(days=1))
        params["date_to"] = _format_date(today + timedelta(days=30 * req.months_ahead))
        if req.flight_type == "round":
            params["nights_in_dst_from"] = req.nights_min
            params["nights_in_dst_to"] = req.nights_max

    elif req.date_mode == "weekends":
        params["date_from"] = req.weekends_from or _format_date(today + timedelta(days=1))
        params["date_to"] = req.weekends_to or _format_date(today + timedelta(days=60))
        params["only_weekends"] = True
        if req.flight_type == "round":
            params["nights_in_dst_from"] = 1
            params["nights_in_dst_to"] = 3

    else:
        params["date_from"] = req.date_from or _format_date(today + timedelta(days=7))
        params["date_to"] = req.date_to or _format_date(today + timedelta(days=60))
        if req.flight_type == "round":
            params["nights_in_dst_from"] = req.nights_min
            params["nights_in_dst_to"] = req.nights_max

    if req.max_stopovers is not None:
        params["max_stopovers"] = req.max_stopovers

    return params


async def run_search(req: SearchRequest) -> dict[str, Any]:
    origin_code = await resolve_location(req.origin)
    dest_code = await resolve_location(req.destination) if req.destination else None

    params = _build_search_params(req, origin_code, dest_code)

    # ALL strategies run by default — no filtering
    strategy_names = list(ALL_STRATEGIES)
    if not dest_code:
        # Without destination, only everywhere makes sense
        strategy_names = ["everywhere"]

    # Run all strategies in parallel
    tasks = []
    for name in strategy_names:
        cls = STRATEGY_MAP.get(name)
        if cls:
            strategy = cls()
            tasks.append((name, strategy.search(params)))

    raw_results = await asyncio.gather(
        *[t[1] for t in tasks], return_exceptions=True
    )

    # Collect results, deduplicate
    all_results: list[FlightResult] = []
    seen_ids: set[str] = set()
    strategies_used: set[str] = set()
    standard_price: int | None = None

    for i, res in enumerate(raw_results):
        name = tasks[i][0]
        if isinstance(res, Exception):
            logger.error(f"Strategy {name} failed: {res}")
            continue
        if not res:
            continue
        strategies_used.add(name)
        for flight in res:
            if flight.id and flight.id in seen_ids:
                continue
            if flight.id:
                seen_ids.add(flight.id)
            if name == "standard" and standard_price is None:
                standard_price = flight.price
            all_results.append(flight)

    # Calculate savings vs standard for strategies that didn't already set it
    if standard_price:
        for flight in all_results:
            if flight.savings_pct is None and flight.strategy != "standard" and flight.price < standard_price:
                flight.savings_pct = round((1 - flight.price / standard_price) * 100, 1)
                flight.savings_vs = standard_price

    all_results.sort(key=lambda r: r.price)

    cheapest = all_results[0].price if all_results else None

    return {
        "results": all_results,
        "total": len(all_results),
        "cheapest": cheapest,
        "strategies_used": sorted(strategies_used),
    }


COUNTRY_TO_CONTINENT: dict[str, str] = {
    # Europe
    "ES": "europe", "FR": "europe", "DE": "europe", "IT": "europe", "PT": "europe",
    "GB": "europe", "NL": "europe", "BE": "europe", "CH": "europe", "AT": "europe",
    "GR": "europe", "TR": "europe", "PL": "europe", "CZ": "europe", "SE": "europe",
    "NO": "europe", "DK": "europe", "FI": "europe", "IE": "europe", "HR": "europe",
    "HU": "europe", "RO": "europe", "BG": "europe", "RS": "europe", "SK": "europe",
    "SI": "europe", "LT": "europe", "LV": "europe", "EE": "europe", "MT": "europe",
    "CY": "europe", "LU": "europe", "IS": "europe", "AL": "europe", "ME": "europe",
    "MK": "europe", "BA": "europe", "MD": "europe", "UA": "europe", "BY": "europe",
    "XK": "europe", "GE": "europe", "AM": "europe", "AZ": "europe",
    # Africa
    "MA": "africa", "TN": "africa", "EG": "africa", "ZA": "africa", "KE": "africa",
    "NG": "africa", "GH": "africa", "SN": "africa", "TZ": "africa", "ET": "africa",
    "DZ": "africa", "MU": "africa", "CV": "africa", "CM": "africa", "CI": "africa",
    "MZ": "africa", "UG": "africa", "RW": "africa", "GM": "africa", "LY": "africa",
    # Americas
    "US": "americas", "CA": "americas", "MX": "americas", "BR": "americas",
    "AR": "americas", "CL": "americas", "CO": "americas", "PE": "americas",
    "CU": "americas", "DO": "americas", "CR": "americas", "PA": "americas",
    "EC": "americas", "UY": "americas", "JM": "americas", "TT": "americas",
    "PR": "americas", "GT": "americas", "HN": "americas", "SV": "americas",
    "BO": "americas", "PY": "americas", "VE": "americas", "NI": "americas",
    # Asia
    "AE": "asia", "SA": "asia", "QA": "asia", "BH": "asia", "OM": "asia",
    "KW": "asia", "JO": "asia", "LB": "asia", "IL": "asia", "IN": "asia",
    "TH": "asia", "VN": "asia", "JP": "asia", "KR": "asia", "CN": "asia",
    "SG": "asia", "MY": "asia", "ID": "asia", "PH": "asia", "LK": "asia",
    "NP": "asia", "KH": "asia", "MM": "asia", "LA": "asia", "MV": "asia",
    "UZ": "asia", "KZ": "asia", "KG": "asia",
    # Oceania
    "AU": "oceania", "NZ": "oceania", "FJ": "oceania", "PF": "oceania",
}


def get_continent(country_code: str) -> str:
    return COUNTRY_TO_CONTINENT.get(country_code.upper(), "other")


def _extract_explore_item(item: dict[str, Any], origin_upper: str) -> dict[str, Any] | None:
    """Extract and validate a single explore result from a Kiwi flight item."""
    fly_from = item.get("flyFrom", "")
    city_code_from = item.get("cityCodeFrom", "")
    city_code_to = item.get("cityCodeTo", "")
    city_to = item.get("cityTo", "")
    fly_to = item.get("flyTo", "")

    if city_code_from.upper() != origin_upper and fly_from.upper() != origin_upper:
        return None

    route = item.get("route", [])
    if route:
        last_seg = route[-1]
        return_city = last_seg.get("cityCodeTo", "").upper()
        return_airport = last_seg.get("flyTo", "").upper()
        if return_city != origin_upper and return_airport != origin_upper:
            return None

    country_code = item.get("countryTo", {}).get("code", "")
    duration_dep = item.get("duration", {}).get("departure", 0)
    max_stops = item.get("max_stopovers", None)
    route_len_outbound = sum(1 for r in route if r.get("return", 0) == 0)
    is_direct = route_len_outbound <= 1

    return {
        "city": city_to,
        "city_code": city_code_to,
        "country": item.get("countryTo", {}).get("name", ""),
        "country_code": country_code,
        "price": item.get("price", 0),
        "local_departure": item.get("local_departure", ""),
        "local_arrival": item.get("local_arrival", ""),
        "deep_link": item.get("deep_link", ""),
        "fly_from": fly_from,
        "fly_to": fly_to,
        "nights_in_dest": item.get("nightsInDest", 0),
        "airlines": item.get("airlines", []),
        "continent": get_continent(country_code),
        "distance_km": round(item.get("distance", 0)),
        "flight_duration_hours": round(duration_dep / 3600, 1) if duration_dep else 0,
        "is_direct": is_direct,
        "best_strategy": "standard",
        "savings_pct": 0,
        "virtual_interlining": item.get("virtual_interlining", False),
    }


async def run_explore(
    origin: str,
    budget: int,
    date_from: str | None = None,
    date_to: str | None = None,
    nights_min: int = 2,
    nights_max: int = 7,
    flight_type: str = "round",
    continent: str | None = None,
    max_duration: float | None = None,
    direct_only: bool = False,
    sort_by: str = "price",
) -> dict[str, Any]:
    from clients.kiwi import get_kiwi_client
    from services.locations import get_nearby_airports

    origin_code = await resolve_location(origin)
    today = date.today()
    client = get_kiwi_client()
    origin_upper = origin_code.upper()

    d_from = date_from or _format_date(today + timedelta(days=7))
    d_to = date_to or _format_date(today + timedelta(days=90))

    # --- Phase 1: Multi-pronged discovery (NO price_to — we want to DISCOVER destinations) ---
    # Search 1: Standard from origin, sorted by price, no price cap (discover everything)
    # Search 2: Same but with virtual interlining (mixed carrier deals)
    # Search 3: From nearby airports (nearby airport arbitrage)
    # Search 4: Direct flights only (users love these)

    nearby = await get_nearby_airports(origin_code, radius_km=250)
    nearby_codes = [a.get("code", "") for a in nearby if a.get("code") and a.get("code") != origin_code][:5]
    fly_from_all = ",".join([origin_code] + nearby_codes) if nearby_codes else origin_code

    base = {
        "date_from": d_from,
        "date_to": d_to,
        "curr": "EUR",
        "sort": "price",
        "adults": 1,
        "selected_cabins": "M",
        "nights_in_dst_from": nights_min,
        "nights_in_dst_to": nights_max,
    }

    # one_for_city only works on one-way, but it's the ONLY way to get diverse destinations
    # We do one-way discovery first, then round-trip pricing for found cities
    discovery_base = {
        "fly_from": origin_code,
        "date_from": d_from,
        "date_to": d_to,
        "curr": "EUR",
        "sort": "price",
        "adults": 1,
        "selected_cabins": "M",
        "one_for_city": 1,
    }

    searches = [
        # One-way discovery — one_for_city gets us MANY different destinations
        ("discovery", {**discovery_base, "limit": 500}),
        ("discovery_vi", {**discovery_base, "limit": 500, "enable_vi": "true"}),
        ("discovery_nearby", {**discovery_base, "fly_from": fly_from_all, "limit": 500}),
        ("roundtrip", {**base, "fly_from": origin_code, "limit": 500}),
        ("roundtrip_vi", {**base, "fly_from": origin_code, "limit": 500, "enable_vi": "true"}),
        ("roundtrip_nearby", {**base, "fly_from": fly_from_all, "limit": 500}),
        ("direct", {**base, "fly_from": origin_code, "limit": 300, "max_stopovers": 0}),
    ]

    tasks = []
    for label, params in searches:
        tasks.append((label, client.search(params)))

    raw = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    # --- Phase 2: Aggregate best per city across all searches ---
    city_best: dict[str, dict[str, Any]] = {}
    city_max_price: dict[str, int] = {}

    # Track which cities we discovered (one-way) vs have round-trip prices for
    discovered_cities: set[str] = set()
    has_roundtrip: set[str] = set()

    for i, (label, _) in enumerate(searches):
        data = raw[i]
        if isinstance(data, Exception):
            logger.error(f"Explore {label} failed: {data}")
            continue
        items = data.get("data", []) if isinstance(data, dict) else []
        is_discovery = label.startswith("discovery")

        for item in items:
            city_code_to = item.get("cityCodeTo", "")
            city_to = item.get("cityTo", "")
            fly_from = item.get("flyFrom", "")
            fly_to = item.get("flyTo", "")
            city_code_from = item.get("cityCodeFrom", "")
            country_code = item.get("countryTo", {}).get("code", "")
            price = item.get("price", 0)

            # Must depart from origin area
            if city_code_from.upper() != origin_upper and fly_from.upper() != origin_upper:
                # For nearby airport searches, allow nearby origins
                if "nearby" not in label:
                    continue

            city_key = city_code_to or city_to
            if not city_key:
                continue

            if is_discovery:
                discovered_cities.add(city_key)
            else:
                # For round-trip, verify return goes back to origin
                route = item.get("route", [])
                if route:
                    last_seg = route[-1]
                    ret_city = last_seg.get("cityCodeTo", "").upper()
                    ret_apt = last_seg.get("flyTo", "").upper()
                    if ret_city != origin_upper and ret_apt != origin_upper:
                        continue
                has_roundtrip.add(city_key)

            duration_dep = item.get("duration", {}).get("departure", 0)
            route = item.get("route", [])
            route_out = sum(1 for r in route if r.get("return", 0) == 0)

            result = {
                "city": city_to,
                "city_code": city_code_to,
                "country": item.get("countryTo", {}).get("name", ""),
                "country_code": country_code,
                "price": price,
                "local_departure": item.get("local_departure", ""),
                "local_arrival": item.get("local_arrival", ""),
                "deep_link": item.get("deep_link", ""),
                "fly_from": fly_from,
                "fly_to": fly_to,
                "nights_in_dest": item.get("nightsInDest") or 0,
                "airlines": item.get("airlines", []),
                "continent": get_continent(country_code),
                "distance_km": round(item.get("distance", 0)),
                "flight_duration_hours": round(duration_dep / 3600, 1) if duration_dep else 0,
                "is_direct": route_out <= 1,
                "best_strategy": "standard",
                "savings_pct": 0,
                "is_roundtrip": not is_discovery,
            }

            # Tag strategy
            if "vi" in label and item.get("virtual_interlining"):
                result["best_strategy"] = "mixed_carrier"
            elif "nearby" in label and fly_from.upper() != origin_upper:
                result["best_strategy"] = "nearby_airport"
            elif label == "direct":
                result["best_strategy"] = "direct"

            city_max_price[city_key] = max(city_max_price.get(city_key, 0), price)

            # Prefer round-trip over discovery; then cheapest
            if city_key not in city_best:
                city_best[city_key] = result
            else:
                existing = city_best[city_key]
                # Round-trip always beats discovery
                if not existing.get("is_roundtrip") and result.get("is_roundtrip"):
                    city_best[city_key] = result
                elif existing.get("is_roundtrip") == result.get("is_roundtrip") and price < existing["price"]:
                    city_best[city_key] = result

    # --- Phase 3: Enrich with savings ---
    explore_results: list[dict[str, Any]] = []
    for city_key, result in city_best.items():
        max_p = city_max_price.get(city_key, result["price"])
        if max_p > result["price"] and max_p > 0:
            result["savings_pct"] = round((1 - result["price"] / max_p) * 100, 1)
        # Mark discovery-only results (no round-trip found)
        is_rt = result.pop("is_roundtrip", False)
        if not is_rt:
            # Discovery-only: price is one-way, estimate round-trip
            result["price"] = result["price"] * 2  # rough estimate
            result["best_strategy"] = "estimated"
            # Replace one-way deep_link with a round-trip search link on Kiwi
            city_code = result.get("city_code") or result.get("fly_to", "")
            if city_code and origin_code:
                result["deep_link"] = (
                    f"https://www.kiwi.com/en/search/results"
                    f"/{origin_code}/{city_code}"
                    f"/{d_from}/{d_to}"
                    f"/{nights_min}-{nights_max}nights"
                )
        explore_results.append(result)

    # --- Phase 4: Apply filters ---
    if budget:
        explore_results = [r for r in explore_results if r["price"] <= budget]
    if continent:
        explore_results = [r for r in explore_results if r["continent"] == continent]
    if max_duration:
        explore_results = [r for r in explore_results if r["flight_duration_hours"] <= max_duration]
    if direct_only:
        explore_results = [r for r in explore_results if r["is_direct"]]

    sort_keys = {
        "price": lambda r: r["price"],
        "distance": lambda r: r["distance_km"],
        "duration": lambda r: r["flight_duration_hours"],
        "destination": lambda r: r["city"].lower(),
    }
    explore_results.sort(key=sort_keys.get(sort_by, sort_keys["price"]))

    return {
        "results": explore_results,
        "total": len(explore_results),
        "origin": origin_code,
    }

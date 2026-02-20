from __future__ import annotations

import asyncio
import calendar
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
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


async def run_search(req: SearchRequest, job_store: dict | None = None, job_id: str | None = None) -> dict[str, Any]:
    # Validate & auto-fix nights
    if req.nights_min and req.nights_max and req.nights_min > req.nights_max:
        req.nights_min, req.nights_max = req.nights_max, req.nights_min

    origin_code = await resolve_location(req.origin)
    dest_code = await resolve_location(req.destination) if req.destination else None

    params = _build_search_params(req, origin_code, dest_code)

    # Use requested strategies, or defaults
    if req.strategies:
        strategy_names = [s for s in req.strategies if s in ALL_STRATEGIES]
    else:
        strategy_names = list(ALL_STRATEGIES)
    if not dest_code:
        strategy_names = ["everywhere"]

    total_strategies = len(strategy_names)

    # Run strategies one by one for streaming progress
    all_results: list[FlightResult] = []
    seen_ids: set[str] = set()
    strategies_used: set[str] = set()
    standard_price: int | None = None

    def _update_job(current_strategy: str, strategies_done: int):
        if not job_store or not job_id:
            return
        # Build partial serializable results
        partial = sorted(all_results, key=lambda r: r.price)
        if req.max_price:
            partial = [f for f in partial if f.price <= req.max_price]
        job_store[job_id] = {
            "status": "running",
            "current_strategy": current_strategy,
            "strategies_done": strategies_done,
            "strategies_total": total_strategies,
            "progress": max(1, int(strategies_done / total_strategies * 100)),
            "results": partial,
            "total": len(partial),
            "cheapest": partial[0].price if partial else None,
            "strategies_used": sorted(strategies_used),
        }

    for idx, name in enumerate(strategy_names):
        cls = STRATEGY_MAP.get(name)
        if not cls:
            continue

        _update_job(name, idx)

        strategy = cls()
        try:
            res = await strategy.search(params)
        except Exception as e:
            logger.error(f"Strategy {name} failed: {e}")
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

        _update_job(name, idx + 1)

    # Calculate savings vs standard
    if standard_price:
        for flight in all_results:
            if flight.savings_pct is None and flight.strategy != "standard" and flight.price < standard_price:
                flight.savings_pct = round((1 - flight.price / standard_price) * 100, 1)
                flight.savings_vs = standard_price

    if req.max_price:
        all_results = [f for f in all_results if f.price <= req.max_price]

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


def _get_countries_for_continent(cont: str) -> list[str]:
    """Return all country codes for a given continent."""
    return [cc for cc, c in COUNTRY_TO_CONTINENT.items() if c == cont]


def _parse_explore_item(item: dict, origin_upper: str, strategy: str = "standard") -> dict[str, Any] | None:
    """Parse a single Kiwi flight item into an explore result dict."""
    fly_from = item.get("flyFrom", "")
    city_code_to = item.get("cityCodeTo", "")
    city_to = item.get("cityTo", "")
    fly_to = item.get("flyTo", "")
    country_code = item.get("countryTo", {}).get("code", "")
    price = item.get("price", 0)

    # Verify return goes back to origin for round-trip
    route = item.get("route", [])
    if route:
        last_seg = route[-1]
        ret_city = last_seg.get("cityCodeTo", "").upper()
        ret_apt = last_seg.get("flyTo", "").upper()
        if ret_city != origin_upper and ret_apt != origin_upper:
            return None

    duration_dep = item.get("duration", {}).get("departure", 0)
    if isinstance(duration_dep, dict):
        duration_dep = duration_dep.get("total", 0)
    route_out = sum(1 for r in route if r.get("return", 0) == 0)

    return {
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
        "best_strategy": strategy,
        "savings_pct": 0,
        "virtual_interlining": item.get("virtual_interlining", False),
    }


async def _explore_continent(
    client: Any,
    origin_code: str,
    fly_from_all: str,
    countries: list[str],
    base_params: dict[str, Any],
    origin_upper: str,
    budget: int,
) -> list[dict[str, Any]]:
    """Aggressive country-by-country search for a specific continent.
    For each country: round-trip standard, round-trip VI, round-trip from nearby airports.
    """
    searches: list[tuple[str, dict[str, Any]]] = []

    for cc in countries:
        # Standard round-trip to country
        searches.append((f"rt_{cc}", {
            **base_params, "fly_from": origin_code, "fly_to": cc,
            "limit": 200, "sort": "price",
        }))
        # With virtual interlining
        searches.append((f"vi_{cc}", {
            **base_params, "fly_from": origin_code, "fly_to": cc,
            "limit": 200, "sort": "price", "enable_vi": "true",
        }))
        # From nearby airports
        searches.append((f"nearby_{cc}", {
            **base_params, "fly_from": fly_from_all, "fly_to": cc,
            "limit": 200, "sort": "price",
        }))

    logger.info(f"Continent explore: {len(searches)} searches for {len(countries)} countries")

    # Execute all in parallel (rate limiter in client handles throttling)
    coros = [client.search(p) for _, p in searches]
    raw = await asyncio.gather(*coros, return_exceptions=True)

    city_best: dict[str, dict[str, Any]] = {}

    for i, (label, _) in enumerate(searches):
        data = raw[i]
        if isinstance(data, Exception):
            logger.warning(f"Explore {label} failed: {data}")
            continue
        items = data.get("data", []) if isinstance(data, dict) else []

        strategy = "standard"
        if label.startswith("vi_"):
            strategy = "mixed_carrier"
        elif label.startswith("nearby_"):
            strategy = "nearby_airport"

        for item in items:
            price = item.get("price", 0)
            if budget and price > budget:
                continue
            result = _parse_explore_item(item, origin_upper, strategy)
            if not result:
                continue
            city_key = result["city_code"] or result["city"]
            if city_key not in city_best or price < city_best[city_key]["price"]:
                city_best[city_key] = result

    return list(city_best.values())


async def run_explore_legacy(
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

    nearby = await get_nearby_airports(origin_code, radius_km=250)
    nearby_codes = [a.get("code", "") for a in nearby if a.get("code") and a.get("code") != origin_code][:5]
    fly_from_all = ",".join([origin_code] + nearby_codes) if nearby_codes else origin_code

    base_rt = {
        "date_from": d_from,
        "date_to": d_to,
        "curr": "EUR",
        "adults": 1,
        "selected_cabins": "M",
        "nights_in_dst_from": nights_min,
        "nights_in_dst_to": nights_max,
    }

    # =====================================================
    # If continent is specified → aggressive per-country search
    # =====================================================
    if continent:
        countries = _get_countries_for_continent(continent)
        if not countries:
            return {"results": [], "total": 0, "origin": origin_code}

        explore_results = await _explore_continent(
            client, origin_code, fly_from_all, countries, base_rt, origin_upper, budget
        )

        # Apply remaining filters
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

    # =====================================================
    # No continent → generic everywhere discovery (original logic)
    # =====================================================
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
        ("discovery", {**discovery_base, "limit": 500}),
        ("discovery_vi", {**discovery_base, "limit": 500, "enable_vi": "true"}),
        ("discovery_nearby", {**discovery_base, "fly_from": fly_from_all, "limit": 500}),
        ("roundtrip", {**base_rt, "fly_from": origin_code, "limit": 500, "sort": "price"}),
        ("roundtrip_vi", {**base_rt, "fly_from": origin_code, "limit": 500, "sort": "price", "enable_vi": "true"}),
        ("roundtrip_nearby", {**base_rt, "fly_from": fly_from_all, "limit": 500, "sort": "price"}),
        ("direct", {**base_rt, "fly_from": origin_code, "limit": 300, "sort": "price", "max_stopovers": 0}),
    ]

    tasks = []
    for label, params in searches:
        tasks.append((label, client.search(params)))

    raw = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    city_best: dict[str, dict[str, Any]] = {}
    city_max_price: dict[str, int] = {}
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

            if city_code_from.upper() != origin_upper and fly_from.upper() != origin_upper:
                if "nearby" not in label:
                    continue

            city_key = city_code_to or city_to
            if not city_key:
                continue

            if is_discovery:
                discovered_cities.add(city_key)
            else:
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

            if "vi" in label and item.get("virtual_interlining"):
                result["best_strategy"] = "mixed_carrier"
            elif "nearby" in label and fly_from.upper() != origin_upper:
                result["best_strategy"] = "nearby_airport"
            elif label == "direct":
                result["best_strategy"] = "direct"

            city_max_price[city_key] = max(city_max_price.get(city_key, 0), price)

            if city_key not in city_best:
                city_best[city_key] = result
            else:
                existing = city_best[city_key]
                if not existing.get("is_roundtrip") and result.get("is_roundtrip"):
                    city_best[city_key] = result
                elif existing.get("is_roundtrip") == result.get("is_roundtrip") and price < existing["price"]:
                    city_best[city_key] = result

    explore_results: list[dict[str, Any]] = []
    for city_key, result in city_best.items():
        max_p = city_max_price.get(city_key, result["price"])
        if max_p > result["price"] and max_p > 0:
            result["savings_pct"] = round((1 - result["price"] / max_p) * 100, 1)
        is_rt = result.pop("is_roundtrip", False)
        if not is_rt:
            result["price"] = result["price"] * 2
            result["best_strategy"] = "estimated"
            city_code = result.get("city_code") or result.get("fly_to", "")
            if city_code and origin_code:
                result["deep_link"] = (
                    f"https://www.kiwi.com/en/search/results"
                    f"/{origin_code}/{city_code}"
                    f"/{d_from}/{d_to}"
                    f"/{nights_min}-{nights_max}nights"
                )
        explore_results.append(result)

    if budget:
        explore_results = [r for r in explore_results if r["price"] <= budget]
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


# Master destination list organized by continent
DESTINATIONS = {
    "europe": [
        "ROM", "PAR", "LON", "BCN", "AMS", "BER", "PRG", "VIE", "BUD", "WAW", 
        "ATH", "LIS", "DUB", "CPH", "OSL", "HEL", "IST", "ZAG", "BEG", "TIA",
        "SKP", "BUH", "SOF", "RIX", "VNO", "TLL", "MSQ", "KIV", "FRA", "MUC",
        "ZUR", "GVA", "MIL", "VCE", "NAP", "FCO", "MAD", "SVQ", "BIO", "VLC",
        "OPO", "STR", "LYS", "MRS", "NCE", "TLS", "BRU", "ANR", "RTM", "EDI",
        "MAN", "LIV", "BFS", "GOT", "STO", "BGO", "TRD", "REK", "KEF"
    ],
    "africa": [
        "CMN", "RAK", "TNG", "FEZ", "TUN", "CAI", "ALG", "CPT", "JNB", "DUR",
        "NBO", "DAR", "ADD", "LOS", "ABV", "ACC", "DKR", "BJL", "FNA", "CKY",
        "ABJ", "COO", "LBV", "MPM", "WDH", "GBE", "ASM", "TNR", "MRU", "RUN"
    ],
    "asia": [
        "BKK", "SGN", "HAN", "TYO", "NRT", "KIX", "ICN", "PUS", "DEL",
        "BOM", "BLR", "MAA", "DPS", "CGK", "KUL", "SIN", "MNL", "CMB",
        "TLV", "TBS", "EVN", "AMM", "DOH", "DXB", "AUH", "KWI", "BAH",
        "RUH", "JED", "MCT", "IKA", "ESB", "ALA", "TSE", "FRU", "TAS", "HKT",
        "VTE", "PNH", "RGN", "DAD", "CXR",
        "PEK", "PVG", "HKG", "TPE", "KTM", "REP", "CEB", "GMP",
    ],
    "americas": [
        "NYC", "JFK", "LGA", "EWR", "LAX", "SFO", "CHI", "ORD", "MIA", "DFW",
        "ATL", "BOS", "SEA", "DEN", "LAS", "PHX", "YYZ", "YVR", "YUL", "MEX",
        "CUN", "GDL", "BOG", "MDE", "LIM", "CUZ", "SCL", "EZE", "GRU", "RIO",
        "CGH", "BSB", "FOR", "SSA", "POA", "CWB", "MAO", "BEL", "HAV", "VRA",
        "SJO", "PTY", "SDQ", "PUJ", "UIO", "LPB", "ASU", "MVD", "CCS", "GEO"
    ],
    "oceania": [
        "SYD", "MEL", "BNE", "PER", "ADL", "DRW", "AKL", "WLG", "CHC", "ZQN", 
        "NAN", "SUV", "PPT", "NOU", "POM", "HNL", "GUM", "APW"
    ]
}

# Default strategies for explore
DEFAULT_EXPLORE_STRATEGIES = ["standard", "nearby_airport", "mixed_carrier", "day_arbitrage", "positioning", "open_jaw"]


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
    strategies: list[str] | None = None,
    months: list[str] | None = None,
    job_store: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """New hybrid city-by-city explore with strategy selector."""
    from clients.kiwi import get_kiwi_client
    from services.locations import resolve_location

    # Use default strategies if none provided
    if not strategies:
        strategies = DEFAULT_EXPLORE_STRATEGIES.copy()
    
    # Filter out strategies that don't make sense for explore
    valid_strategies = [s for s in strategies if s in STRATEGY_MAP and s != "everywhere"]
    if not valid_strategies:
        valid_strategies = ["standard"]
    
    origin_code = await resolve_location(origin)
    today = date.today()
    client = get_kiwi_client()
    origin_upper = origin_code.upper()

    # Build monthly date ranges from user selection (or default next 3 months)
    month_ranges: list[tuple[str, str]] = []
    earliest = today + timedelta(days=1)  # at least tomorrow

    if months:
        # User selected specific months like ["2026-03", "2026-07"]
        for m_str in sorted(months):
            try:
                year, month_num = int(m_str[:4]), int(m_str[5:7])
                m_start = date(year, month_num, 1)
                if m_start < earliest:
                    m_start = earliest  # don't search in the past
                if month_num == 12:
                    m_end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    m_end = date(year, month_num + 1, 1) - timedelta(days=1)
                if m_start <= m_end:
                    month_ranges.append((_format_date(m_start), _format_date(m_end)))
            except (ValueError, IndexError):
                continue
    else:
        # Default: next 3 months
        cursor = earliest
        for _ in range(3):
            m_start = cursor.replace(day=1)
            if m_start < cursor:
                m_start = cursor
            if m_start.month == 12:
                m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)
            month_ranges.append((_format_date(m_start), _format_date(m_end)))
            if m_start.month == 12:
                cursor = m_start.replace(year=m_start.year + 1, month=1, day=1)
            else:
                cursor = m_start.replace(month=m_start.month + 1, day=1)
    
    if not month_ranges:
        return {"results": [], "total": 0, "origin": origin_code}

    # Base search parameters (date ranges added per-month)
    base_params = {
        "curr": "EUR",
        "adults": 1,
        "selected_cabins": "M",
        "flight_type": flight_type,
        "nights_in_dst_from": nights_min,
        "nights_in_dst_to": nights_max,
        "max_price": budget if budget else None,
    }

    # Get destination list
    if continent and continent in DESTINATIONS:
        dest_cities = DESTINATIONS[continent]
    else:
        dest_cities = []
        for cont_cities in DESTINATIONS.values():
            dest_cities.extend(cont_cities)
    
    if not dest_cities:
        return {"results": [], "total": 0, "origin": origin_code}

    # City-by-city scan, month-by-month, with selected strategies
    all_results = []
    destinations_searched = 0
    total_destinations = len(dest_cities)
    
    # ── Test logging ──
    import time as _time
    _test_log_start = _time.time()
    _test_log_id = f"{origin_code}_{continent or 'all'}_{','.join(valid_strategies)}_{int(_test_log_start)}"

    logger.info(f"Starting explore: {total_destinations} destinations × {len(month_ranges)} months × {len(valid_strategies)} strategies")

    for i, dest_city in enumerate(dest_cities):
        destinations_searched += 1
        
        # Update progress in job store if provided
        if job_store and job_id:
            progress = max(1, int((destinations_searched / total_destinations) * 100))
            # Build aggregated partial results for streaming
            _partial_routes: dict[str, dict] = {}
            for _r in all_results:
                _ff = (_r.get("fly_from") or "").upper()
                _cc = (_r.get("city_code") or _r.get("city") or "").upper()
                _rk = f"{_ff}→{_cc}"
                if _rk not in _partial_routes:
                    _partial_routes[_rk] = {
                        "city": _r["city"], "city_code": _r.get("city_code", ""),
                        "country": _r.get("country", ""), "country_code": _r.get("country_code", ""),
                        "fly_from": _r.get("fly_from", ""), "continent": _r.get("continent", ""),
                        "distance_km": _r.get("distance_km", 0), "price": _r["price"],
                        "is_direct": _r.get("is_direct", False),
                        "best_strategy": _r.get("best_strategy", "standard"),
                        "flight_duration_hours": _r.get("flight_duration_hours", 0),
                        "airlines": _r.get("airlines", []),
                        "dates": [{"local_departure": _r.get("local_departure", ""), "price": _r["price"],
                                   "nights_in_dest": _r.get("nights_in_dest", 0), "deep_link": _r.get("deep_link", ""),
                                   "best_strategy": _r.get("best_strategy", "standard")}],
                    }
                else:
                    _d = _partial_routes[_rk]["dates"]
                    if len(_d) < 15:
                        _d.append({"local_departure": _r.get("local_departure", ""), "price": _r["price"],
                                   "nights_in_dest": _r.get("nights_in_dest", 0), "deep_link": _r.get("deep_link", ""),
                                   "best_strategy": _r.get("best_strategy", "standard")})
                    elif _r["price"] < max(x["price"] for x in _d):
                        _mi = max(range(len(_d)), key=lambda j: _d[j]["price"])
                        _d[_mi] = {"local_departure": _r.get("local_departure", ""), "price": _r["price"],
                                   "nights_in_dest": _r.get("nights_in_dest", 0), "deep_link": _r.get("deep_link", ""),
                                   "best_strategy": _r.get("best_strategy", "standard")}
                    if _r["price"] < _partial_routes[_rk]["price"]:
                        _partial_routes[_rk]["price"] = _r["price"]
            for _pr in _partial_routes.values():
                _pr["dates"].sort(key=lambda d: d["price"])
            _partial_list = sorted(_partial_routes.values(), key=lambda r: r["price"])[:250]
            job_store[job_id] = {
                "status": "running",
                "progress": progress,
                "destinations_searched": destinations_searched,
                "destinations_total": total_destinations,
                "current_destination": dest_city if isinstance(dest_city, str) else dest_city.get("city", ""),
                "results": _partial_list,
                "total": len(_partial_list)
            }

        # Search this destination month-by-month with each selected strategy
        for m_idx, (m_from, m_to) in enumerate(month_ranges):
            for strategy_name in valid_strategies:
                if strategy_name not in STRATEGY_MAP:
                    continue
                    
                try:
                    strategy_class = STRATEGY_MAP[strategy_name]
                    strategy = strategy_class()
                    
                    # Build params for this strategy with monthly date range
                    strategy_params = {
                        **base_params,
                        "fly_from": origin_code,
                        "fly_to": dest_city,
                        "date_from": m_from,
                        "date_to": m_to,
                    }
                    
                    # Call the strategy
                    strategy_results = await strategy.search(strategy_params)
                    
                    # Convert FlightResult objects to explore result dicts
                    logger.info(f"[explore] {strategy_name} returned {len(strategy_results)} results for {dest_city}, budget={budget}")
                    filtered_price = 0
                    filtered_origin = 0
                    for flight in strategy_results:
                        if flight.price > budget:
                            filtered_price += 1
                            continue
                            
                        # Verify this goes back to origin for round-trip
                        # Skip check for strategies that build combined one-way legs
                        skip_origin_check = strategy_name in ("split_ticket", "open_jaw", "double_open_jaw", "positioning")
                        if flight_type == "round" and not skip_origin_check:
                            route = flight.route or []
                            if route:
                                last_seg = route[-1]
                                ret_city = getattr(last_seg, 'city_code_to', '').upper()
                                ret_airport = getattr(last_seg, 'fly_to', '').upper()
                                if ret_city != origin_upper and ret_airport != origin_upper:
                                    filtered_origin += 1
                                    continue
                        
                        result = {
                            "city": flight.city_to,
                            "city_code": flight.city_code_to,
                            "country": flight.country_to.get("name", "") if flight.country_to else "",
                            "country_code": flight.country_to.get("code", "") if flight.country_to else "",
                            "price": flight.price,
                            "local_departure": flight.local_departure,
                            "local_arrival": flight.local_arrival,
                            "deep_link": flight.deep_link,
                            "fly_from": flight.fly_from,
                            "fly_to": flight.fly_to,
                            "nights_in_dest": flight.nights_in_dest,
                            "airlines": flight.airlines,
                            "continent": get_continent(flight.country_to.get("code", "") if flight.country_to else ""),
                            "distance_km": round(flight.distance),
                            "flight_duration_hours": round(flight.duration.get("departure", 0) / 3600, 1) if isinstance(flight.duration, dict) else 0,
                            "is_direct": len([r for r in (flight.route or []) if getattr(r, 'return_leg', 0) == 0]) <= 1,
                            "best_strategy": strategy_name,
                            "savings_pct": flight.savings_pct or 0,
                            "virtual_interlining": flight.virtual_interlining,
                        }
                        all_results.append(result)
                    
                    if filtered_price or filtered_origin:
                        logger.info(f"[explore] {strategy_name} {dest_city}: filtered {filtered_price} by price, {filtered_origin} by origin")
                        
                except Exception as e:
                    logger.warning(f"Strategy {strategy_name} failed for {dest_city} month {m_from}: {e}")
                    continue
                
                # Rate limiting: 3 seconds between API calls
                await asyncio.sleep(3)

    logger.info(f"[explore] Total all_results before aggregation: {len(all_results)}")
    # ── Aggregate by route (fly_from→city_code), keep top 5 cheapest date combos ──
    MAX_CARDS = 250
    MAX_DATES_PER_ROUTE = 15

    route_map: dict[str, dict[str, Any]] = {}  # key = "FLY_FROM→CITY_CODE"

    for result in all_results:
        fly_from = (result.get("fly_from") or "").upper()
        city_code = (result.get("city_code") or result.get("city") or "").upper()
        if not fly_from or not city_code:
            continue

        # Apply filters early
        if max_duration and result["flight_duration_hours"] > max_duration:
            continue
        if direct_only and not result["is_direct"]:
            continue

        route_key = f"{fly_from}→{city_code}"
        date_entry = {
            "local_departure": result.get("local_departure", ""),
            "local_arrival": result.get("local_arrival", ""),
            "price": result["price"],
            "nights_in_dest": result.get("nights_in_dest", 0),
            "deep_link": result.get("deep_link", ""),
            "airlines": result.get("airlines", []),
            "is_direct": result.get("is_direct", False),
            "best_strategy": result.get("best_strategy", "standard"),
            "flight_duration_hours": result.get("flight_duration_hours", 0),
        }

        if route_key not in route_map:
            route_map[route_key] = {
                "city": result["city"],
                "city_code": result.get("city_code", ""),
                "country": result.get("country", ""),
                "country_code": result.get("country_code", ""),
                "fly_from": result.get("fly_from", ""),
                "continent": result.get("continent", ""),
                "distance_km": result.get("distance_km", 0),
                "virtual_interlining": result.get("virtual_interlining", False),
                "dates": [date_entry],
            }
        else:
            dates = route_map[route_key]["dates"]
            # Deduplicate by departure date string (keep cheapest per date)
            dep_date = (result.get("local_departure") or "")[:10]
            existing_dates = {(d.get("local_departure") or "")[:10] for d in dates}
            if dep_date in existing_dates:
                # Replace if cheaper
                for j, d in enumerate(dates):
                    if (d.get("local_departure") or "")[:10] == dep_date and result["price"] < d["price"]:
                        dates[j] = date_entry
                        break
            elif len(dates) < MAX_DATES_PER_ROUTE:
                dates.append(date_entry)
            else:
                # Replace the most expensive if this is cheaper
                max_idx = max(range(len(dates)), key=lambda j: dates[j]["price"])
                if result["price"] < dates[max_idx]["price"]:
                    dates[max_idx] = date_entry

    # Build final cards sorted by cheapest price
    final_results = []
    for route_key, card in route_map.items():
        card["dates"].sort(key=lambda d: d["price"])
        card["price"] = card["dates"][0]["price"]  # headline price = cheapest
        card["best_strategy"] = card["dates"][0].get("best_strategy", "standard")
        card["is_direct"] = any(d["is_direct"] for d in card["dates"])
        card["airlines"] = card["dates"][0].get("airlines", [])
        card["flight_duration_hours"] = card["dates"][0].get("flight_duration_hours", 0)
        card["savings_pct"] = 0
        final_results.append(card)

    # Sort all cards
    sort_keys = {
        "price": lambda r: r["price"],
        "distance": lambda r: r["distance_km"],
        "duration": lambda r: r["flight_duration_hours"],
        "destination": lambda r: r["city"].lower(),
    }
    final_results.sort(key=sort_keys.get(sort_by, sort_keys["price"]))

    # Cap at MAX_CARDS
    final_results = final_results[:MAX_CARDS]

    # ── Save test log (toggle: enabled) ──
    try:
        _test_log_dir = Path(__file__).parent.parent / "test_logs"
        _test_log_dir.mkdir(exist_ok=True)
        _elapsed = round(_time.time() - _test_log_start, 1)
        _log_entry = {
            "id": _test_log_id,
            "timestamp": datetime.utcnow().isoformat(),
            "params": {
                "origin": origin_code,
                "budget": budget,
                "nights_min": nights_min,
                "nights_max": nights_max,
                "continent": continent,
                "months": [f"{mr[0]}-{mr[1]}" for mr in month_ranges],
                "strategies": valid_strategies,
                "flight_type": flight_type,
                "max_duration": max_duration,
                "direct_only": direct_only,
            },
            "stats": {
                "destinations_searched": destinations_searched,
                "destinations_total": total_destinations,
                "total_raw_results": len(all_results),
                "total_routes": len(final_results),
                "elapsed_seconds": _elapsed,
                "api_calls_approx": destinations_searched * len(month_ranges) * len(valid_strategies),
            },
            "results": final_results,
        }
        _log_file = _test_log_dir / f"{_test_log_id}.json"
        with open(_log_file, "w") as f:
            json.dump(_log_entry, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Test log saved: {_log_file.name} ({len(final_results)} routes, {_elapsed}s)")
    except Exception as e:
        logger.warning(f"Failed to save test log: {e}")

    return {
        "results": final_results,
        "total": len(final_results),
        "origin": origin_code,
        "destinations_searched": destinations_searched,
        "destinations_total": total_destinations,
        "strategies_used": valid_strategies,
    }

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

DEFAULT_STRATEGIES = ["standard", "nearby_airport", "day_arbitrage", "mixed_carrier"]
OPTIONAL_STRATEGIES = [
    "hidden_city", "throwaway", "open_jaw", "double_open_jaw",
    "split_ticket", "positioning", "back_to_back",
]

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

    # Determine which strategies to run
    strategy_names = list(DEFAULT_STRATEGIES)
    if req.strategies:
        for s in req.strategies:
            if s in STRATEGY_MAP and s not in strategy_names:
                strategy_names.append(s)
    if not dest_code:
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


async def run_explore(
    origin: str,
    budget: int,
    date_from: str | None = None,
    date_to: str | None = None,
    nights_min: int = 2,
    nights_max: int = 7,
    flight_type: str = "round",
) -> dict[str, Any]:
    origin_code = await resolve_location(origin)
    today = date.today()

    params: dict[str, Any] = {
        "fly_from": origin_code,
        "date_from": date_from or _format_date(today + timedelta(days=7)),
        "date_to": date_to or _format_date(today + timedelta(days=90)),
        "max_price": budget,
        "adults": 1,
        "selected_cabins": "M",
        "flight_type": "oneway",
        "limit": 100,
    }
    if flight_type == "round":
        params["nights_in_dst_from"] = nights_min
        params["nights_in_dst_to"] = nights_max
        params["flight_type"] = "round"
        params.pop("one_for_city", None)
    else:
        params["one_for_city"] = 1

    strategy = EverywhereStrategy()
    results = await strategy.search(params)

    explore_results = []
    seen_cities: set[str] = set()
    for flight in results:
        city_key = flight.city_code_to or flight.city_to
        if city_key in seen_cities:
            continue
        seen_cities.add(city_key)
        explore_results.append({
            "city": flight.city_to,
            "city_code": flight.city_code_to,
            "country": flight.country_to.get("name", ""),
            "country_code": flight.country_to.get("code", ""),
            "price": flight.price,
            "local_departure": flight.local_departure,
            "local_arrival": flight.local_arrival,
            "deep_link": flight.deep_link,
            "fly_from": flight.fly_from,
            "fly_to": flight.fly_to,
            "nights_in_dest": flight.nights_in_dest,
            "airlines": flight.airlines,
        })

    explore_results.sort(key=lambda r: r["price"])

    return {
        "results": explore_results,
        "total": len(explore_results),
        "origin": origin_code,
    }

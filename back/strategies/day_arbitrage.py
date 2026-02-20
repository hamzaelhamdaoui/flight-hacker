from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy

logger = logging.getLogger("day_arbitrage")

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _analyze_day_prices(items: list[dict]) -> tuple[dict[int, float], list[int]]:
    """Group prices by day-of-week, return averages and top 3 cheapest day indices."""
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
        return {}, []
    day_avgs: dict[int, float] = {}
    for dow, prices in day_prices.items():
        day_avgs[dow] = sum(prices) / len(prices) if prices else 0
    # Top 3 cheapest days
    sorted_days = sorted(day_avgs, key=lambda d: day_avgs[d])
    top3 = sorted_days[:3]
    return day_avgs, top3


def _get_dates_for_weekdays(date_from: str, date_to: str, weekdays: list[int]) -> list[str]:
    """Get all dates within range that fall on given weekday indices (0=Mon)."""
    fmt = "%d/%m/%Y"
    start = datetime.strptime(date_from, fmt)
    end = datetime.strptime(date_to, fmt)
    dates: list[str] = []
    current = start
    while current <= end:
        if current.weekday() in weekdays:
            dates.append(current.strftime(fmt))
        current += timedelta(days=1)
    return dates


class DayArbitrageStrategy(BaseStrategy):
    name = "day_arbitrage"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []

        client = get_kiwi_client()

        date_from = params.get("date_from", "")
        date_to = params.get("date_to", "")
        nights_from = params.get("nights_in_dst_from", 4)
        nights_to = params.get("nights_in_dst_to", 17)

        # --- Phase 1: Analyze cheapest days of week ---
        base = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": 500,
            "one_per_date": 1,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        outbound_params = {**base, "date_from": date_from, "date_to": date_to}

        # For return analysis, estimate return window based on nights
        fmt = "%d/%m/%Y"
        try:
            d_from = datetime.strptime(date_from, fmt)
            d_to = datetime.strptime(date_to, fmt)
            ret_from = (d_from + timedelta(days=nights_from)).strftime(fmt)
            ret_to = (d_to + timedelta(days=nights_to)).strftime(fmt)
        except (ValueError, TypeError):
            return []

        inbound_params = {
            **base,
            "fly_from": params["fly_to"],
            "fly_to": params["fly_from"],
            "date_from": ret_from,
            "date_to": ret_to,
        }

        logger.info(f"Phase 1: Analyzing day prices for {params['fly_from']}→{params['fly_to']}")
        out_data, in_data = await asyncio.gather(
            client.search(outbound_params),
            client.search(inbound_params),
            return_exceptions=True,
        )

        if isinstance(out_data, Exception):
            out_data = {"data": []}
        if isinstance(in_data, Exception):
            in_data = {"data": []}

        out_avgs, cheap_out_days = _analyze_day_prices(out_data.get("data", []))
        in_avgs, cheap_in_days = _analyze_day_prices(in_data.get("data", []))

        if not cheap_out_days:
            return []

        # Build explanation
        out_str = ", ".join(f"{DAY_NAMES[d]} €{out_avgs[d]:.0f}" for d in sorted(out_avgs))
        in_str = ", ".join(f"{DAY_NAMES[d]} €{in_avgs[d]:.0f}" for d in sorted(in_avgs)) if in_avgs else "N/A"
        explanation = (
            f"Outbound avg by day: {out_str}. "
            f"Return avg by day: {in_str}. "
            f"Best combo: depart {'/'.join(DAY_NAMES[d] for d in cheap_out_days)}, "
            f"return {'/'.join(DAY_NAMES[d] for d in cheap_in_days) if cheap_in_days else 'any'}"
        )
        logger.info(f"Phase 1 result: {explanation}")

        # --- Phase 2: Search round-trips on best day combos ---
        # Get specific dates that fall on cheapest outbound days
        out_dates = _get_dates_for_weekdays(date_from, date_to, cheap_out_days)
        if not out_dates:
            return []

        # Build round-trip searches pinned to cheap departure dates
        # Group outbound dates into batches of ~7 consecutive to reduce API calls
        phase2_tasks = []
        max_searches = 9  # 3 out days × 3 combos max

        for out_date in out_dates[:max_searches]:
            try:
                dep_dt = datetime.strptime(out_date, fmt)
                r_from = (dep_dt + timedelta(days=nights_from)).strftime(fmt)
                r_to = (dep_dt + timedelta(days=nights_to)).strftime(fmt)
            except (ValueError, TypeError):
                continue

            rt_params = {
                "fly_from": params["fly_from"],
                "fly_to": params["fly_to"],
                "date_from": out_date,
                "date_to": out_date,  # Pin departure to this exact date
                "return_from": r_from,
                "return_to": r_to,
                "curr": "EUR",
                "sort": "price",
                "limit": 20,
                "adults": params.get("adults", 1),
                "selected_cabins": params.get("selected_cabins", "M"),
                "nights_in_dst_from": str(nights_from),
                "nights_in_dst_to": str(nights_to),
            }
            if params.get("max_price"):
                rt_params["price_to"] = params["max_price"]
            if params.get("max_fly_duration"):
                rt_params["max_fly_duration"] = params["max_fly_duration"]
            if params.get("max_sector_stopovers") is not None:
                rt_params["max_sector_stopovers"] = params["max_sector_stopovers"]

            # If we know cheap return days, filter return dates to those days only
            if cheap_in_days:
                ret_dates = _get_dates_for_weekdays(r_from, r_to, cheap_in_days)
                if ret_dates:
                    # Use first and last to narrow the window
                    rt_params["return_from"] = ret_dates[0]
                    rt_params["return_to"] = ret_dates[-1]

            phase2_tasks.append(client.search(rt_params))

        if not phase2_tasks:
            return []

        logger.info(f"Phase 2: {len(phase2_tasks)} round-trip searches on best days")
        phase2_results = await asyncio.gather(*phase2_tasks, return_exceptions=True)

        # Collect and deduplicate results
        seen: set[str] = set()
        results: list[FlightResult] = []

        for data in phase2_results:
            if isinstance(data, Exception):
                continue
            for item in data.get("data", []):
                booking_token = item.get("booking_token", "")
                # Dedup by route+price+dates
                dep = item.get("local_departure", "")[:10]
                arr = item.get("local_arrival", "")[:10]
                price = item.get("price", 0)
                key = f"{dep}_{arr}_{price}"
                if key in seen:
                    continue
                seen.add(key)

                flight = self.parse_flight(item, strategy="day_arbitrage")
                flight.strategy_explanation = explanation
                results.append(flight)

        results.sort(key=lambda r: r.price)
        logger.info(f"Phase 2 done: {len(results)} unique results")
        return results[:30]

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


def _format_ticket_summary(item: dict) -> str:
    """Build a short summary like 'BCN→MAD, 10 Aug, Ryanair FR1234, €25'."""
    route = item.get("route", [])
    if not route:
        fly_from = item.get("flyFrom", "?")
        fly_to = item.get("flyTo", "?")
    else:
        # Use first outbound segment for summary
        first_seg = route[0]
        fly_from = first_seg.get("flyFrom", item.get("flyFrom", "?"))
        fly_to = first_seg.get("flyTo", item.get("flyTo", "?"))

    dep = item.get("local_departure", "")
    date_str = ""
    if dep:
        try:
            dt = datetime.fromisoformat(dep.replace("Z", "+00:00"))
            date_str = dt.strftime("%d %b")
        except (ValueError, TypeError):
            date_str = dep[:10]

    airlines = item.get("airlines", [])
    airline = airlines[0] if airlines else ""
    flight_no = ""
    if route:
        fn = route[0].get("flight_no", "")
        if fn:
            flight_no = f" {airline}{fn}"
        elif airline:
            flight_no = f" {airline}"
    elif airline:
        flight_no = f" {airline}"

    price = item.get("price", 0)
    return f"{fly_from}→{fly_to}, {date_str},{flight_no}, €{price}"


class BackToBackStrategy(BaseStrategy):
    name = "back_to_back"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []
        if params.get("flight_type") == "oneway":
            return []

        client = get_kiwi_client()

        # Get standard long-stay price
        std_params: dict[str, Any] = {
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
        if params.get("return_from"):
            std_params["return_from"] = params["return_from"]
        if params.get("return_to"):
            std_params["return_to"] = params["return_to"]
        if params.get("nights_in_dst_from") is not None:
            std_params["nights_in_dst_from"] = params["nights_in_dst_from"]
            std_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        std_data = await client.search(std_params)
        std_results = std_data.get("data", [])
        if not std_results:
            return []
        std_price = std_results[0].get("price", 0)
        if std_price == 0:
            return []

        return_from = params.get("return_from", params["date_from"])
        return_to = params.get("return_to", params["date_to"])

        # Ticket 1: origin→dest with short stay (1-2 nights)
        t1_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "fly_to": params["fly_to"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "nights_in_dst_from": 1,
            "nights_in_dst_to": 2,
            "curr": "EUR",
            "sort": "price",
            "limit": 100,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        # Ticket 2: dest→origin with short stay (1-2 nights)
        t2_params: dict[str, Any] = {
            "fly_from": params["fly_to"],
            "fly_to": params["fly_from"],
            "date_from": return_from,
            "date_to": return_to,
            "nights_in_dst_from": 1,
            "nights_in_dst_to": 2,
            "curr": "EUR",
            "sort": "price",
            "limit": 100,
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        t1_data, t2_data = await asyncio.gather(
            client.search(t1_params),
            client.search(t2_params),
            return_exceptions=True,
        )

        if isinstance(t1_data, Exception) or isinstance(t2_data, Exception):
            return []

        t1_items = t1_data.get("data", [])
        t2_items = t2_data.get("data", [])

        if not t1_items or not t2_items:
            return []

        # Try top 3 t1 × top 3 t2 combinations (9 combos max)
        results: list[FlightResult] = []

        for t1 in t1_items[:3]:
            t1_price = t1.get("price", 0)
            for t2 in t2_items[:3]:
                t2_price = t2.get("price", 0)
                combined = t1_price + t2_price
                if combined >= std_price:
                    continue

                # Extract flight details for explanation
                t1_route = t1.get("route", [])
                t2_route = t2.get("route", [])
                t1_dep = t1.get("local_departure", "")[:16]
                t2_dep = t2.get("local_departure", "")[:16]
                t1_airlines = t1.get("airlines", [])
                t2_airlines = t2.get("airlines", [])
                t1_airline_str = t1_airlines[0] if t1_airlines else ""
                t2_airline_str = t2_airlines[0] if t2_airlines else ""
                t1_fn = ""
                t2_fn = ""
                if t1_route:
                    fn = t1_route[0].get("flight_no", "")
                    if fn:
                        t1_fn = f" {t1_airline_str}{fn}"
                if t2_route:
                    fn = t2_route[0].get("flight_no", "")
                    if fn:
                        t2_fn = f" {t2_airline_str}{fn}"

                flight = self.parse_flight(t1, strategy="back_to_back")
                flight.price = combined
                savings = round((1 - combined / std_price) * 100, 1)
                flight.savings_pct = savings
                flight.savings_vs = std_price

                # Populate ticket 2 info
                flight.ticket_2_deep_link = t2.get("deep_link", "")
                flight.ticket_2_booking_token = t2.get("booking_token", "")
                flight.ticket_2_summary = _format_ticket_summary(t2)

                flight.strategy_explanation = (
                    f"Ticket 1: {params['fly_from']}→{params['fly_to']} "
                    f"({t1_dep},{t1_fn}, €{t1_price}). "
                    f"Ticket 2: {params['fly_to']}→{params['fly_from']} "
                    f"({t2_dep},{t2_fn}, €{t2_price}). "
                    f"Use outbound of T1 + return of T2. "
                    f"Combined €{combined} vs €{std_price}. Save {savings}%"
                )
                results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:10]

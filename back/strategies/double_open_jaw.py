from __future__ import annotations

import asyncio
from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from services.locations import get_nearby_airports
from strategies.base import BaseStrategy


class DoubleOpenJawStrategy(BaseStrategy):
    name = "double_open_jaw"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        if not params.get("fly_to"):
            return []
        if params.get("flight_type") == "oneway":
            return []

        client = get_kiwi_client()

        # Get standard price
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

        # Find nearby airports to both origin and destination
        nearby_origin_task = get_nearby_airports(params["fly_from"], radius_km=250)
        nearby_dest_task = get_nearby_airports(params["fly_to"], radius_km=250)
        nearby_origin, nearby_dest = await asyncio.gather(nearby_origin_task, nearby_dest_task)

        origin_alts = [
            a.get("code", "") for a in nearby_origin
            if a.get("code") and a.get("code") != params["fly_from"]
        ][:5]
        dest_alts = [
            a.get("code", "") for a in nearby_dest
            if a.get("code") and a.get("code") != params["fly_to"]
        ][:5]

        if not origin_alts or not dest_alts:
            return []

        return_from = params.get("return_from", params["date_from"])
        return_to = params.get("return_to", params["date_to"])

        # Build combinations (limit to 10)
        combos = []
        for d_alt in dest_alts:
            for o_alt in origin_alts:
                combos.append((d_alt, o_alt))
                if len(combos) >= 10:
                    break
            if len(combos) >= 10:
                break

        tasks = []
        for d_alt, o_alt in combos:
            body: dict[str, Any] = {
                "requests": [
                    {
                        "fly_from": params["fly_from"],
                        "fly_to": params["fly_to"],
                        "date_from": params["date_from"],
                        "date_to": params["date_to"],
                        "adults": params.get("adults", 1),
                        "selected_cabins": params.get("selected_cabins", "M"),
                    },
                    {
                        "fly_from": d_alt,
                        "fly_to": o_alt,
                        "date_from": return_from,
                        "date_to": return_to,
                        "adults": params.get("adults", 1),
                        "selected_cabins": params.get("selected_cabins", "M"),
                    },
                ],
                "curr": "EUR",
                "limit": 50,
            }
            tasks.append(client.search_multi(body))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[FlightResult] = []
        for i, res in enumerate(all_results):
            if isinstance(res, Exception) or not res:
                continue
            d_alt, o_alt = combos[i]
            for item in res:
                price = item.get("price", 0)
                if price >= std_price:
                    continue
                flight = self.parse_flight(item, strategy="double_open_jaw")
                savings = round((1 - price / std_price) * 100, 1)
                flight.savings_pct = savings
                flight.savings_vs = std_price
                flight.strategy_explanation = (
                    f"Fly {params['fly_from']}→{params['fly_to']}, "
                    f"return {d_alt}→{o_alt}. "
                    f"Save {savings}% vs standard (€{std_price})"
                )
                results.append(flight)

        results.sort(key=lambda r: r.price)
        return results[:15]

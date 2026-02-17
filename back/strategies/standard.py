from __future__ import annotations

from typing import Any

from api.schemas import FlightResult
from clients.kiwi import get_kiwi_client
from strategies.base import BaseStrategy


class StandardStrategy(BaseStrategy):
    name = "standard"

    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        client = get_kiwi_client()
        search_params: dict[str, Any] = {
            "fly_from": params["fly_from"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "curr": "EUR",
            "sort": "price",
            "limit": params.get("limit", 500),
            "adults": params.get("adults", 1),
            "selected_cabins": params.get("selected_cabins", "M"),
        }

        if params.get("fly_to"):
            search_params["fly_to"] = params["fly_to"]

        if params.get("flight_type") == "oneway":
            pass  # no return params
        else:
            if params.get("return_from"):
                search_params["return_from"] = params["return_from"]
            if params.get("return_to"):
                search_params["return_to"] = params["return_to"]
            if params.get("nights_in_dst_from") is not None:
                search_params["nights_in_dst_from"] = params["nights_in_dst_from"]
                search_params["nights_in_dst_to"] = params.get("nights_in_dst_to", params["nights_in_dst_from"])

        if params.get("max_stopovers") is not None:
            search_params["max_stopovers"] = params["max_stopovers"]
        if params.get("max_price") is not None:
            search_params["price_to"] = params["max_price"]
        if params.get("only_weekends"):
            search_params["only_weekends"] = "true"

        data = await client.search(search_params)
        results = []
        for item in data.get("data", []):
            results.append(self.parse_flight(item, strategy="standard"))
        return results

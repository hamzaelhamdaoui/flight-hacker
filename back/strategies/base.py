from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from api.schemas import FlightResult, RouteSegment


class BaseStrategy(ABC):
    name: str = ""

    @abstractmethod
    async def search(self, params: dict[str, Any]) -> list[FlightResult]:
        ...

    def parse_flight(self, item: dict, strategy: str = "standard") -> FlightResult:
        route_segments = []
        for seg in item.get("route", []):
            route_segments.append(RouteSegment(
                id=seg.get("id", ""),
                fly_from=seg.get("flyFrom", ""),
                fly_to=seg.get("flyTo", ""),
                city_from=seg.get("cityFrom", ""),
                city_to=seg.get("cityTo", ""),
                city_code_from=seg.get("cityCodeFrom", ""),
                city_code_to=seg.get("cityCodeTo", ""),
                local_departure=seg.get("local_departure", ""),
                local_arrival=seg.get("local_arrival", ""),
                airline=seg.get("airline", ""),
                flight_no=seg.get("flight_no", 0),
                operating_carrier=seg.get("operating_carrier", ""),
                return_leg=seg.get("return", 0),
                bags_recheck_required=seg.get("bags_recheck_required", False),
                vi_connection=seg.get("vi_connection", False),
                fare_classes=seg.get("fare_classes", ""),
            ))

        return FlightResult(
            id=item.get("id", ""),
            fly_from=item.get("flyFrom", ""),
            fly_to=item.get("flyTo", ""),
            city_from=item.get("cityFrom", ""),
            city_to=item.get("cityTo", ""),
            city_code_from=item.get("cityCodeFrom", ""),
            city_code_to=item.get("cityCodeTo", ""),
            country_from=item.get("countryFrom", {}),
            country_to=item.get("countryTo", {}),
            local_departure=item.get("local_departure", ""),
            local_arrival=item.get("local_arrival", ""),
            utc_departure=item.get("utc_departure", ""),
            utc_arrival=item.get("utc_arrival", ""),
            nights_in_dest=item.get("nightsInDest") or 0,
            quality=item.get("quality", 0),
            distance=item.get("distance", 0),
            duration=item.get("duration") if isinstance(item.get("duration"), dict) else {"total": item.get("duration", 0)},
            price=item.get("price", 0),
            conversion=item.get("conversion", {}),
            fare=item.get("fare", {}),
            bags_price=item.get("bags_price", {}),
            baglimit=item.get("baglimit", {}),
            availability=item.get("availability", {}),
            airlines=item.get("airlines", []),
            route=route_segments,
            booking_token=item.get("booking_token", ""),
            deep_link=item.get("deep_link", ""),
            virtual_interlining=item.get("virtual_interlining", False),
            pnr_count=item.get("pnr_count", 1),
            has_airport_change=item.get("has_airport_change", False),
            technical_stops=item.get("technical_stops", 0),
            strategy=strategy,
        )

from __future__ import annotations

from fastapi import APIRouter, Query

from api.schemas import (
    ExploreResponse,
    LocationsResponse,
    SearchRequest,
    SearchResponse,
    StrategiesResponse,
    StrategyInfo,
)
from services.locations import search_locations
from services.search import run_explore, run_search

router = APIRouter()

STRATEGY_LIST = [
    StrategyInfo(id="standard", name="Standard Search", description="Direct search for the best prices", default=True),
    StrategyInfo(id="nearby_airport", name="Nearby Airport", description="Compare prices from nearby airports", default=True),
    StrategyInfo(id="day_arbitrage", name="Day Arbitrage", description="Find the cheapest day of the week to fly", default=True),
    StrategyInfo(id="mixed_carrier", name="Mixed Carrier", description="Virtual interlining — combine airlines for cheaper fares", default=True),
    StrategyInfo(id="hidden_city", name="Hidden City", description="Book a flight with a layover at your real destination", default=False),
    StrategyInfo(id="throwaway", name="Throwaway Ticketing", description="Book round-trip when it's cheaper than one-way, skip the return", default=False),
    StrategyInfo(id="open_jaw", name="Open Jaw", description="Return from a nearby city for a lower fare", default=False),
    StrategyInfo(id="double_open_jaw", name="Double Open Jaw", description="Depart and return from different nearby cities", default=False),
    StrategyInfo(id="back_to_back", name="Back to Back", description="Two overlapping round-trips to hack minimum stay rules", default=False),
    StrategyInfo(id="split_ticket", name="Split Ticket", description="Buy separate tickets via a hub city", default=False),
    StrategyInfo(id="positioning", name="Positioning Flight", description="Fly to a nearby hub where the main flight is cheaper", default=False),
    StrategyInfo(id="everywhere", name="Everywhere Explorer", description="Find the cheapest destinations from your city", default=False),
]


@router.post("/api/search", response_model=SearchResponse)
async def search_flights(req: SearchRequest) -> SearchResponse:
    result = await run_search(req)
    return SearchResponse(**result)


@router.get("/api/explore", response_model=ExploreResponse)
async def explore_flights(
    origin: str = Query(...),
    budget: int = Query(500),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    nights_min: int = Query(2),
    nights_max: int = Query(7),
    flight_type: str = Query("round"),
) -> ExploreResponse:
    result = await run_explore(
        origin=origin,
        budget=budget,
        date_from=date_from,
        date_to=date_to,
        nights_min=nights_min,
        nights_max=nights_max,
        flight_type=flight_type,
    )
    return ExploreResponse(**result)


@router.get("/api/locations", response_model=LocationsResponse)
async def get_locations(
    query: str = Query(..., min_length=1),
    limit: int = Query(10),
) -> LocationsResponse:
    results = await search_locations(query, limit=limit)
    return LocationsResponse(results=results)


@router.get("/api/strategies", response_model=StrategiesResponse)
async def get_strategies() -> StrategiesResponse:
    return StrategiesResponse(strategies=STRATEGY_LIST)

from __future__ import annotations
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    origin: str
    destination: str | None = None

    date_mode: str = "range"  # exact, range, month, cheapest, weekends

    date_from: str | None = None
    date_to: str | None = None
    return_from: str | None = None
    return_to: str | None = None

    nights_min: int = 2
    nights_max: int = 7

    month: int | None = None
    year: int | None = None

    months_ahead: int = 3

    weekends_from: str | None = None
    weekends_to: str | None = None

    flight_type: str = "round"
    adults: int = 1
    max_stopovers: int | None = None
    selected_cabins: str = "M"
    max_price: int | None = None

    strategies: list[str] = Field(default_factory=list)


class RouteSegment(BaseModel):
    id: str = ""
    fly_from: str = ""
    fly_to: str = ""
    city_from: str = ""
    city_to: str = ""
    city_code_from: str = ""
    city_code_to: str = ""
    local_departure: str = ""
    local_arrival: str = ""
    airline: str = ""
    flight_no: int = 0
    operating_carrier: str = ""
    return_leg: int = 0
    bags_recheck_required: bool = False
    vi_connection: bool = False
    fare_classes: str = ""


class FlightResult(BaseModel):
    id: str = ""
    fly_from: str = ""
    fly_to: str = ""
    city_from: str = ""
    city_to: str = ""
    city_code_from: str = ""
    city_code_to: str = ""
    country_from: dict = Field(default_factory=dict)
    country_to: dict = Field(default_factory=dict)
    local_departure: str = ""
    local_arrival: str = ""
    utc_departure: str = ""
    utc_arrival: str = ""
    nights_in_dest: int = 0
    quality: float = 0
    distance: float = 0
    duration: dict = Field(default_factory=dict)
    price: int = 0
    conversion: dict = Field(default_factory=dict)
    fare: dict = Field(default_factory=dict)
    bags_price: dict = Field(default_factory=dict)
    baglimit: dict = Field(default_factory=dict)
    availability: dict = Field(default_factory=dict)
    airlines: list[str] = Field(default_factory=list)
    route: list[RouteSegment] = Field(default_factory=list)
    booking_token: str = ""
    deep_link: str = ""
    virtual_interlining: bool = False
    pnr_count: int = 1
    has_airport_change: bool = False
    technical_stops: int = 0
    strategy: str = "standard"
    savings_pct: float | None = None
    savings_vs: int | None = None
    strategy_explanation: str = ""
    ticket_2_deep_link: str = ""
    ticket_2_booking_token: str = ""
    ticket_2_summary: str = ""


class SearchResponse(BaseModel):
    results: list[FlightResult] = Field(default_factory=list)
    total: int = 0
    cheapest: int | None = None
    strategies_used: list[str] = Field(default_factory=list)


class ExploreResult(BaseModel):
    city: str = ""
    city_code: str = ""
    country: str = ""
    country_code: str = ""
    price: int = 0
    local_departure: str = ""
    local_arrival: str = ""
    deep_link: str = ""
    fly_from: str = ""
    fly_to: str = ""
    nights_in_dest: int = 0
    airlines: list[str] = Field(default_factory=list)


class ExploreResponse(BaseModel):
    results: list[ExploreResult] = Field(default_factory=list)
    total: int = 0
    origin: str = ""


class LocationResult(BaseModel):
    id: str = ""
    name: str = ""
    code: str = ""
    city: str = ""
    country: str = ""
    country_code: str = ""
    type: str = ""
    lat: float = 0
    lon: float = 0


class LocationsResponse(BaseModel):
    results: list[LocationResult] = Field(default_factory=list)


class StrategyInfo(BaseModel):
    id: str
    name: str
    description: str
    default: bool = False


class StrategiesResponse(BaseModel):
    strategies: list[StrategyInfo] = Field(default_factory=list)

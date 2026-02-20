from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

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

# In-memory job store for async explore
_explore_jobs: dict[str, dict[str, Any]] = {}

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


# In-memory job store for async search
_search_jobs: dict[str, dict[str, Any]] = {}


async def _run_search_job(job_id: str, req: SearchRequest) -> None:
    try:
        result = await run_search(req)
        _search_jobs[job_id] = {"status": "done", "result": result}
    except Exception as e:
        _search_jobs[job_id] = {"status": "error", "error": str(e)}


@router.post("/api/search")
async def search_flights(req: SearchRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())[:8]
    _search_jobs[job_id] = {"status": "running"}
    asyncio.create_task(_run_search_job(job_id, req))
    return {"job_id": job_id, "status": "running"}


@router.get("/api/search/status/{job_id}")
async def search_status(job_id: str) -> dict[str, Any]:
    job = _search_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    if job["status"] == "done":
        result = job["result"]
        del _search_jobs[job_id]
        return {"status": "done", **result}
    elif job["status"] == "error":
        err = job.get("error", "Unknown error")
        del _search_jobs[job_id]
        return {"status": "error", "error": err}
    return {"status": "running"}


async def _run_explore_job(job_id: str, kwargs: dict[str, Any]) -> None:
    """Background task that runs explore and stores result."""
    try:
        # Pass job store and ID for progress updates
        kwargs["job_store"] = _explore_jobs
        kwargs["job_id"] = job_id
        result = await run_explore(**kwargs)
        _explore_jobs[job_id] = {"status": "done", "result": result}
    except Exception as e:
        _explore_jobs[job_id] = {"status": "error", "error": str(e)}


class ExploreRequest(BaseModel):
    origin: str
    budget: int = 500
    date_from: str | None = None
    date_to: str | None = None
    nights_min: int = 2
    nights_max: int = 7
    flight_type: str = "round"
    continent: str | None = None
    max_duration: float | None = None
    direct_only: bool = False
    sort_by: str = "price"
    strategies: list[str] | None = None
    months: list[str] | None = None  # e.g. ["2026-03", "2026-07"]


@router.post("/api/explore")
async def explore_flights_async(req: ExploreRequest) -> dict[str, str]:
    job_id = str(uuid.uuid4())[:8]
    _explore_jobs[job_id] = {"status": "running"}
    kwargs = req.dict()
    asyncio.create_task(_run_explore_job(job_id, kwargs))
    return {"job_id": job_id, "status": "running"}


@router.get("/api/explore/status/{job_id}")
async def explore_status(job_id: str) -> dict[str, Any]:
    job = _explore_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    
    if job["status"] == "done":
        result = job["result"]
        # Clean up after retrieval
        del _explore_jobs[job_id]
        return {"status": "done", **result}
    elif job["status"] == "running":
        # Return partial results with progress
        return {
            "status": "running",
            "progress": job.get("progress", 0),
            "destinations_searched": job.get("destinations_searched", 0),
            "destinations_total": job.get("destinations_total", 0),
            "current_destination": job.get("current_destination", ""),
            "results": job.get("results", []),
            "total": job.get("total", 0),
        }
    else:
        return {"status": job["status"], "error": job.get("error")}


@router.get("/api/explore", response_model=ExploreResponse)
async def explore_flights(
    origin: str = Query(...),
    budget: int = Query(500),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    nights_min: int = Query(2),
    nights_max: int = Query(7),
    flight_type: str = Query("round"),
    continent: str | None = Query(None),
    max_duration: float | None = Query(None),
    direct_only: bool = Query(False),
    sort_by: str = Query("price"),
    strategies: list[str] = Query([]),
) -> ExploreResponse:
    result = await run_explore(
        origin=origin, budget=budget, date_from=date_from, date_to=date_to,
        nights_min=nights_min, nights_max=nights_max, flight_type=flight_type,
        continent=continent, max_duration=max_duration, direct_only=direct_only,
        sort_by=sort_by, strategies=strategies or None,
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


# ── RataTrip Publications API ─────────────────────────────────────────────

DEALS_DB = Path("/home/ec2-user/.openclaw/workspace/flights-kiwi/deals-engine/deals.db")


@router.get("/api/publications")
async def get_publications(
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
):
    """Paginated list of published deals for ofertas page."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="DB not available")

    conn = sqlite3.connect(str(DEALS_DB))
    conn.row_factory = sqlite3.Row

    offset = (page - 1) * per_page
    rows = conn.execute(
        "SELECT * FROM publications ORDER BY published_at DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
    conn.close()

    publications = []
    for r in rows:
        publications.append({
            "id": r["id"],
            "origin": r["origin"],
            "destination": r["destination"],
            "destination_country": r["destination_country"],
            "price": r["price"],
            "departure_date": r["departure_date"],
            "nights": r["nights"],
            "is_direct": bool(r["is_direct"]),
            "continent": r["continent"],
            "image_url": r["image_url"],
            "slug": r["slug"],
            "blog_url": r["blog_url"],
            "kiwi_link": r["kiwi_link"],
            "telegram_copy": r["telegram_copy"],
            "blog_copy": r["blog_copy"],
            "published_at": r["published_at"],
            "airlines": r["airlines"],
            "duration": r["duration"],
            "strategy": r["strategy"],
            "route_json": r["route_json"],
        })

    return {
        "publications": publications,
        "pagination": {
            "current_page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
        },
    }


@router.get("/api/publications/{slug}")
async def get_publication_by_slug(slug: str):
    """Single publication by slug."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="DB not available")

    conn = sqlite3.connect(str(DEALS_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM publications WHERE slug = ?", (slug,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Publication not found")

    return dict(row)


# ── RataTrip Deals API ────────────────────────────────────────────────────

def _create_deal_slug(origin: str, destination: str, price: int, departure_date: str) -> str:
    """Create URL slug from deal data."""
    origin_clean = origin.lower().replace(" ", "-").replace(",", "")
    destination_clean = destination.lower().replace(" ", "-").replace(",", "")
    
    try:
        date_obj = datetime.fromisoformat(departure_date.replace('T', ' ').replace('Z', ''))
        date_str = date_obj.strftime('%Y-%m-%d')
    except:
        date_str = departure_date.split('T')[0] if 'T' in departure_date else departure_date
    
    return f"{origin_clean}-{destination_clean}-{price}e-{date_str}"


def _get_unsplash_url(city: str, country: str = "") -> str:
    """Generate Unsplash image URL for destination."""
    query = f"{city} {country}".strip().replace(" ", "%20")
    return f"https://images.unsplash.com/photo-1506905925346-21bda4d32df4?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80&city={query}"


@router.get("/api/deals")
async def get_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    continent: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    sort_by: str = Query("price", enum=["price", "savings_pct", "departure_date"])
):
    """Get published deals with pagination and filtering."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Deals database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        # Base query for published deals
        base_query = """
        SELECT 
            id, origin, real_origin_city, destination_city, destination_country,
            price, savings_pct, continent, departure_date, nights_in_dest,
            airlines, route_json, deep_link, strategy, is_direct,
            blog_copy, image_url, slug
        FROM deals 
        WHERE published_telegram = 1
        """
        
        params = []
        conditions = []
        
        # Add filters
        if continent:
            conditions.append("continent = ?")
            params.append(continent.lower())
            
        if min_price is not None:
            conditions.append("price >= ?")
            params.append(min_price)
            
        if max_price is not None:
            conditions.append("price <= ?")
            params.append(max_price)
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # Add sorting
        sort_map = {
            "price": "price ASC",
            "savings_pct": "savings_pct DESC", 
            "departure_date": "departure_date ASC"
        }
        base_query += f" ORDER BY {sort_map.get(sort_by, 'price ASC')}"
        
        # Add pagination
        offset = (page - 1) * limit
        base_query += f" LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = conn.execute(base_query, params)
        deals_raw = cursor.fetchall()
        
        # Get total count for pagination
        count_query = """
        SELECT COUNT(*) as total 
        FROM deals 
        WHERE published_telegram = 1
        """
        count_params = []
        if conditions:
            count_query += " AND " + " AND ".join(conditions)
            count_params = params[:-2]  # Remove limit/offset params
        
        count_cursor = conn.execute(count_query, count_params)
        total_count = count_cursor.fetchone()["total"]
        
        # Process deals
        deals = []
        for row in deals_raw:
            # Parse route_json to get origin city name
            route_data = []
            if row["route_json"]:
                try:
                    route_data = json.loads(row["route_json"])
                except:
                    pass
            
            # Get real origin city from route data or fallback
            real_origin_city = row["real_origin_city"] or row["origin"]
            if route_data and len(route_data) > 0:
                real_origin_city = route_data[0].get("cityFrom", real_origin_city)
            
            # Create deal data
            deal = {
                "id": row["id"],
                "origin": row["origin"],
                "real_origin_city": real_origin_city,
                "destination_city": row["destination_city"],
                "price": row["price"],
                "savings_pct": row["savings_pct"] or 0,
                "continent": row["continent"],
                "departure_date": row["departure_date"],
                "nights_in_dest": row["nights_in_dest"] or 0,
                "airlines": json.loads(row["airlines"]) if row["airlines"] else [],
                "route_json": route_data,
                "image_url": row["image_url"] or _get_unsplash_url(row["destination_city"], row["destination_country"]),
                "deep_link": row["deep_link"],
                "strategy": row["strategy"],
                "short_link": f"https://ratatrip.com/go/{row['id']}",
                "slug": row["slug"] or _create_deal_slug(real_origin_city, row["destination_city"], row["price"], row["departure_date"]),
                "is_direct": bool(row["is_direct"]),
                "blog_copy": row["blog_copy"] or "",
            }
            deals.append(deal)
        
        conn.close()
        
        return {
            "deals": deals,
            "pagination": {
                "current_page": page,
                "per_page": limit,
                "total": total_count,
                "total_pages": (total_count + limit - 1) // limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/deals/{deal_id}")
async def get_deal(deal_id: int):
    """Get single deal with full details."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Deals database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
        SELECT 
            id, origin, real_origin_city, destination_city, destination_code,
            destination_country, price, savings_pct, continent, departure_date, 
            nights_in_dest, airlines, route_json, deep_link, strategy, 
            is_direct, flight_duration_hours
        FROM deals 
        WHERE id = ? AND published_telegram = 1
        """, (deal_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Deal not found")
        
        # Parse route_json
        route_data = []
        if row["route_json"]:
            try:
                route_data = json.loads(row["route_json"])
            except:
                pass
        
        # Get real origin city
        real_origin_city = row["real_origin_city"] or row["origin"]
        if route_data and len(route_data) > 0:
            real_origin_city = route_data[0].get("cityFrom", real_origin_city)
        
        # Create deal data
        deal = {
            "id": row["id"],
            "origin": row["origin"],
            "real_origin_city": real_origin_city,
            "destination_city": row["destination_city"],
            "destination_code": row["destination_code"],
            "destination_country": row["destination_country"],
            "price": row["price"],
            "savings_pct": row["savings_pct"] or 0,
            "continent": row["continent"],
            "departure_date": row["departure_date"],
            "nights_in_dest": row["nights_in_dest"] or 0,
            "airlines": json.loads(row["airlines"]) if row["airlines"] else [],
            "route_json": route_data,
            "image_url": _get_unsplash_url(row["destination_city"], row["destination_country"]),
            "deep_link": row["deep_link"],
            "strategy": row["strategy"],
            "short_link": f"https://ratatrip.com/go/{row['id']}",
            "slug": _create_deal_slug(real_origin_city, row["destination_city"], row["price"], row["departure_date"]),
            "is_direct": bool(row["is_direct"]),
            "flight_duration_hours": row["flight_duration_hours"] or 0
        }
        
        conn.close()
        return deal
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ── RataTrip Link Redirects ──────────────────────────────────────────────

_B62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _decode_b62(s: str) -> int:
    n = 0
    for ch in s:
        n = n * 62 + _B62.index(ch)
    return n


@router.get("/api/deals/by-slug/{slug}")
async def get_deal_by_slug(slug: str):
    """Get deal by URL slug — serves as CMS for blog detail pages."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Deals database not available")

    conn = sqlite3.connect(str(DEALS_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT id, origin, real_origin_city, destination_city, destination_code,
               destination_country, price, savings_pct, continent, departure_date,
               nights_in_dest, airlines, route_json, deep_link, strategy,
               is_direct, flight_duration_hours, blog_copy, image_url, slug
        FROM deals WHERE slug = ? AND published_telegram = 1
    """, (slug,)).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Deal not found")

    route_data = []
    if row["route_json"]:
        try:
            route_data = json.loads(row["route_json"])
        except:
            pass

    real_origin = row["real_origin_city"] or row["origin"]
    if route_data:
        real_origin = route_data[0].get("cityFrom", real_origin)

    deal = {
        "id": row["id"],
        "origin": row["origin"],
        "real_origin_city": real_origin,
        "destination_city": row["destination_city"],
        "destination_code": row["destination_code"],
        "destination_country": row["destination_country"],
        "price": row["price"],
        "savings_pct": row["savings_pct"] or 0,
        "continent": row["continent"],
        "departure_date": row["departure_date"],
        "nights_in_dest": row["nights_in_dest"] or 0,
        "airlines": json.loads(row["airlines"]) if row["airlines"] else [],
        "route_json": route_data,
        "deep_link": row["deep_link"],
        "strategy": row["strategy"],
        "is_direct": bool(row["is_direct"]),
        "flight_duration_hours": row["flight_duration_hours"] or 0,
        "blog_copy": row["blog_copy"] or "",
        "image_url": row["image_url"] or "",
        "slug": row["slug"] or slug,
        "short_link": f"https://ratatrip.com/go/{_encode_b62(row['id'] + 1000)}",
    }
    conn.close()
    return deal


def _encode_b62(num: int) -> str:
    if num == 0:
        return _B62[0]
    result = []
    while num > 0:
        result.append(_B62[num % 62])
        num //= 62
    return "".join(reversed(result))


@router.get("/go/{code}")
async def redirect_deal(code: str):
    """Redirect ratatrip.com/go/{code} to Kiwi affiliate deep link."""
    try:
        deal_id = _decode_b62(code) - 1000
    except (ValueError, IndexError):
        raise HTTPException(status_code=404, detail="Invalid link")

    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Deals DB not available")

    conn = sqlite3.connect(str(DEALS_DB))
    row = conn.execute("SELECT deep_link FROM deals WHERE id = ?", (deal_id,)).fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Deal not found or expired")

    return RedirectResponse(url=row[0], status_code=302)


# ── Newsletter Subscription ──

class SubscribeRequest(BaseModel):
    email: str
    lang: str = "es"
    source: str = "web"

@router.post("/api/subscribe")
async def subscribe(req: SubscribeRequest):
    """Subscribe an email to the RataTrip newsletter."""
    import re
    email = req.email.strip().lower()
    
    # Validate email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(status_code=400, detail="Email inválido")
    
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="DB not available")
    
    conn = sqlite3.connect(str(DEALS_DB))
    try:
        conn.execute(
            "INSERT INTO subscribers (email, lang, source) VALUES (?, ?, ?)",
            (email, req.lang, req.source)
        )
        conn.commit()
        
        # Try Brevo sync if configured
        brevo_key = os.environ.get("BREVO_API_KEY", "")
        if brevo_key:
            try:
                import httpx
                httpx.post(
                    "https://api.brevo.com/v3/contacts",
                    headers={"api-key": brevo_key, "Content-Type": "application/json"},
                    json={
                        "email": email,
                        "listIds": [int(os.environ.get("BREVO_LIST_ID", "2"))],
                        "attributes": {"LANG": req.lang, "SOURCE": req.source},
                        "updateEnabled": True,
                    },
                    timeout=10,
                )
            except Exception:
                pass  # Brevo sync is best-effort
        
        return {"ok": True, "message": "Suscrito correctamente"}
    except sqlite3.IntegrityError:
        conn.close()
        return {"ok": True, "message": "Ya estás suscrito"}
    finally:
        conn.close()


@router.get("/api/subscribers/count")
async def subscriber_count():
    """Get total subscriber count (public, for social proof)."""
    if not DEALS_DB.exists():
        return {"count": 0}
    conn = sqlite3.connect(str(DEALS_DB))
    count = conn.execute("SELECT COUNT(*) FROM subscribers WHERE unsubscribed = 0").fetchone()[0]
    conn.close()
    return {"count": count}

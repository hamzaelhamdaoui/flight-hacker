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
        result = await run_search(req, job_store=_search_jobs, job_id=job_id)
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
    # Running — return partial results
    return {
        "status": "running",
        "current_strategy": job.get("current_strategy", ""),
        "strategies_done": job.get("strategies_done", 0),
        "strategies_total": job.get("strategies_total", 0),
        "progress": job.get("progress", 0),
        "results": job.get("results", []),
        "total": job.get("total", 0),
        "cheapest": job.get("cheapest"),
        "strategies_used": job.get("strategies_used", []),
    }


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


# ── Admin Panel API ──────────────────────────────────────────────────────


class AdminDealUpdate(BaseModel):
    origin: Optional[str] = None
    destination_city: Optional[str] = None
    destination_code: Optional[str] = None
    destination_country: Optional[str] = None
    continent: Optional[str] = None
    price: Optional[int] = None
    departure_date: Optional[str] = None
    nights_in_dest: Optional[int] = None
    airlines: Optional[str] = None
    strategy: Optional[str] = None
    is_direct: Optional[bool] = None
    published_telegram: Optional[bool] = None
    published_twitter: Optional[bool] = None
    published_blog: Optional[bool] = None


class AdminQueueItem(BaseModel):
    deal_id: int
    position: Optional[int] = None
    status: Optional[str] = "pending"
    telegram_copy: Optional[str] = None
    twitter_copy: Optional[str] = None
    blog_copy: Optional[str] = None
    image_url: Optional[str] = None
    image_query: Optional[str] = None
    image_path: Optional[str] = None
    slug: Optional[str] = None


class AdminQueueUpdate(BaseModel):
    position: Optional[int] = None
    status: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    destination_country: Optional[str] = None
    continent: Optional[str] = None
    price: Optional[float] = None
    departure_date: Optional[str] = None
    nights: Optional[int] = None
    is_direct: Optional[bool] = None
    airlines: Optional[str] = None
    duration: Optional[str] = None
    strategy: Optional[str] = None
    route_json: Optional[str] = None
    kiwi_link: Optional[str] = None
    telegram_copy: Optional[str] = None
    twitter_copy: Optional[str] = None
    blog_copy: Optional[str] = None
    image_url: Optional[str] = None
    image_query: Optional[str] = None
    image_path: Optional[str] = None
    slug: Optional[str] = None


class AdminPublishedUpdate(BaseModel):
    telegram_copy: Optional[str] = None
    twitter_copy: Optional[str] = None
    blog_copy: Optional[str] = None


class ReorderItem(BaseModel):
    id: int
    position: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


@router.get("/api/admin/deals")
async def admin_get_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    country: Optional[str] = Query(None),
    continent: Optional[str] = Query(None), 
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    origin: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    is_direct: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("found_at", enum=["id", "origin", "destination_city", "price", "departure_date", "found_at"]),
    order: str = Query("desc", enum=["asc", "desc"]),
):
    """Get deals with pagination and filters for admin panel."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        # Build query
        where_conditions = []
        params = []
        
        if country:
            where_conditions.append("destination_country LIKE ?")
            params.append(f"%{country}%")
            
        if continent:
            where_conditions.append("continent = ?")
            params.append(continent.lower())
            
        if min_price is not None:
            where_conditions.append("price >= ?")
            params.append(min_price)
            
        if max_price is not None:
            where_conditions.append("price <= ?")
            params.append(max_price)
            
        if origin:
            where_conditions.append("origin LIKE ?")
            params.append(f"%{origin}%")
            
        if strategy:
            where_conditions.append("strategy = ?")
            params.append(strategy)
            
        if is_direct is not None:
            where_conditions.append("is_direct = ?")
            params.append(1 if is_direct else 0)
            
        if date_from:
            where_conditions.append("departure_date >= ?")
            params.append(date_from)
            
        if date_to:
            where_conditions.append("departure_date <= ?")
            params.append(date_to)
            
        if search:
            where_conditions.append("(destination_city LIKE ? OR destination_country LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM deals WHERE {where_clause}"
        total = conn.execute(count_query, params).fetchone()[0]
        
        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT id, origin, destination_city, destination_code, destination_country,
                   continent, price, departure_date, nights_in_dest, airlines,
                   strategy, is_direct, found_at, published_telegram, published_twitter, published_blog
            FROM deals 
            WHERE {where_clause}
            ORDER BY {sort} {order.upper()}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        deals = []
        for row in conn.execute(query, params):
            deals.append({
                "id": row["id"],
                "origin": row["origin"],
                "destination": row["destination_city"],
                "destination_code": row["destination_code"],
                "country": row["destination_country"],
                "continent": row["continent"],
                "price": row["price"],
                "departure_date": row["departure_date"],
                "nights": row["nights_in_dest"] or 0,
                "airlines": row["airlines"] or "",
                "strategy": row["strategy"],
                "is_direct": bool(row["is_direct"]),
                "found_at": row["found_at"],
                "published_telegram": bool(row["published_telegram"]),
                "published_twitter": bool(row["published_twitter"]),
                "published_blog": bool(row["published_blog"]),
            })
        
        conn.close()
        
        return {
            "deals": deals,
            "pagination": {
                "current_page": page,
                "per_page": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            },
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/api/admin/deals/{deal_id}")
async def admin_delete_deal(deal_id: int):
    """Delete a deal from admin panel."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if deal exists
        cursor = conn.execute("SELECT id FROM deals WHERE id = ?", (deal_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Deal not found")
        
        # Delete deal
        conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
        conn.commit()
        conn.close()
        
        return {"message": "Deal deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/api/admin/deals/{deal_id}")
async def admin_update_deal(deal_id: int, update_data: AdminDealUpdate):
    """Update a deal from admin panel."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if deal exists
        cursor = conn.execute("SELECT id FROM deals WHERE id = ?", (deal_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Deal not found")
        
        # Build update query
        update_fields = []
        params = []
        
        for field, value in update_data.dict(exclude_unset=True).items():
            if field == "is_direct":
                update_fields.append("is_direct = ?")
                params.append(1 if value else 0)
            elif field in ["published_telegram", "published_twitter", "published_blog"]:
                update_fields.append(f"{field} = ?")
                params.append(1 if value else 0)
            else:
                update_fields.append(f"{field} = ?")
                params.append(value)
        
        if not update_fields:
            conn.close()
            raise HTTPException(status_code=400, detail="No fields to update")
        
        query = f"UPDATE deals SET {', '.join(update_fields)} WHERE id = ?"
        params.append(deal_id)
        
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        return {"message": "Deal updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/admin/queue")
async def admin_get_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, enum=["pending", "ready", "skipped"]),
    country: Optional[str] = Query(None),
    continent: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    origin: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    is_direct: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("position", enum=["id", "position", "origin", "destination", "price", "departure_date", "created_at"]),
    order: str = Query("asc", enum=["asc", "desc"]),
):
    """Get queue items with pagination and filters for admin panel."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        # Build query
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = ?")
            params.append(status)
            
        if country:
            where_conditions.append("destination_country LIKE ?")
            params.append(f"%{country}%")
            
        if continent:
            where_conditions.append("continent = ?")
            params.append(continent.lower())
            
        if min_price is not None:
            where_conditions.append("price >= ?")
            params.append(min_price)
            
        if max_price is not None:
            where_conditions.append("price <= ?")
            params.append(max_price)
            
        if origin:
            where_conditions.append("origin LIKE ?")
            params.append(f"%{origin}%")
            
        if strategy:
            where_conditions.append("strategy = ?")
            params.append(strategy)
            
        if is_direct is not None:
            where_conditions.append("is_direct = ?")
            params.append(1 if is_direct else 0)
            
        if date_from:
            where_conditions.append("departure_date >= ?")
            params.append(date_from)
            
        if date_to:
            where_conditions.append("departure_date <= ?")
            params.append(date_to)
            
        if search:
            where_conditions.append("(destination LIKE ? OR destination_country LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM queue WHERE {where_clause}"
        total = conn.execute(count_query, params).fetchone()[0]
        
        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT id, deal_id, position, status, origin, destination, destination_country,
                   continent, price, departure_date, nights, is_direct, airlines,
                   duration, strategy, telegram_copy, created_at, updated_at
            FROM queue 
            WHERE {where_clause}
            ORDER BY {sort} {order.upper()}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        queue_items = []
        for row in conn.execute(query, params):
            queue_items.append({
                "id": row["id"],
                "deal_id": row["deal_id"],
                "position": row["position"],
                "status": row["status"],
                "origin": row["origin"],
                "destination": row["destination"],
                "country": row["destination_country"],
                "continent": row["continent"],
                "price": row["price"],
                "departure_date": row["departure_date"],
                "nights": row["nights"] or 0,
                "is_direct": bool(row["is_direct"]),
                "airlines": row["airlines"] or "",
                "duration": row["duration"] or "",
                "strategy": row["strategy"],
                "telegram_copy": row["telegram_copy"] or "",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
        
        conn.close()
        
        return {
            "queue": queue_items,
            "pagination": {
                "current_page": page,
                "per_page": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            },
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/api/admin/queue")
async def admin_add_to_queue(queue_item: AdminQueueItem):
    """Add a deal to the publication queue."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        # Check if deal exists
        deal_row = conn.execute("""
            SELECT id, origin, destination_city, destination_country, continent,
                   price, departure_date, nights_in_dest, is_direct, airlines,
                   strategy, deep_link, route_json
            FROM deals WHERE id = ?
        """, (queue_item.deal_id,)).fetchone()
        
        if not deal_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Deal not found")
        
        # Check if deal is already in queue
        existing = conn.execute("SELECT id FROM queue WHERE deal_id = ?", (queue_item.deal_id,)).fetchone()
        if existing:
            conn.close()
            raise HTTPException(status_code=400, detail="Deal already in queue")
        
        # Get next position if not specified
        position = queue_item.position
        if position is None:
            cursor = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM queue")
            position = cursor.fetchone()[0]
        
        # Insert into queue
        conn.execute("""
            INSERT INTO queue (
                deal_id, position, status, origin, destination, destination_country,
                continent, price, departure_date, nights, is_direct, airlines,
                strategy, kiwi_link, route_json, telegram_copy, twitter_copy,
                blog_copy, image_url, image_query, image_path, slug
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            queue_item.deal_id, position, queue_item.status,
            deal_row["origin"], deal_row["destination_city"], deal_row["destination_country"],
            deal_row["continent"], deal_row["price"], deal_row["departure_date"],
            deal_row["nights_in_dest"] or 0, deal_row["is_direct"] or 0, deal_row["airlines"],
            deal_row["strategy"], deal_row["deep_link"], deal_row["route_json"],
            queue_item.telegram_copy, queue_item.twitter_copy, queue_item.blog_copy,
            queue_item.image_url, queue_item.image_query, queue_item.image_path, queue_item.slug
        ))
        
        conn.commit()
        conn.close()
        
        return {"message": "Deal added to queue successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/api/admin/queue/{queue_id}")
async def admin_update_queue(queue_id: int, update_data: AdminQueueUpdate):
    """Update a queue item."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if queue item exists
        cursor = conn.execute("SELECT id FROM queue WHERE id = ?", (queue_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        # Build update query
        update_fields = []
        params = []
        
        for field, value in update_data.dict(exclude_unset=True).items():
            if field == "is_direct":
                update_fields.append("is_direct = ?")
                params.append(1 if value else 0)
            else:
                update_fields.append(f"{field} = ?")
                params.append(value)
        
        # Always update updated_at
        update_fields.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        if len(update_fields) <= 1:  # Only updated_at
            conn.close()
            raise HTTPException(status_code=400, detail="No fields to update")
        
        query = f"UPDATE queue SET {', '.join(update_fields)} WHERE id = ?"
        params.append(queue_id)
        
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        return {"message": "Queue item updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/api/admin/queue/{queue_id}")
async def admin_delete_queue(queue_id: int):
    """Delete a queue item."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if queue item exists
        cursor = conn.execute("SELECT id FROM queue WHERE id = ?", (queue_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        # Delete queue item
        conn.execute("DELETE FROM queue WHERE id = ?", (queue_id,))
        conn.commit()
        conn.close()
        
        return {"message": "Queue item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/api/admin/queue/reorder")
async def admin_reorder_queue(reorder_data: ReorderRequest):
    """Reorder queue items."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Update positions
        for item in reorder_data.items:
            conn.execute(
                "UPDATE queue SET position = ?, updated_at = ? WHERE id = ?",
                (item.position, datetime.utcnow().isoformat(), item.id)
            )
        
        conn.commit()
        conn.close()
        
        return {"message": f"Reordered {len(reorder_data.items)} queue items"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/admin/published")
async def admin_get_published(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    country: Optional[str] = Query(None),
    continent: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    origin: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    is_direct: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("published_at", enum=["id", "origin", "destination", "price", "departure_date", "published_at"]),
    order: str = Query("desc", enum=["asc", "desc"]),
):
    """Get published items with pagination and filters for admin panel."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        conn.row_factory = sqlite3.Row
        
        # Build query
        where_conditions = []
        params = []
        
        if country:
            where_conditions.append("destination_country LIKE ?")
            params.append(f"%{country}%")
            
        if continent:
            where_conditions.append("continent = ?")
            params.append(continent.lower())
            
        if min_price is not None:
            where_conditions.append("price >= ?")
            params.append(min_price)
            
        if max_price is not None:
            where_conditions.append("price <= ?")
            params.append(max_price)
            
        if origin:
            where_conditions.append("origin LIKE ?")
            params.append(f"%{origin}%")
            
        if strategy:
            where_conditions.append("strategy = ?")
            params.append(strategy)
            
        if is_direct is not None:
            where_conditions.append("is_direct = ?")
            params.append(1 if is_direct else 0)
            
        if date_from:
            where_conditions.append("departure_date >= ?")
            params.append(date_from)
            
        if date_to:
            where_conditions.append("departure_date <= ?")
            params.append(date_to)
            
        if search:
            where_conditions.append("(destination LIKE ? OR destination_country LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM published WHERE {where_clause}"
        total = conn.execute(count_query, params).fetchone()[0]
        
        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT id, deal_id, origin, destination, destination_country, continent,
                   price, departure_date, nights, is_direct, airlines, strategy,
                   telegram_copy, twitter_copy, blog_copy, telegram_sent, twitter_sent,
                   published_at
            FROM published 
            WHERE {where_clause}
            ORDER BY {sort} {order.upper()}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        published_items = []
        for row in conn.execute(query, params):
            published_items.append({
                "id": row["id"],
                "deal_id": row["deal_id"],
                "origin": row["origin"],
                "destination": row["destination"],
                "country": row["destination_country"],
                "continent": row["continent"],
                "price": row["price"],
                "departure_date": row["departure_date"],
                "nights": row["nights"] or 0,
                "is_direct": bool(row["is_direct"]),
                "airlines": row["airlines"] or "",
                "strategy": row["strategy"],
                "telegram_copy": row["telegram_copy"] or "",
                "twitter_copy": row["twitter_copy"] or "",
                "blog_copy": row["blog_copy"] or "",
                "telegram_sent": bool(row["telegram_sent"]),
                "twitter_sent": bool(row["twitter_sent"]),
                "published_at": row["published_at"],
            })
        
        conn.close()
        
        return {
            "published": published_items,
            "pagination": {
                "current_page": page,
                "per_page": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            },
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/api/admin/published/{published_id}")
async def admin_update_published(published_id: int, update_data: AdminPublishedUpdate):
    """Update a published item."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if published item exists
        cursor = conn.execute("SELECT id FROM published WHERE id = ?", (published_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Published item not found")
        
        # Build update query
        update_fields = []
        params = []
        
        for field, value in update_data.dict(exclude_unset=True).items():
            update_fields.append(f"{field} = ?")
            params.append(value)
        
        if not update_fields:
            conn.close()
            raise HTTPException(status_code=400, detail="No fields to update")
        
        query = f"UPDATE published SET {', '.join(update_fields)} WHERE id = ?"
        params.append(published_id)
        
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        return {"message": "Published item updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/api/admin/published/{published_id}")
async def admin_delete_published(published_id: int):
    """Delete a published item."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Check if published item exists
        cursor = conn.execute("SELECT id FROM published WHERE id = ?", (published_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Published item not found")
        
        # Delete published item
        conn.execute("DELETE FROM published WHERE id = ?", (published_id,))
        conn.commit()
        conn.close()
        
        return {"message": "Published item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/admin/stats")
async def admin_get_stats():
    """Get admin dashboard statistics."""
    if not DEALS_DB.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        
        # Get counts
        total_deals = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        total_queue = conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
        total_published = conn.execute("SELECT COUNT(*) FROM published").fetchone()[0]
        
        # Deals today
        today = datetime.utcnow().strftime('%Y-%m-%d')
        deals_today = conn.execute(
            "SELECT COUNT(*) FROM deals WHERE DATE(found_at) = ?", (today,)
        ).fetchone()[0]
        
        # Last scan
        last_scan_row = conn.execute(
            "SELECT MAX(found_at) FROM deals"
        ).fetchone()
        last_scan_at = last_scan_row[0] if last_scan_row and last_scan_row[0] else None
        
        # Last publish
        last_publish_row = conn.execute(
            "SELECT MAX(published_at) FROM published"
        ).fetchone()
        last_publish_at = last_publish_row[0] if last_publish_row and last_publish_row[0] else None
        
        conn.close()
        
        return {
            "total_deals": total_deals,
            "total_queue": total_queue,
            "total_published": total_published,
            "deals_today": deals_today,
            "last_scan_at": last_scan_at,
            "last_publish_at": last_publish_at,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


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
        "SELECT * FROM published ORDER BY published_at DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM published").fetchone()[0]
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
    row = conn.execute("SELECT * FROM published WHERE slug = ?", (slug,)).fetchone()
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

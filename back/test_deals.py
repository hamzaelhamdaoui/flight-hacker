#!/usr/bin/env python3

import sqlite3
import json
from datetime import datetime

DEALS_DB = "/home/ec2-user/.openclaw/workspace/flights-kiwi/deals-engine/deals.db"

def test_deals_query():
    """Test querying the deals database directly."""
    if not sqlite3.connect(DEALS_DB):
        print("❌ Cannot connect to deals database")
        return
    
    conn = sqlite3.connect(DEALS_DB)
    conn.row_factory = sqlite3.Row
    
    # Test basic query
    cursor = conn.execute("""
    SELECT 
        id, origin, real_origin_city, destination_city, 
        price, savings_pct, continent, departure_date
    FROM deals 
    WHERE published_telegram = 1
    LIMIT 3
    """)
    
    deals = cursor.fetchall()
    print(f"✅ Found {len(deals)} published deals")
    
    for deal in deals:
        print(f"  - {deal['id']}: {deal['real_origin_city'] or deal['origin']} → {deal['destination_city']} - {deal['price']}€")
    
    conn.close()

if __name__ == "__main__":
    print("🧪 Testing deals database connection...")
    test_deals_query()
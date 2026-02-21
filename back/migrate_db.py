#!/usr/bin/env python3
"""
Database migration script for RataTrip Admin Panel
Creates the new queue table and handles publications table restructuring.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DEALS_DB = Path("/home/ec2-user/.openclaw/workspace/flights-kiwi/deals-engine/deals.db")

def migrate_database():
    """Apply database migrations for admin panel."""
    if not DEALS_DB.exists():
        print(f"❌ Database not found: {DEALS_DB}")
        return False
    
    print(f"🔧 Migrating database: {DEALS_DB}")
    
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        cursor = conn.cursor()
        
        # Check if queue table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue'")
        if cursor.fetchone():
            print("✅ Queue table already exists, skipping creation")
        else:
            print("📋 Creating queue table...")
            cursor.execute('''
                CREATE TABLE queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'ready', 'skipped')),
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    destination_country TEXT,
                    continent TEXT,
                    price REAL NOT NULL,
                    departure_date TEXT,
                    nights INTEGER DEFAULT 0,
                    is_direct INTEGER DEFAULT 0,
                    airlines TEXT,
                    duration TEXT,
                    strategy TEXT,
                    route_json TEXT,
                    kiwi_link TEXT,
                    telegram_copy TEXT,
                    twitter_copy TEXT,
                    blog_copy TEXT,
                    image_url TEXT,
                    image_query TEXT,
                    image_path TEXT,
                    slug TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals(id),
                    UNIQUE(deal_id)
                )
            ''')
            
            # Create index for queue position ordering
            cursor.execute('CREATE INDEX idx_queue_position ON queue(position)')
            cursor.execute('CREATE INDEX idx_queue_status ON queue(status)')
            cursor.execute('CREATE INDEX idx_queue_created ON queue(created_at)')
            
            print("✅ Queue table created successfully")
        
        # Migrate unpublished deals from publications to queue
        print("🔄 Migrating unpublished publications to queue...")
        
        cursor.execute('''
            SELECT id, deal_id, origin, destination, destination_country, continent, 
                   price, departure_date, nights, is_direct, airlines, duration,
                   strategy, route_json, kiwi_link, telegram_copy, twitter_copy,
                   blog_copy, image_url, image_query, image_path, slug
            FROM publications 
            WHERE (telegram_sent = 0 OR twitter_sent = 0) 
              AND deal_id NOT IN (SELECT deal_id FROM queue)
        ''')
        
        unpublished = cursor.fetchall()
        migrated_count = 0
        
        for row in unpublished:
            try:
                # Get next position
                cursor.execute('SELECT COALESCE(MAX(position), 0) + 1 FROM queue')
                next_position = cursor.fetchone()[0]
                
                cursor.execute('''
                    INSERT INTO queue (
                        deal_id, position, status, origin, destination, 
                        destination_country, continent, price, departure_date, 
                        nights, is_direct, airlines, duration, strategy, 
                        route_json, kiwi_link, telegram_copy, twitter_copy,
                        blog_copy, image_url, image_query, image_path, slug
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row[1], next_position, 'ready', row[2], row[3], row[4], row[5],
                    row[6], row[7], row[8], row[9], row[10], row[11], row[12],
                    row[13], row[14], row[15], row[16], row[17], row[18], row[19], row[20], row[21]
                ))
                migrated_count += 1
            except sqlite3.IntegrityError:
                # Deal already in queue, skip
                continue
        
        print(f"✅ Migrated {migrated_count} unpublished deals to queue")
        
        # Check if published table exists, if not rename publications to published
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='published'")
        if not cursor.fetchone():
            print("📋 Renaming publications table to published...")
            cursor.execute('ALTER TABLE publications RENAME TO published')
            print("✅ Table renamed successfully")
        else:
            print("✅ Published table already exists")
        
        conn.commit()
        conn.close()
        
        print("🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

def get_table_stats():
    """Get statistics about the database tables."""
    try:
        conn = sqlite3.connect(str(DEALS_DB))
        cursor = conn.cursor()
        
        # Get row counts
        tables = ['deals', 'queue', 'published']
        stats = {}
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats[table] = "N/A (table doesn't exist)"
        
        conn.close()
        
        print("\n📊 Database Statistics:")
        for table, count in stats.items():
            print(f"  {table}: {count} rows")
        
    except Exception as e:
        print(f"❌ Could not get stats: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting RataTrip Admin Panel database migration...")
    
    # Show current stats
    get_table_stats()
    
    # Run migration
    success = migrate_database()
    
    if success:
        print("\n📊 Final statistics:")
        get_table_stats()
    else:
        print("\n❌ Migration failed!")
        exit(1)
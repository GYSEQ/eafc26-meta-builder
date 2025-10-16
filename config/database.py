"""
MongoDB database configuration and connection management.
"""

import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection settings
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'fut_builder')

# Global MongoDB client and database
_client = None
_db = None


def get_database():
    """
    Get MongoDB database instance.
    Creates connection if it doesn't exist.
    """
    global _client, _db

    if _db is None:
        _client = MongoClient(MONGODB_URI)
        _db = _client[MONGODB_DB_NAME]
        _ensure_indexes()

    return _db


def _ensure_indexes():
    """
    Create all required indexes for collections.
    This runs automatically when getting the database.
    """
    print("Ensuring database indexes...")

    # players collection indexes
    players = _db['players']
    players.create_index('ea_id', unique=True)
    players.create_index('club_ea_id')
    players.create_index('league_ea_id')
    players.create_index('nation_ea_id')

    # NEW: Create indexes for metaratings per position
    # These enable fast queries like: metaratings.ST.score >= 80
    positions = ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF', 'LF', 'RF']
    for position in positions:
        players.create_index(f'metaratings.{position}.score', name=f'idx_meta_{position}')

    # my_club collection indexes
    my_club = _db['my_club']
    my_club.create_index('player_ea_id', unique=True)
    my_club.create_index('untradeable')  # For filtering by tradeable status

    print("All indexes created successfully")


def close_connection():
    """
    Close MongoDB connection.
    Call this when shutting down the application.
    """
    global _client, _db

    if _client:
        _client.close()
        _client = None
        _db = None
        print("MongoDB connection closed")

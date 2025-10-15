"""Flask API for receiving owned player data from userscript."""
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import UpdateOne
from dotenv import load_dotenv

from config.database import get_database

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for userscript requests
CORS(app)

# Get MongoDB database
db = get_database()
my_club_collection = db['my_club']


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    Returns: {"status": "ok"}
    """
    return jsonify({
        'status': 'ok'
    })


@app.route('/api/my-club', methods=['POST'])
def add_players_to_club():
    """
    Receive player IDs from userscript and store in my_club collection.

    Request body:
    {
        "player_ea_ids": [123456, 234567, ...]
    }

    Returns:
    {
        "success": true,
        "count": 150,
        "total_players": 150,
        "message": "Successfully processed 150 players in your club"
    }
    """
    try:
        data = request.get_json()

        if not data or 'player_ea_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing player_ea_ids in request body'
            }), 400

        player_ids = data['player_ea_ids']

        if not isinstance(player_ids, list):
            return jsonify({
                'success': False,
                'error': 'player_ea_ids must be an array'
            }), 400

        # Remove duplicates
        unique_player_ids = list(set(player_ids))

        if not unique_player_ids:
            return jsonify({
                'success': True,
                'count': 0,
                'total_players': 0,
                'message': 'No players to process'
            })

        # Bulk upsert to MongoDB
        operations = [
            UpdateOne(
                {'player_ea_id': player_id},
                {'$set': {'player_ea_id': player_id}},
                upsert=True
            )
            for player_id in unique_player_ids
        ]

        result = my_club_collection.bulk_write(operations, ordered=False)

        # Get total count
        total_players = my_club_collection.count_documents({})

        # Count how many were actually processed (new + existing)
        processed_count = len(unique_player_ids)

        return jsonify({
            'success': True,
            'count': processed_count,
            'total_players': total_players,
            'message': f'Successfully processed {processed_count} players in your club'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/my-club/stats', methods=['GET'])
def get_club_stats():
    """
    Get statistics about owned players.

    Returns:
    {
        "success": true,
        "total_players": 150
    }
    """
    try:
        total_players = my_club_collection.count_documents({})

        return jsonify({
            'success': True,
            'total_players': total_players
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/my-club/clear', methods=['DELETE'])
def clear_club():
    """
    Clear all owned players (testing utility).

    Returns:
    {
        "success": true,
        "deleted_count": 150,
        "message": "Deleted 150 players from your club"
    }
    """
    try:
        result = my_club_collection.delete_many({})
        deleted_count = result.deleted_count

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} players from your club'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def main():
    """Start Flask development server."""
    host = os.getenv('FLASK_HOST', 'localhost')
    port = int(os.getenv('FLASK_PORT', 5000))

    print("=" * 60)
    print("EA FC 26 Squad Builder - Userscript API")
    print("=" * 60)
    print(f"Server running at: http://{host}:{port}")
    print("\nAvailable endpoints:")
    print(f"  GET    http://{host}:{port}/health")
    print(f"  POST   http://{host}:{port}/api/my-club")
    print(f"  GET    http://{host}:{port}/api/my-club/stats")
    print(f"  DELETE http://{host}:{port}/api/my-club/clear")
    print("\nReady to receive player data from userscript!")
    print("=" * 60)
    print()

    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    main()

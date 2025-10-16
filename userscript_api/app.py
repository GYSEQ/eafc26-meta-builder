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
    Receive player data from userscript and store in my_club collection.

    Request body:
    {
        "players": [
            {
                "ea_id": 123456,
                "name": "Cristiano Ronaldo",
                "untradeable": false
            },
            ...
        ]
    }

    Returns:
    {
        "success": true,
        "count": 150,
        "total_players": 150,
        "new_players": 10,
        "updated_players": 140,
        "message": "Successfully processed 150 players in your club"
    }
    """
    try:
        data = request.get_json()

        # Support both old and new format for backward compatibility
        if data and 'players' in data:
            # New format with full player data
            players = data['players']

            if not isinstance(players, list):
                return jsonify({
                    'success': False,
                    'error': 'players must be an array'
                }), 400

            if not players:
                return jsonify({
                    'success': True,
                    'count': 0,
                    'total_players': 0,
                    'new_players': 0,
                    'updated_players': 0,
                    'message': 'No players to process'
                })

            # Validate player objects
            for player in players:
                if not isinstance(player, dict) or 'ea_id' not in player:
                    return jsonify({
                        'success': False,
                        'error': 'Each player must have an ea_id field'
                    }), 400

            # Remove duplicates by ea_id (keep last occurrence)
            unique_players = {player['ea_id']: player for player in players}.values()

            # Bulk upsert to MongoDB
            operations = [
                UpdateOne(
                    {'player_ea_id': player['ea_id']},
                    {
                        '$set': {
                            'player_ea_id': player['ea_id'],
                            'name': player.get('name', 'Unknown Player'),
                            'untradeable': player.get('untradeable', False)
                        },
                        '$setOnInsert': {
                            'acquisition_date': None
                        }
                    },
                    upsert=True
                )
                for player in unique_players
            ]

            result = my_club_collection.bulk_write(operations, ordered=False)

            # Get statistics
            total_players = my_club_collection.count_documents({})
            processed_count = len(unique_players)
            new_players = result.upserted_count
            updated_players = result.modified_count

            return jsonify({
                'success': True,
                'count': processed_count,
                'total_players': total_players,
                'new_players': new_players,
                'updated_players': updated_players,
                'message': f'Successfully processed {processed_count} players in your club'
            })

        elif data and 'player_ea_ids' in data:
            # Old format - maintain backward compatibility
            player_ids = data['player_ea_ids']

            if not isinstance(player_ids, list):
                return jsonify({
                    'success': False,
                    'error': 'player_ea_ids must be an array'
                }), 400

            unique_player_ids = list(set(player_ids))

            if not unique_player_ids:
                return jsonify({
                    'success': True,
                    'count': 0,
                    'total_players': 0,
                    'message': 'No players to process'
                })

            operations = [
                UpdateOne(
                    {'player_ea_id': player_id},
                    {
                        '$set': {
                            'player_ea_id': player_id
                        },
                        '$setOnInsert': {
                            'name': None,
                            'untradeable': None,
                            'acquisition_date': None
                        }
                    },
                    upsert=True
                )
                for player_id in unique_player_ids
            ]

            result = my_club_collection.bulk_write(operations, ordered=False)
            total_players = my_club_collection.count_documents({})
            processed_count = len(unique_player_ids)

            return jsonify({
                'success': True,
                'count': processed_count,
                'total_players': total_players,
                'message': f'Successfully processed {processed_count} players in your club'
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Missing players or player_ea_ids in request body'
            }), 400

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
        "total_players": 150,
        "tradeable_players": 80,
        "untradeable_players": 70
    }
    """
    try:
        total_players = my_club_collection.count_documents({})
        tradeable_players = my_club_collection.count_documents({'untradeable': False})
        untradeable_players = my_club_collection.count_documents({'untradeable': True})

        return jsonify({
            'success': True,
            'total_players': total_players,
            'tradeable_players': tradeable_players,
            'untradeable_players': untradeable_players
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/my-club/value', methods=['GET'])
def get_club_value():
    """
    Calculate total market value of tradeable players.

    Returns:
    {
        "success": true,
        "total_value": 1500000,
        "tradeable_value": 800000,
        "tradeable_count": 50,
        "untradeable_count": 100,
        "players_with_prices": 45,
        "players_without_prices": 5
    }
    """
    try:
        players_collection = db['players']

        # Get all owned tradeable players
        tradeable_owned = list(my_club_collection.find({'untradeable': False}))
        untradeable_owned = list(my_club_collection.find({'untradeable': True}))

        tradeable_ids = [doc['player_ea_id'] for doc in tradeable_owned]

        # Get prices from players collection
        tradeable_players = list(players_collection.find(
            {'ea_id': {'$in': tradeable_ids}},
            {'ea_id': 1, 'name': 1, 'market_price': 1}
        ))

        # Calculate total value
        total_value = 0
        players_with_prices = 0
        players_without_prices = 0

        for player in tradeable_players:
            price = player.get('market_price')
            if price is not None and price > 0:
                total_value += price
                players_with_prices += 1
            else:
                players_without_prices += 1

        return jsonify({
            'success': True,
            'total_value': total_value,
            'tradeable_value': total_value,
            'tradeable_count': len(tradeable_owned),
            'untradeable_count': len(untradeable_owned),
            'players_with_prices': players_with_prices,
            'players_without_prices': players_without_prices
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
    print(f"  GET    http://{host}:{port}/api/my-club/value")
    print(f"  DELETE http://{host}:{port}/api/my-club/clear")
    print("\nReady to receive player data from userscript!")
    print("=" * 60)
    print()

    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    main()

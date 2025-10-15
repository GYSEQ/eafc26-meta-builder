"""Main scraper script for importing players from fut.gg."""
import argparse
import sys
from typing import List, Dict
from tqdm import tqdm
from pymongo import UpdateOne

from config.database import get_database
from scraper.futgg_service import FutGGService


class PlayerScraper:
    """Main scraper orchestrator."""

    def __init__(self):
        self.db = get_database()
        self.service = FutGGService()
        self.players_collection = self.db.players

    def scrape_players(self, max_pages: int = None):
        """
        Scrape players from fut.gg and store in MongoDB.

        Per Migration Guide:
        - Simplified schema (no position fields, only EA IDs)
        - Single best metarating per player
        - Store metarating_position (position code)

        Args:
            max_pages: Maximum number of pages to scrape (None for all)
        """
        print("Starting player scraper...")
        print(f"Max pages: {max_pages if max_pages else 'All'}")

        page = 1
        total_players_processed = 0
        total_players_imported = 0

        # Progress tracking
        pbar = tqdm(desc="Scraping players", unit="page")

        while True:
            if max_pages and page > max_pages:
                break

            # Fetch players page
            response = self.service.fetch_players_page(page)

            if not response:
                print(f"\nNo response at page {page}")
                break

            # Handle both 'data' and 'items' keys for compatibility
            players_data = response.get('data') or response.get('items')

            if not players_data:
                print(f"\nNo more data at page {page}")
                break

            # Parse players
            parsed_players = []
            ea_ids = []

            for raw_player in players_data:
                try:
                    player_data = self.service.parse_player_data(raw_player)
                    parsed_players.append(player_data)
                    ea_ids.append(player_data['ea_id'])
                except Exception as e:
                    # Continue on individual player failures
                    continue

            total_players_processed += len(parsed_players)

            # Fetch metaratings in bulk for all players on this page
            if ea_ids:
                try:
                    meta_response = self.service.fetch_metaratings_bulk(ea_ids)

                    if meta_response:
                        # Handle both 'data' and 'items' response formats
                        meta_items = meta_response.get('data') or meta_response.get('items', [])

                        # Create a mapping of ea_id to (score, position_code)
                        meta_by_id = {}
                        for meta_item in meta_items:
                            ea_id, score, position_code = self.service.parse_metarating(meta_item)
                            if ea_id:
                                meta_by_id[ea_id] = (score, position_code)

                        # Assign metaratings to players
                        for player_data in parsed_players:
                            ea_id = player_data['ea_id']
                            if ea_id in meta_by_id:
                                score, position_code = meta_by_id[ea_id]
                                player_data['metarating'] = score
                                player_data['metarating_position'] = position_code

                except Exception as e:
                    # If bulk fetch fails, continue with 0 metarating
                    print(f"\n  Warning: Failed to fetch metaratings for page {page}: {e}")

            # Bulk upsert to MongoDB
            if parsed_players:
                try:
                    operations = [
                        UpdateOne(
                            {'ea_id': player['ea_id']},
                            {'$set': player},
                            upsert=True
                        )
                        for player in parsed_players
                    ]

                    result = self.players_collection.bulk_write(operations, ordered=False)
                    total_players_imported += result.upserted_count + result.modified_count

                except Exception as e:
                    print(f"\nError storing players in database: {e}")

            pbar.update(1)
            pbar.set_postfix({
                'processed': total_players_processed,
                'imported': total_players_imported
            })

            # Check if there are more pages
            # Simply increment page number - API will return empty when done
            page += 1

        pbar.close()

        print(f"\n✓ Scraping complete!")
        print(f"  Pages processed: {page}")
        print(f"  Players processed: {total_players_processed}")
        print(f"  Players imported/updated: {total_players_imported}")

    def get_stats(self):
        """Print database statistics."""
        total_players = self.players_collection.count_documents({})
        players_with_meta = self.players_collection.count_documents({
            'metarating': {'$gt': 0}
        })

        print("\n=== Database Statistics ===")
        print(f"Total players: {total_players:,}")
        print(f"Players with metaratings: {players_with_meta:,}")

        # Count by metarating_position
        pipeline = [
            {'$match': {'metarating_position': {'$ne': None}}},
            {'$group': {'_id': '$metarating_position', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        position_counts = list(self.players_collection.aggregate(pipeline))

        if position_counts:
            print("\nPlayers by metarating position:")
            for item in position_counts[:15]:
                print(f"  {item['_id']}: {item['count']:,}")

        # Show top rated players
        print("\nTop 10 players by metarating:")
        top_players = self.players_collection.find(
            {'metarating': {'$gt': 0}},
            {'name': 1, 'metarating': 1, 'metarating_position': 1, '_id': 0}
        ).sort('metarating', -1).limit(10)

        for player in top_players:
            print(f"  {player.get('name', 'Unknown'):30} {player.get('metarating', 0):5.1f}  ({player.get('metarating_position', '?')})")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Scrape player data from fut.gg')
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum number of pages to scrape (default: all)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics without scraping'
    )

    args = parser.parse_args()

    scraper = PlayerScraper()

    if args.stats:
        scraper.get_stats()
    else:
        try:
            scraper.scrape_players(max_pages=args.max_pages)
            scraper.get_stats()
        except KeyboardInterrupt:
            print("\n\nScraping interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n\nError during scraping: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()

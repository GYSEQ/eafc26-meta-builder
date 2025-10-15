"""Service for fetching player data from fut.gg API."""
import os
import time
import cloudscraper
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

from utils.position_mappings import POSITION_ID_TO_CODE

load_dotenv()


class FutGGService:
    """Handles API requests to fut.gg."""

    def __init__(self, delay: float = 0.5, max_retries: int = 3):
        """
        Initialize FutGG service.

        Args:
            delay: Delay in seconds between requests (1.5s per migration guide)
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.base_url = os.getenv('FUTGG_API_BASE', 'https://www.fut.gg/api/fut')
        self.delay = delay
        self.max_retries = max_retries

        # Use cloudscraper instead of requests to bypass Cloudflare
        self.session = cloudscraper.create_scraper()

        # Set headers to match browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request with retry logic and exponential backoff.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            JSON response or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                time.sleep(self.delay)
                return response.json()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.delay * (2 ** attempt)  # Exponential backoff
                    print(f"  Retry attempt {attempt + 1} after error: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"  Failed after {self.max_retries} attempts: {e}")
                    return None
        return None

    def fetch_players_page(self, page: int = 1) -> Optional[Dict]:
        """
        Fetch a page of players from the fut.gg API.

        Args:
            page: Page number to fetch

        Returns:
            API response with players data
        """
        url = f"{self.base_url}/players/v2/26/"
        params = {'page': page}
        return self._make_request(url, params)

    def fetch_metaratings_bulk(self, ea_ids: List[int]) -> Optional[Dict]:
        """
        Fetch metaratings for multiple players at once.
        Uses bulk endpoint: /metarank/players/?ids=1,2,3

        Args:
            ea_ids: List of EA player IDs

        Returns:
            API response with metaratings
        """
        if not ea_ids:
            return None

        ids_string = ','.join(map(str, ea_ids))
        url = f"{self.base_url}/metarank/players/"
        params = {'ids': ids_string}
        return self._make_request(url, params)

    def parse_player_data(self, raw_player: Dict) -> Dict:
        """
        Parse raw player data from API into SIMPLIFIED format.

        Per Migration Guide:
        - Only store EA IDs for club/league/nation (no names)
        - No position or alt_positions fields
        - metarating and metarating_position will be added later

        Args:
            raw_player: Raw player data from API

        Returns:
            Parsed player data dictionary (simplified schema)
        """
        # Extract nation data
        nation = raw_player.get('nation', {})
        nation_ea_id = nation.get('eaId', 0) if nation else 0

        # Extract league data
        league = raw_player.get('league', {})
        league_ea_id = league.get('eaId', 0) if league else 0

        # Extract club data
        club = raw_player.get('club') or raw_player.get('uniqueClub', {})
        club_ea_id = club.get('eaId', 0) if club else 0

        return {
            'ea_id': raw_player.get('eaId', 0),
            'name': raw_player.get('commonName', ''),
            'club_ea_id': club_ea_id,
            'nation_ea_id': nation_ea_id,
            'league_ea_id': league_ea_id,
            'market_price': raw_player.get('price', 0),
            'metarating': 0.0,  # Will be updated with actual metarating
            'metarating_position': None,  # Will be updated with position code
            'is_icon': raw_player.get('isIcon', False),
            'is_hero': raw_player.get('isHero', False),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }

    def parse_metarating(self, meta_item: Dict) -> tuple[int, float, Optional[str]]:
        """
        Parse metarating data from API response.

        Per Migration Guide:
        - API returns the BEST metarating score automatically
        - Extract: eaId, score, and position (as position code)

        Args:
            meta_item: Single metarating item from API response

        Returns:
            Tuple of (ea_id, score, position_code)
        """
        ea_id = meta_item.get('eaId') or meta_item.get('playerId')
        score = float(meta_item.get('score', 0))

        # Convert position ID to position code
        position_id = meta_item.get('position')
        position_code = POSITION_ID_TO_CODE.get(position_id) if position_id is not None else None

        return ea_id, score, position_code

"""Service for fetching player data from fut.gg API."""
import os
import time
import asyncio
import cloudscraper
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

from utils.position_mappings import POSITION_ID_TO_CODE
from role_position_mapping import ROLE_TO_POSITION

load_dotenv()


class FutGGService:
    """Handles API requests to fut.gg."""

    def __init__(self, delay: float = 0.5, max_retries: int = 3, max_concurrent: int = 10):
        """
        Initialize FutGG service.

        Args:
            delay: Delay in seconds between requests
            max_retries: Maximum number of retry attempts for failed requests
            max_concurrent: Maximum concurrent async requests
        """
        self.base_url = os.getenv('FUTGG_API_BASE', 'https://www.fut.gg/api/fut')
        self.delay = delay
        self.max_retries = max_retries
        self.max_concurrent = max_concurrent

        # Use cloudscraper instead of requests to bypass Cloudflare
        self.session = cloudscraper.create_scraper()

        # Set headers to match browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

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
        Parse raw player data from API.

        Now includes position and alt_positions to filter metaratings.

        Args:
            raw_player: Raw player data from API

        Returns:
            Parsed player data dictionary
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

        # Extract position and alternative positions
        position_id = raw_player.get('positionId')
        position = POSITION_ID_TO_CODE.get(position_id) if position_id is not None else None

        # Convert alternative position IDs to codes
        alt_position_ids = raw_player.get('alternativePositionIds', [])
        alt_positions = []
        if alt_position_ids:
            for alt_id in alt_position_ids:
                alt_pos = POSITION_ID_TO_CODE.get(alt_id)
                if alt_pos:
                    alt_positions.append(alt_pos)

        # Combine main position and alt positions
        all_positions = []
        if position:
            all_positions.append(position)
        all_positions.extend(alt_positions)

        return {
            'ea_id': raw_player.get('eaId', 0),
            'name': raw_player.get('commonName', ''),
            'club_ea_id': club_ea_id,
            'nation_ea_id': nation_ea_id,
            'league_ea_id': league_ea_id,
            'market_price': raw_player.get('price', 0),
            'position': position,  # Main position
            'alt_positions': alt_positions,  # Alternative positions
            'all_positions': all_positions,  # For filtering metaratings
            'is_icon': raw_player.get('isIcon', False),
            'is_hero': raw_player.get('isHero', False),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }

    def fetch_metarating_single(self, ea_id: int) -> Optional[Dict]:
        """
        Fetch ALL metaratings for a single player.
        Uses endpoint: /metarank/player/{ea_id}/

        Args:
            ea_id: EA player ID

        Returns:
            API response with all role metaratings
        """
        if not ea_id:
            return None

        url = f"{self.base_url}/metarank/player/{ea_id}/"
        return self._make_request(url, params=None)

    async def fetch_metaratings_async(self, players_data: List[Dict]) -> Dict[int, Dict]:
        """
        Fetch metaratings for multiple players asynchronously.

        NEW: Takes full player data to filter by allowed positions.

        Args:
            players_data: List of player dicts with 'ea_id' and 'all_positions'

        Returns:
            Dictionary mapping ea_id to metaratings dict
        """
        loop = asyncio.get_event_loop()

        async def fetch_one(player_data: Dict) -> tuple[int, Optional[Dict], List[str]]:
            """Fetch single player metarating in thread pool."""
            ea_id = player_data['ea_id']
            allowed_positions = player_data.get('all_positions', [])

            result = await loop.run_in_executor(
                self.executor,
                self.fetch_metarating_single,
                ea_id
            )
            return ea_id, result, allowed_positions

        # Fetch all players concurrently with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(player_data: Dict):
            async with semaphore:
                return await fetch_one(player_data)

        tasks = [fetch_with_semaphore(player_data) for player_data in players_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse results
        metaratings_by_id = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            ea_id, meta_response, allowed_positions = result
            if meta_response and 'data' in meta_response:
                # Pass allowed positions to filter metaratings
                parsed = self.parse_metaratings_response(meta_response['data'], allowed_positions)
                if parsed:
                    metaratings_by_id[ea_id] = parsed

        return metaratings_by_id

    def parse_metaratings_response(self, data: Dict, allowed_positions: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Parse metarating response to extract highest score per position.

        NEW: Only includes positions the player can actually play.

        Response format:
        {
            "eaId": 50520215,
            "scores": [
                {"role": 66, "chemistryStyle": 1, "score": 80.8, ...},
                {"role": 65, "chemistryStyle": 1, "score": 83.7, ...},
                ...
            ]
        }

        Returns:
        {
            "ST": {"score": 84.8},
            "CF": {"score": 84.2},
            ...
        }

        Args:
            data: API response data
            allowed_positions: List of positions player can play (main + alt positions)

        Returns:
            Dictionary of position -> {score} or None
        """
        scores = data.get('scores', [])
        if not scores:
            return None

        # Group by position, keep highest score per position
        position_scores = {}

        for score_item in scores:
            role_id = score_item.get('role')
            score = score_item.get('score')

            if role_id is None or score is None:
                continue

            # Map role ID to position code
            position = ROLE_TO_POSITION.get(role_id)
            if not position:
                continue

            # NEW: Filter by allowed positions
            if allowed_positions and position not in allowed_positions:
                continue

            # Keep highest score for this position
            if position not in position_scores or score > position_scores[position]['score']:
                position_scores[position] = {'score': float(score)}

        return position_scores if position_scores else None

    def parse_metarating(self, meta_item: Dict) -> tuple[int, float, Optional[str]]:
        """
        DEPRECATED: Legacy method for backward compatibility.

        Parse metarating data from API response.

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

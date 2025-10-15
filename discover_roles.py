"""Scraper to discover and map all FIFA roles to positions."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import json
from collections import defaultdict, Counter
from typing import Dict, Set, List, Tuple
from tqdm import tqdm
import cloudscraper

from utils.position_mappings import get_position_code


class RoleDiscoveryScraper:
    """Scraper to discover all role-to-position mappings from fut.gg."""

    def __init__(self, delay: float = 0.5, max_retries: int = 3, top_n_roles: int = 3):
        """
        Initialize role discovery scraper.
        
        Args:
            delay: Delay in seconds between requests
            max_retries: Maximum number of retry attempts
            top_n_roles: Only consider top N highest scoring roles per player (default: 3)
        """
        self.base_url = 'https://www.fut.gg/api/fut'
        self.delay = delay
        self.max_retries = max_retries
        self.top_n_roles = top_n_roles
        
        # Use cloudscraper to bypass Cloudflare
        self.session = cloudscraper.create_scraper()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        
        # Storage for discovered mappings
        self.role_position_counts: Dict[int, Counter] = defaultdict(Counter)  # role -> {position: count}
        self.role_primary_positions: Dict[int, Dict] = {}  # role -> best match data
        self.role_examples: Dict[int, List[Dict]] = defaultdict(list)
        
        # Track which roles appear with Plus++ (indicating primary position match)
        self.role_plusplus_positions: Dict[int, Counter] = defaultdict(Counter)
        
        # Track processed players
        self.processed_ea_ids: Set[int] = set()
        
        # Statistics
        self.total_roles_analyzed = 0
        self.roles_filtered_out = 0

    def _make_request(self, url: str, params: Dict = None) -> Dict:
        """Make HTTP request with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                time.sleep(self.delay)
                return response.json()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.delay * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    raise e
        return None

    def fetch_players_page(self, page: int) -> Dict:
        """Fetch a page of players."""
        url = f"{self.base_url}/players/v2/26/"
        params = {'page': page}
        return self._make_request(url, params)

    def fetch_metarank(self, ea_id: int) -> Dict:
        """Fetch metarank data for a single player."""
        url = f"{self.base_url}/metarank/player/{ea_id}/"
        return self._make_request(url)

    def get_top_n_roles(self, scores: List[Dict]) -> List[Dict]:
        """
        Get only the top N highest scoring roles for a player.
        
        Args:
            scores: List of score entries from metarank API
            
        Returns:
            List of top N score entries sorted by score (descending)
        """
        # Sort by score descending
        sorted_scores = sorted(scores, key=lambda x: x.get('score', 0), reverse=True)
        
        # Return top N
        return sorted_scores[:self.top_n_roles]

    def analyze_player(self, ea_id: int, position_id: int, player_name: str) -> bool:
        """
        Analyze a single player's metarank data to extract roles.
        Only considers the top N highest scoring roles.
        """
        if ea_id in self.processed_ea_ids:
            return False
            
        try:
            metarank_data = self.fetch_metarank(ea_id)
            
            if not metarank_data or 'data' not in metarank_data:
                return False
            
            scores = metarank_data['data'].get('scores', [])
            
            if not scores:
                return False
            
            position = get_position_code(position_id)
            
            # Get only top N roles
            top_roles = self.get_top_n_roles(scores)
            
            # Track filtering
            self.total_roles_analyzed += len(top_roles)
            self.roles_filtered_out += (len(scores) - len(top_roles))
            
            # Process only the top N role entries
            for score_entry in top_roles:
                role = score_entry.get('role')
                if role is None:
                    continue
                
                score = score_entry.get('score', 0)
                rank = score_entry.get('rank', 0)
                is_plus = score_entry.get('isPlus', False)
                is_plusplus = score_entry.get('isPlusPlus', False)
                chem_style = score_entry.get('chemistryStyle')
                
                # Count occurrences of role with this position
                self.role_position_counts[role][position] += 1
                
                # Track Plus++ occurrences (strong signal for primary position)
                if is_plusplus:
                    self.role_plusplus_positions[role][position] += 1
                
                # Store example (limit to 3 per role)
                if len(self.role_examples[role]) < 3:
                    self.role_examples[role].append({
                        'ea_id': ea_id,
                        'name': player_name,
                        'position': position,
                        'score': score,
                        'rank': rank,
                        'is_plus': is_plus,
                        'is_plusplus': is_plusplus,
                        'chem_style': chem_style
                    })
            
            self.processed_ea_ids.add(ea_id)
            return True
            
        except Exception as e:
            print(f"\n✗ Error analyzing player {ea_id}: {e}")
            return False

    def determine_primary_positions(self):
        """Determine the primary position for each role based on Plus++ frequency."""
        print("\n" + "="*80)
        print("Determining primary positions for each role...")
        print("="*80 + "\n")
        
        for role in sorted(self.role_position_counts.keys()):
            # First priority: Plus++ occurrences (strongest signal)
            plusplus_counts = self.role_plusplus_positions.get(role, Counter())
            
            if plusplus_counts:
                # Use position with most Plus++ occurrences
                primary_position = plusplus_counts.most_common(1)[0][0]
                confidence = "HIGH (Plus++ match)"
            else:
                # Fallback: Use position with most occurrences
                primary_position = self.role_position_counts[role].most_common(1)[0][0]
                confidence = "MEDIUM (frequency-based)"
            
            total_occurrences = sum(self.role_position_counts[role].values())
            primary_count = self.role_position_counts[role][primary_position]
            percentage = (primary_count / total_occurrences * 100) if total_occurrences > 0 else 0
            
            self.role_primary_positions[role] = {
                'position': primary_position,
                'confidence': confidence,
                'occurrences': primary_count,
                'total_occurrences': total_occurrences,
                'percentage': percentage,
                'all_positions': dict(self.role_position_counts[role]),
                'plusplus_positions': dict(plusplus_counts)
            }

    def scrape_roles(self, max_pages: int = None, sample_rate: float = 1.0):
        """Scrape roles from fut.gg by analyzing players across multiple pages."""
        print("Starting role discovery scraper...")
        print(f"Top N roles per player: {self.top_n_roles}")
        print(f"Sample rate: {sample_rate * 100:.0f}%")
        print(f"Max pages: {max_pages if max_pages else 'All'}\n")
        
        page = 1
        total_players = 0
        analyzed_players = 0
        
        pbar = tqdm(desc="Discovering roles", unit="player")
        
        while True:
            if max_pages and page > max_pages:
                break
            
            try:
                response = self.fetch_players_page(page)
                
                if not response:
                    print(f"\n✗ No response at page {page}")
                    break
                
                players_data = response.get('data', [])
                
                if not players_data:
                    print(f"\n✓ No more data at page {page}")
                    break
                
                for raw_player in players_data:
                    total_players += 1
                    
                    if sample_rate < 1.0:
                        import random
                        if random.random() > sample_rate:
                            continue
                    
                    ea_id = raw_player.get('eaId', 0)
                    position_id = raw_player.get('positionId', -1)
                    player_name = raw_player.get('commonName') or raw_player.get('lastName', 'Unknown')
                    
                    if ea_id and position_id >= 0:
                        if self.analyze_player(ea_id, position_id, player_name):
                            analyzed_players += 1
                            pbar.update(1)
                            pbar.set_postfix({
                                'page': page,
                                'analyzed': analyzed_players,
                                'roles': len(self.role_position_counts)
                            })
                
                has_next = response.get('next') or response.get('pagination', {}).get('hasNext', False)
                if not has_next:
                    break
                
                page += 1
                
            except KeyboardInterrupt:
                print("\n\n⚠ Scraping interrupted by user")
                break
            except Exception as e:
                print(f"\n✗ Error on page {page}: {e}")
                break
        
        pbar.close()
        
        # Determine primary positions after scraping
        self.determine_primary_positions()
        
        print(f"\n{'='*60}")
        print(f"Scraping complete!")
        print(f"  Pages processed: {page}")
        print(f"  Total players seen: {total_players}")
        print(f"  Players analyzed: {analyzed_players}")
        print(f"  Total roles analyzed: {self.total_roles_analyzed}")
        print(f"  Roles filtered out: {self.roles_filtered_out}")
        print(f"  Unique roles discovered: {len(self.role_primary_positions)}")
        print(f"{'='*60}\n")

    def print_role_mapping(self):
        """Print detailed role-to-position mapping."""
        print("\n" + "="*80)
        print(f"ROLE TO PRIMARY POSITION MAPPING (Top {self.top_n_roles} roles per player)")
        print("="*80 + "\n")
        
        for role in sorted(self.role_primary_positions.keys()):
            data = self.role_primary_positions[role]
            
            print(f"┌─ Role {role}: {data['position']}")
            print(f"│  Confidence: {data['confidence']}")
            print(f"│  Primary position occurrences: {data['occurrences']}/{data['total_occurrences']} ({data['percentage']:.1f}%)")
            
            # Show Plus++ positions if available
            if data['plusplus_positions']:
                plusplus_str = ', '.join(f"{pos}({count})" for pos, count in data['plusplus_positions'].items())
                print(f"│  Plus++ positions: {plusplus_str}")
            
            # Show all positions where this role appears
            if len(data['all_positions']) > 1:
                other_positions = {k: v for k, v in data['all_positions'].items() if k != data['position']}
                if other_positions:
                    others_str = ', '.join(f"{pos}({count})" for pos, count in sorted(other_positions.items(), key=lambda x: -x[1]))
                    print(f"│  Also appears in: {others_str}")
            
            print(f"│")
            
            # Show examples
            examples = self.role_examples[role][:2]
            print(f"│  Examples:")
            for ex in examples:
                plus_marker = " [++]" if ex['is_plusplus'] else " [+]" if ex['is_plus'] else ""
                print(f"│    • {ex['name']} ({ex['position']}) - Score: {ex['score']:.1f}{plus_marker}")
            print(f"└─\n")

    def export_python_dict(self, filename: str = 'role_mappings.py'):
        """Export as Python dictionary with ONE position per role."""
        lines = [
            '"""Auto-generated role to position mappings from fut.gg."""',
            f'# Generated using top {self.top_n_roles} highest scoring roles per player',
            '# Each role maps to ONE primary position based on Plus++ matches and frequency',
            '',
            '# Role ID to Primary Position mapping',
            'ROLE_TO_POSITION = {'
        ]
        
        for role in sorted(self.role_primary_positions.keys()):
            position = self.role_primary_positions[role]['position']
            confidence = self.role_primary_positions[role]['confidence']
            percentage = self.role_primary_positions[role]['percentage']
            lines.append(f"    {role}: '{position}',  # {confidence}, {percentage:.1f}% match")
        
        lines.append('}')
        lines.append('')
        lines.append('# Position to Role IDs mapping (reverse)')
        lines.append('POSITION_TO_ROLES = {')
        
        # Create reverse mapping
        position_to_roles = defaultdict(list)
        for role, data in self.role_primary_positions.items():
            position_to_roles[data['position']].append(role)
        
        for position in sorted(position_to_roles.keys()):
            roles = sorted(position_to_roles[position])
            roles_str = ', '.join(str(r) for r in roles)
            lines.append(f"    '{position}': [{roles_str}],")
        
        lines.append('}')
        lines.append('')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"✓ Python mappings exported to {filename}")

    def export_mapping(self, filename: str = 'role_position_mapping.json'):
        """Export detailed mapping to JSON."""
        mapping = {
            'metadata': {
                'total_roles': len(self.role_primary_positions),
                'total_players_analyzed': len(self.processed_ea_ids),
                'top_n_roles': self.top_n_roles,
                'total_roles_analyzed': self.total_roles_analyzed,
                'roles_filtered_out': self.roles_filtered_out,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'roles': {}
        }
        
        for role, data in self.role_primary_positions.items():
            mapping['roles'][str(role)] = {
                'primary_position': data['position'],
                'confidence': data['confidence'],
                'occurrences': data['occurrences'],
                'total_occurrences': data['total_occurrences'],
                'percentage': round(data['percentage'], 2),
                'all_positions': data['all_positions'],
                'plusplus_positions': data['plusplus_positions'],
                'examples': self.role_examples[role][:3]
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Detailed mapping exported to {filename}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover FIFA role-to-position mappings')
    parser.add_argument('--max-pages', type=int, default=None, help='Maximum pages to scrape')
    parser.add_argument('--sample-rate', type=float, default=1.0, help='Fraction of players to analyze (0.0-1.0)')
    parser.add_argument('--top-n', type=int, default=3, help='Only use top N highest scoring roles per player (default: 3)')
    parser.add_argument('--output', type=str, default='role_position_mapping', help='Output filename prefix')
    
    args = parser.parse_args()
    
    if not 0.0 < args.sample_rate <= 1.0:
        print("Error: sample-rate must be between 0.0 and 1.0")
        return
    
    if args.top_n < 1:
        print("Error: top-n must be at least 1")
        return
    
    scraper = RoleDiscoveryScraper(top_n_roles=args.top_n)
    
    try:
        scraper.scrape_roles(max_pages=args.max_pages, sample_rate=args.sample_rate)
        scraper.print_role_mapping()
        scraper.export_mapping(f'{args.output}.json')
        scraper.export_python_dict(f'{args.output}.py')
        
        print("\n✓ Role discovery complete!")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        scraper.determine_primary_positions()
        scraper.print_role_mapping()
        scraper.export_mapping(f'{args.output}_partial.json')
        scraper.export_python_dict(f'{args.output}_partial.py')


if __name__ == '__main__':
    main()
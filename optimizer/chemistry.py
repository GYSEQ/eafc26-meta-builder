"""
EA FC 26 Chemistry Calculation - Squad-Threshold System

Chemistry is based on how many teammates share the same club/league/nation.
Icons and Heroes get special bonuses and count double toward certain thresholds.

Rules:
- Players earn chemistry based on teammate counts (not individual links)
- Icons: Full chemistry + count double for nationality thresholds
- Heroes: Full chemistry + count double for league thresholds
- Max chemistry per player: 3 points
- Max squad chemistry: 33 points (11 players × 3)
"""

from typing import List, Dict, Optional


class ChemistryCalculator:
    """
    Calculates chemistry for EA FC 26 squads using the squad-threshold system.
    """

    # Chemistry thresholds based on teammate counts
    THRESHOLDS = {
        'club': {
            2: 1,   # 2 players same club = +1 chemistry
            4: 2,   # 4 players same club = +2 chemistry
            7: 3,   # 7 players same club = +3 chemistry
        },
        'league': {
            3: 1,   # 3 players same league = +1 chemistry
            5: 2,   # 5 players same league = +2 chemistry
            8: 3,   # 8 players same league = +3 chemistry
        },
        'nation': {
            2: 1,   # 2 players same nation = +1 chemistry
            5: 2,   # 5 players same nation = +2 chemistry
            8: 3,   # 8 players same nation = +3 chemistry
        }
    }

    def __init__(self):
        """Initialize chemistry calculator."""
        pass

    def count_teammates(self, squad: List[Dict], attribute: str, target_value: int,
                        count_double_for: Optional[str] = None) -> int:
        """
        Count how many teammates share the same attribute value.

        Args:
            squad: List of player dictionaries
            attribute: Attribute to check (e.g., 'club_ea_id', 'league_ea_id', 'nation_ea_id')
            target_value: The value to match
            count_double_for: Special card type that counts double ('is_icon' or 'is_hero')

        Returns:
            Count of teammates with matching attribute (including double counting)
        """
        count = 0

        for player in squad:
            if player.get(attribute) == target_value:
                # Check if this card type counts double
                if count_double_for and player.get(count_double_for, False):
                    count += 2  # Icons/Heroes count double
                else:
                    count += 1

        return count

    def get_chemistry_from_threshold(self, count: int, thresholds: Dict[int, int]) -> int:
        """
        Convert teammate count to chemistry points based on thresholds.

        Args:
            count: Number of teammates
            thresholds: Dictionary mapping count -> chemistry points

        Returns:
            Chemistry points (0-3)
        """
        chemistry = 0

        for threshold, points in sorted(thresholds.items()):
            if count >= threshold:
                chemistry = points
            else:
                break

        return chemistry

    def calculate_player_chemistry(self, player: Dict, squad: List[Dict]) -> int:
        """
        Calculate chemistry for a single player based on squad composition.

        Per EA FC 26 rules:
        - Count teammates with same club (Heroes count double for this)
        - Count teammates with same league (Heroes count double for this)
        - Count teammates with same nation (Icons count double for this)
        - Apply thresholds to get chemistry points
        - Chemistry points from different sources stack
        - Max 3 chemistry per player

        Args:
            player: Player dictionary with club_ea_id, league_ea_id, nation_ea_id, is_icon, is_hero
            squad: List of all 11 players in the squad

        Returns:
            Chemistry value (0-3)
        """
        # Icons and Heroes get full chemistry automatically
        if player.get('is_icon') or player.get('is_hero'):
            return 3

        chemistry = 0

        # Club chemistry (no special counting)
        club_count = self.count_teammates(squad, 'club_ea_id', player.get('club_ea_id'))
        club_chem = self.get_chemistry_from_threshold(club_count, self.THRESHOLDS['club'])
        chemistry += club_chem

        # League chemistry (Heroes count double)
        league_count = self.count_teammates(
            squad, 'league_ea_id', player.get('league_ea_id'),
            count_double_for='is_hero'
        )
        league_chem = self.get_chemistry_from_threshold(league_count, self.THRESHOLDS['league'])
        chemistry += league_chem

        # Nation chemistry (Icons count double)
        nation_count = self.count_teammates(
            squad, 'nation_ea_id', player.get('nation_ea_id'),
            count_double_for='is_icon'
        )
        nation_chem = self.get_chemistry_from_threshold(nation_count, self.THRESHOLDS['nation'])
        chemistry += nation_chem

        # Cap at maximum 3 chemistry
        return min(chemistry, 3)

    def calculate_squad_chemistry(self, squad: List[Dict]) -> int:
        """
        Calculate total squad chemistry (sum of all player chemistries).

        Args:
            squad: List of 11 player dictionaries

        Returns:
            Total squad chemistry (0-33)
        """
        if not squad or len(squad) != 11:
            return 0

        total_chemistry = 0

        for player in squad:
            player_chem = self.calculate_player_chemistry(player, squad)
            total_chemistry += player_chem

        return total_chemistry

    def get_chemistry_breakdown(self, squad: List[Dict]) -> Dict:
        """
        Get detailed chemistry breakdown for debugging and display.

        Args:
            squad: List of 11 player dictionaries

        Returns:
            Dictionary with detailed chemistry information per player
        """
        breakdown = {
            'total_chemistry': 0,
            'max_chemistry': 33,
            'players': []
        }

        for i, player in enumerate(squad, 1):
            # Calculate chemistry
            player_chem = self.calculate_player_chemistry(player, squad)

            # Get counts for display
            club_count = self.count_teammates(squad, 'club_ea_id', player.get('club_ea_id'))
            league_count = self.count_teammates(
                squad, 'league_ea_id', player.get('league_ea_id'),
                count_double_for='is_hero'
            )
            nation_count = self.count_teammates(
                squad, 'nation_ea_id', player.get('nation_ea_id'),
                count_double_for='is_icon'
            )

            # Get chemistry from each source
            club_chem = self.get_chemistry_from_threshold(club_count, self.THRESHOLDS['club'])
            league_chem = self.get_chemistry_from_threshold(league_count, self.THRESHOLDS['league'])
            nation_chem = self.get_chemistry_from_threshold(nation_count, self.THRESHOLDS['nation'])

            player_info = {
                'position': i,
                'name': player.get('name', 'Unknown'),
                'chemistry': player_chem,
                'is_icon': player.get('is_icon', False),
                'is_hero': player.get('is_hero', False),
                'club_count': club_count,
                'club_chemistry': club_chem,
                'league_count': league_count,
                'league_chemistry': league_chem,
                'nation_count': nation_count,
                'nation_chemistry': nation_chem,
            }

            breakdown['players'].append(player_info)
            breakdown['total_chemistry'] += player_chem

        return breakdown


# Convenience functions for easy import
def calculate_squad_chemistry(squad: List[Dict]) -> int:
    """
    Calculate total squad chemistry.

    Args:
        squad: List of 11 player dictionaries

    Returns:
        Total chemistry (0-33)
    """
    calculator = ChemistryCalculator()
    return calculator.calculate_squad_chemistry(squad)


def get_chemistry_breakdown(squad: List[Dict]) -> Dict:
    """
    Get detailed chemistry breakdown.

    Args:
        squad: List of 11 player dictionaries

    Returns:
        Dictionary with detailed breakdown
    """
    calculator = ChemistryCalculator()
    return calculator.get_chemistry_breakdown(squad)

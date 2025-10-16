"""
Squad optimization using Google OR-Tools CP-SAT with chemistry as HARD constraint.
"""

import time
from typing import List, Dict, Set, Optional
from ortools.sat.python import cp_model

from config.database import get_database
from optimizer.chemistry import ChemistryCalculator


class SquadOptimizer:
    """
    Optimizes squad selection using CP-SAT with chemistry as hard constraint.
    """

    def __init__(self, timeout: int = 300):
        """
        Initialize optimizer.

        Args:
            timeout: Solver timeout in seconds (default: 5 minutes for complex chemistry)
        """
        self.db = get_database()
        self.timeout = timeout
        self.chemistry_calc = ChemistryCalculator()

    def get_owned_player_ids(self) -> Set[int]:
        """Get set of owned player EA IDs."""
        my_club = self.db['my_club']
        owned = my_club.find({}, {'player_ea_id': 1})
        return set(doc['player_ea_id'] for doc in owned)

    def get_candidates_for_position(self, position: str, owned_player_ids: Set[int],
                                     owned_only: bool = False, limit: int = 200,
                                     min_metarating: float = 0.0,
                                     include_players: Optional[Set[int]] = None) -> List[Dict]:
        """
        Get eligible player candidates for a position.

        NEW: Uses metaratings.{position}.score field

        Args:
            position: Position code (e.g., 'ST', 'CM')
            owned_player_ids: Set of owned player IDs
            owned_only: Only return owned players
            limit: Maximum number of candidates (optimization: lower = faster)
            min_metarating: Minimum metarating threshold (optimization: higher = faster)
            include_players: Set of player IDs that must be included regardless of filters
        """
        players = self.db['players']
        include_players = include_players or set()

        # Build query - must have metarating for this specific position
        base_query = {
            f'metaratings.{position}.score': {'$gte': max(min_metarating, 0.01)}
        }

        if owned_only:
            base_query['ea_id'] = {'$in': list(owned_player_ids)}

        # If we have required players, include them regardless of other filters
        if include_players:
            query = {
                '$or': [
                    base_query,
                    {
                        f'metaratings.{position}': {'$exists': True},
                        'ea_id': {'$in': list(include_players)}
                    }
                ]
            }
        else:
            query = base_query

        candidates = list(
            players.find(query)
            .sort(f'metaratings.{position}.score', -1)
            .limit(limit + len(include_players))  # Increase limit to ensure we get required players
        )

        # Filter and set prices, extract position-specific metarating
        valid_candidates = []
        for player in candidates:
            player['is_owned'] = player['ea_id'] in owned_player_ids
            player['is_required'] = player['ea_id'] in include_players

            # Extract position-specific metarating score
            metaratings = player.get('metaratings', {})
            position_meta = metaratings.get(position, {})
            player['metarating'] = position_meta.get('score', 0.0)

            if player['is_owned']:
                # Owned players always have price 0
                player['price'] = 0
                valid_candidates.append(player)
            elif player['is_required']:
                # Required players must be included even if not owned
                market_price = player.get('market_price')
                if market_price is not None:
                    player['price'] = market_price
                    valid_candidates.append(player)
                else:
                    # Required player is extinct - still include with a high price estimate
                    player['price'] = player.get('futbin_price', 1000000)
                    valid_candidates.append(player)
            else:
                # Non-owned, non-required players must have a valid market price
                market_price = player.get('market_price')
                if market_price is not None:
                    player['price'] = market_price
                    valid_candidates.append(player)

        return valid_candidates

    def optimize_squad(self, positions: List[str], budget: int, min_chemistry: int = 20,
                       owned_only: bool = False, max_iterations: int = 1,
                       candidate_limit: int = 200, min_metarating: float = 0.0,
                       include_players: Optional[List[int]] = None) -> Dict:
        """
        Optimize squad with chemistry as HARD constraint using CP-SAT.

        Args:
            positions: List of 11 position codes
            budget: Maximum budget
            min_chemistry: Minimum required chemistry (HARD constraint)
            owned_only: Only use owned players
            max_iterations: Unused (kept for API compatibility)
            candidate_limit: Maximum candidates per position (optimization: lower = faster)
            min_metarating: Minimum metarating filter (optimization: higher = faster)
            include_players: List of player EA IDs that must be included in the squad

        Returns:
            Dict with squad details and optimization results
        """
        start_time = time.time()

        if len(positions) != 11:
            return {
                'success': False,
                'error': f'Must provide exactly 11 positions, got {len(positions)}'
            }

        include_player_set = set(include_players) if include_players else set()

        print(f"Starting CP-SAT optimization with HARD chemistry constraint...")
        print(f"  Positions: {', '.join(positions)}")
        print(f"  Budget: {budget:,}")
        print(f"  Min Chemistry: {min_chemistry} (HARD CONSTRAINT)")
        print(f"  Owned Only: {owned_only}")
        print(f"  Candidate Limit: {candidate_limit} per position")
        print(f"  Min Metarating: {min_metarating}")
        print(f"  Required Players: {include_players if include_players else 'None'}")
        print(f"  Timeout: {self.timeout}s")
        print()

        owned_player_ids = self.get_owned_player_ids()
        print(f"Owned players in database: {len(owned_player_ids)}")

        # Validate required players exist
        if include_player_set:
            players_collection = self.db['players']
            for player_id in include_player_set:
                player = players_collection.find_one({'ea_id': player_id})
                if not player:
                    return {
                        'success': False,
                        'error': f'Required player with ID {player_id} not found in database'
                    }
                print(f"  Required player: {player['name']} (ID: {player_id})")

        # Get candidates
        print("\nFetching candidates...")
        candidates = []
        for i, position in enumerate(positions):
            pos_candidates = self.get_candidates_for_position(
                position, owned_player_ids, owned_only, candidate_limit, min_metarating, include_player_set
            )
            candidates.append(pos_candidates)
            
            # Count required players in this position
            required_in_pos = sum(1 for p in pos_candidates if p.get('is_required', False))
            print(f"  Position {i+1} ({position}): {len(pos_candidates)} candidates" +
                  (f" (includes {required_in_pos} required)" if required_in_pos > 0 else ""))

            if not pos_candidates:
                return {
                    'success': False,
                    'error': f'No candidates found for position {position}'
                }

        # Check if all required players can be placed
        if include_player_set:
            placeable_required = set()
            for pos_candidates in candidates:
                for player in pos_candidates:
                    if player.get('is_required', False):
                        placeable_required.add(player['ea_id'])
            
            missing = include_player_set - placeable_required
            if missing:
                return {
                    'success': False,
                    'error': f'Required players {missing} cannot be placed in any of the specified positions'
                }

        print(f"\nTotal decision variables: {sum(len(c) for c in candidates)}")
        print("\nBuilding CP-SAT model with chemistry as HARD constraint...")

        result = self._build_and_solve_cpsat(positions, candidates, budget, min_chemistry, include_player_set)
        result['solve_time'] = time.time() - start_time

        return result

    def _build_and_solve_cpsat(self, positions, candidates, budget, min_chemistry, include_players=None):
        """Build and solve CP-SAT model with chemistry hard constraint."""
        model = cp_model.CpModel()
        include_players = include_players or set()

        # Scale factor for metarating (CP-SAT prefers integers)
        SCALE = 100

        print("  Creating decision variables...")
        # Decision variables: x[pos][cand] - binary
        x = {}
        for pos_idx in range(11):
            for cand_idx in range(len(candidates[pos_idx])):
                x[pos_idx, cand_idx] = model.NewBoolVar(f'x_{pos_idx}_{cand_idx}')

        print(f"  Decision variables: {len(x)}")

        # =================================================================
        # CONSTRAINT 1: One player per position
        # =================================================================
        for pos_idx in range(11):
            model.AddExactlyOne([x[pos_idx, cand_idx] for cand_idx in range(len(candidates[pos_idx]))])

        # =================================================================
        # CONSTRAINT 2: Unique players (by EA ID and by Name)
        # =================================================================
        # Prevent same EA ID (same exact card)
        player_positions = {}
        for pos_idx in range(11):
            for cand_idx, player in enumerate(candidates[pos_idx]):
                ea_id = player['ea_id']
                if ea_id not in player_positions:
                    player_positions[ea_id] = []
                player_positions[ea_id].append((pos_idx, cand_idx))

        for ea_id, pos_list in player_positions.items():
            if len(pos_list) > 1:
                model.Add(sum([x[pos_idx, cand_idx] for pos_idx, cand_idx in pos_list]) <= 1)

        # Prevent same player name (different versions/cards)
        player_names = {}
        for pos_idx in range(11):
            for cand_idx, player in enumerate(candidates[pos_idx]):
                name = player.get('name', '').strip().lower()
                if name and name != 'unknown':
                    if name not in player_names:
                        player_names[name] = []
                    player_names[name].append((pos_idx, cand_idx))

        duplicate_names_count = 0
        for name, pos_list in player_names.items():
            if len(pos_list) > 1:
                # Only one version of this player can be selected
                model.Add(sum([x[pos_idx, cand_idx] for pos_idx, cand_idx in pos_list]) <= 1)
                duplicate_names_count += 1

        if duplicate_names_count > 0:
            print(f"  Added uniqueness constraints for {duplicate_names_count} players with multiple cards")

        # =================================================================
        # CONSTRAINT 3: Required players must be selected
        # =================================================================
        if include_players:
            print(f"  Adding constraints for {len(include_players)} required players...")
            for required_id in include_players:
                # Find all positions where this player can be placed
                player_vars = []
                for pos_idx in range(11):
                    for cand_idx, player in enumerate(candidates[pos_idx]):
                        if player['ea_id'] == required_id:
                            player_vars.append(x[pos_idx, cand_idx])
                
                if player_vars:
                    # This player must be selected in exactly one position
                    model.AddExactlyOne(player_vars)
                    print(f"    Player {required_id} must be selected (found in {len(player_vars)} positions)")

        # =================================================================
        # CONSTRAINT 4: Budget
        # =================================================================
        budget_terms = []
        for pos_idx in range(11):
            for cand_idx, player in enumerate(candidates[pos_idx]):
                price = int(player.get('price', 0))
                budget_terms.append(price * x[pos_idx, cand_idx])
        model.Add(sum(budget_terms) <= budget)

        print(f"  Basic constraints added")

        # =================================================================
        # CHEMISTRY CONSTRAINTS (HARD)
        # =================================================================
        print(f"  Building chemistry constraints...")
        player_chemistry_vars = self._add_chemistry_constraints(model, x, candidates, min_chemistry)

        print(f"  Chemistry constraints added")

        # =================================================================
        # OBJECTIVE: Maximize metarating
        # =================================================================
        metarating_terms = []
        for pos_idx in range(11):
            for cand_idx, player in enumerate(candidates[pos_idx]):
                metarating = int(player.get('metarating', 0) * SCALE)
                metarating_terms.append(metarating * x[pos_idx, cand_idx])
        model.Maximize(sum(metarating_terms))

        # =================================================================
        # SOLVE
        # =================================================================
        print(f"\nSolving with CP-SAT...")
        print(f"  This may take up to {self.timeout}s for complex chemistry constraints...")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.timeout
        solver.parameters.log_search_progress = True  # Show progress
        solver.parameters.num_search_workers = 12 # Use multiple threads

        status = solver.Solve(model)

        print(f"\nSolver finished!")
        print(f"  Status: {solver.StatusName(status)}")
        print(f"  Wall time: {solver.WallTime():.2f}s")

        # =================================================================
        # EXTRACT SOLUTION
        # =================================================================
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self._extract_solution(solver, x, positions, candidates, player_chemistry_vars, status, include_players)
        elif status == cp_model.INFEASIBLE:
            return {
                'success': False,
                'error': f'No feasible solution exists with {min_chemistry} chemistry and required players. Try lowering min_chemistry, increasing budget, or removing some required players.'
            }
        else:
            return {
                'success': False,
                'error': f'Solver failed: {solver.StatusName(status)}'
            }

    def _add_chemistry_constraints(self, model, x, candidates, min_chemistry):
        """Add chemistry constraints to CP-SAT model (HARD constraints)."""

        # Collect all unique clubs, leagues, nations
        all_clubs = set()
        all_leagues = set()
        all_nations = set()

        for pos_idx in range(11):
            for player in candidates[pos_idx]:
                if player.get('club_ea_id'):
                    all_clubs.add(player['club_ea_id'])
                if player.get('league_ea_id'):
                    all_leagues.add(player['league_ea_id'])
                if player.get('nation_ea_id'):
                    all_nations.add(player['nation_ea_id'])

        print(f"    Unique clubs: {len(all_clubs)}, leagues: {len(all_leagues)}, nations: {len(all_nations)}")

        # Count variables
        club_count = {}
        league_count = {}
        nation_count = {}

        for club_id in all_clubs:
            club_count[club_id] = model.NewIntVar(0, 11, f'club_{club_id}')
            terms = []
            for pos_idx in range(11):
                for cand_idx, player in enumerate(candidates[pos_idx]):
                    if player.get('club_ea_id') == club_id:
                        terms.append(x[pos_idx, cand_idx])
            if terms:
                model.Add(club_count[club_id] == sum(terms))

        for league_id in all_leagues:
            league_count[league_id] = model.NewIntVar(0, 22, f'league_{league_id}')
            terms = []
            for pos_idx in range(11):
                for cand_idx, player in enumerate(candidates[pos_idx]):
                    if player.get('league_ea_id') == league_id:
                        multiplier = 2 if player.get('is_hero', False) else 1
                        terms.append(multiplier * x[pos_idx, cand_idx])
            if terms:
                model.Add(league_count[league_id] == sum(terms))

        for nation_id in all_nations:
            nation_count[nation_id] = model.NewIntVar(0, 22, f'nation_{nation_id}')
            terms = []
            for pos_idx in range(11):
                for cand_idx, player in enumerate(candidates[pos_idx]):
                    if player.get('nation_ea_id') == nation_id:
                        multiplier = 2 if player.get('is_icon', False) else 1
                        terms.append(multiplier * x[pos_idx, cand_idx])
            if terms:
                model.Add(nation_count[nation_id] == sum(terms))

        # Player chemistry variables
        player_chemistry = {}
        thresholds = self.chemistry_calc.THRESHOLDS

        for pos_idx in range(11):
            player_chemistry[pos_idx] = model.NewIntVar(0, 3, f'chem_{pos_idx}')

            # For each candidate, define chemistry if selected
            for cand_idx, player in enumerate(candidates[pos_idx]):
                is_selected = x[pos_idx, cand_idx]

                # Icons/Heroes get 3 automatically
                if player.get('is_icon') or player.get('is_hero'):
                    model.Add(player_chemistry[pos_idx] == 3).OnlyEnforceIf(is_selected)
                    continue

                # Calculate chemistry for this player
                club_id = player.get('club_ea_id')
                league_id = player.get('league_ea_id')
                nation_id = player.get('nation_ea_id')

                # Create auxiliary variables for this specific player's chemistry
                club_chem = model.NewIntVar(0, 3, f'club_chem_{pos_idx}_{cand_idx}')
                league_chem = model.NewIntVar(0, 3, f'league_chem_{pos_idx}_{cand_idx}')
                nation_chem = model.NewIntVar(0, 3, f'nation_chem_{pos_idx}_{cand_idx}')

                # Club chemistry using AddElement (lookup table)
                # Index: count value (0-11), Value: chemistry points
                if club_id and club_id in club_count:
                    # Thresholds: 2→1, 4→2, 7→3
                    model.AddElement(club_count[club_id], [0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3], club_chem)
                else:
                    model.Add(club_chem == 0)

                # League chemistry
                # Thresholds: 3→1, 5→2, 8→3
                if league_id and league_id in league_count:
                    model.AddElement(league_count[league_id], [0, 0, 0, 1, 1, 2, 2, 2, 3] + [3]*14, league_chem)
                else:
                    model.Add(league_chem == 0)

                # Nation chemistry
                # Thresholds: 2→1, 5→2, 8→3
                if nation_id and nation_id in nation_count:
                    model.AddElement(nation_count[nation_id], [0, 0, 1, 1, 1, 2, 2, 2, 3] + [3]*14, nation_chem)
                else:
                    model.Add(nation_chem == 0)

                # Total chemistry = min(club + league + nation, 3)
                total = model.NewIntVar(0, 9, f'total_{pos_idx}_{cand_idx}')
                model.Add(total == club_chem + league_chem + nation_chem)

                capped_chem = model.NewIntVar(0, 3, f'capped_{pos_idx}_{cand_idx}')
                model.AddMinEquality(capped_chem, [total, 3])

                # If this player is selected, set player_chemistry[pos] to capped_chem
                model.Add(player_chemistry[pos_idx] == capped_chem).OnlyEnforceIf(is_selected)

        # HARD CONSTRAINT: Total chemistry >= min_chemistry
        total_chemistry = model.NewIntVar(0, 33, 'total_chemistry')
        model.Add(total_chemistry == sum([player_chemistry[pos_idx] for pos_idx in range(11)]))
        model.Add(total_chemistry >= min_chemistry)

        print(f"    HARD constraint: total_chemistry >= {min_chemistry}")

        return player_chemistry

    def _extract_solution(self, solver, x, positions, candidates, player_chemistry, status, include_players=None):
        """Extract solution from solved CP-SAT model."""
        include_players = include_players or set()
        squad = []
        total_cost = 0
        total_metarating = 0

        for pos_idx in range(11):
            for cand_idx, player in enumerate(candidates[pos_idx]):
                if solver.Value(x[pos_idx, cand_idx]):
                    squad_player = {
                        'position': positions[pos_idx],
                        'position_index': pos_idx,
                        'ea_id': player['ea_id'],
                        'name': player.get('name', 'Unknown'),
                        'metarating': player.get('metarating', 0),
                        'price': player.get('price', 0),
                        'is_owned': player.get('is_owned', False),
                        'is_required': player['ea_id'] in include_players,
                        'club_ea_id': player.get('club_ea_id'),
                        'league_ea_id': player.get('league_ea_id'),
                        'nation_ea_id': player.get('nation_ea_id'),
                        'is_icon': player.get('is_icon', False),
                        'is_hero': player.get('is_hero', False),
                        'chemistry': solver.Value(player_chemistry[pos_idx])
                    }
                    squad.append(squad_player)
                    total_cost += squad_player['price']
                    total_metarating += squad_player['metarating']
                    break

        # Verify chemistry
        actual_chemistry = self.chemistry_calc.calculate_squad_chemistry(squad)
        total_chemistry = sum(p['chemistry'] for p in squad)

        status_str = 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'

        return {
            'success': True,
            'status': status_str,
            'squad': squad,
            'total_metarating': round(total_metarating, 2),
            'total_cost': total_cost,
            'total_chemistry': total_chemistry,
            'actual_chemistry': actual_chemistry,
            'owned_count': sum(1 for p in squad if p['is_owned']),
            'required_count': sum(1 for p in squad if p['is_required']),
            'chemistry_valid': True
        }
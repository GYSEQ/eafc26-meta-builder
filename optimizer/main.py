"""CLI for squad optimization."""
import argparse
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from optimizer.solver import SquadOptimizer


def format_squad_output(result):
    """Format optimization result for console output."""
    if not result['success']:
        print(f"\n✗ Optimization failed:")
        print(f"  {result['error']}")
        if 'warning' in result:
            print(f"  Warning: {result['warning']}")
        return

    squad = result['squad']

    print("\n" + "=" * 80)
    print(f"OPTIMIZED SQUAD - {result['status']}")
    print("=" * 80)
    print(f"Total Metarating: {result['total_metarating']:.2f}")
    print(f"Total Cost: {result['total_cost']:,} coins")
    print(f"Total Chemistry: {result.get('total_chemistry', 0)}/33")

    if 'iterations' in result:
        print(f"Iterations: {result['iterations']}")

    print(f"Solve Time: {result.get('solve_time', 0):.1f}s")
    print(f"Owned Players: {result.get('owned_count', 0)}/11")
    
    if result.get('required_count', 0) > 0:
        print(f"Required Players: {result['required_count']}/11")

    if 'warning' in result:
        print(f"\n⚠ WARNING: {result['warning']}")

    print("\n" + "-" * 80)
    print(f"{'#':<3} {'Pos':<6} {'Player':<25} {'Meta':<6} {'Price':<12} {'Own':<5} {'Req':<5}")
    print("-" * 80)

    for i, player in enumerate(squad, 1):
        name = player['name'][:24]
        meta = f"{player['metarating']:.1f}"
        price = "OWNED" if player['is_owned'] else f"{player['price']:,}"
        owned = "✓" if player['is_owned'] else ""
        required = "★" if player.get('is_required', False) else ""
        pos = player['position']

        special = ""
        if player.get('is_icon'):
            special = " [ICON]"
        elif player.get('is_hero'):
            special = " [HERO]"

        print(f"{i:<3} {pos:<6} {name + special:<25} {meta:<6} {price:<12} {owned:<5} {required:<5}")

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Optimize EA FC 26 squad with chemistry and budget constraints'
    )

    parser.add_argument(
        '--positions',
        type=str,
        required=True,
        help='Comma-separated list of 11 positions (e.g., "GK,RB,CB,CB,LB,CDM,CM,CM,RW,ST,LW")'
    )

    parser.add_argument(
        '--budget',
        type=int,
        required=True,
        help='Maximum budget in coins'
    )

    parser.add_argument(
        '--min-chemistry',
        type=int,
        default=20,
        help='Minimum required chemistry (default: 20)'
    )

    parser.add_argument(
        '--owned-only',
        action='store_true',
        help='Only use owned players from your club'
    )

    parser.add_argument(
        '--include-player',
        type=int,
        action='append',
        help='EA ID of player that must be included in the squad (can be used multiple times)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Solver timeout in seconds per iteration (default: 60)'
    )

    parser.add_argument(
        '--max-iterations',
        type=int,
        default=50,
        help='Maximum optimization iterations (default: 20)'
    )

    parser.add_argument(
        '--candidate-limit',
        type=int,
        default=150,
        help='Maximum candidates per position (default: 100, use lower for faster solving)'
    )

    parser.add_argument(
        '--min-metarating',
        type=float,
        default=0.0,
        help='Minimum metarating filter (default: 0, use 70-80 for faster solving)'
    )

    args = parser.parse_args()

    # Parse positions
    positions = [p.strip().upper() for p in args.positions.split(',')]

    if len(positions) != 11:
        print(f"Error: Must provide exactly 11 positions, got {len(positions)}")
        sys.exit(1)

    # Valid positions
    valid_positions = {'GK', 'RB', 'RWB', 'CB', 'LB', 'LWB', 'CDM', 'RM', 'CM', 'LM',
                       'CAM', 'RF', 'RW', 'ST', 'LW', 'LF', 'CF'}

    for pos in positions:
        if pos not in valid_positions:
            print(f"Error: Invalid position '{pos}'")
            print(f"Valid positions: {', '.join(sorted(valid_positions))}")
            sys.exit(1)

    # Validate chemistry
    if args.min_chemistry < 0 or args.min_chemistry > 33:
        print("Error: Chemistry must be between 0 and 33")
        sys.exit(1)

    # Validate required players
    if args.include_player:
        if len(args.include_player) > 11:
            print("Error: Cannot require more than 11 players")
            sys.exit(1)
        
        # Check for duplicates
        unique_players = set(args.include_player)
        if len(unique_players) != len(args.include_player):
            print("Error: Duplicate player IDs in --include-player")
            sys.exit(1)
        
        print(f"Required players: {args.include_player}")

    # Run optimization
    try:
        optimizer = SquadOptimizer(timeout=args.timeout)
        result = optimizer.optimize_squad(
            positions=positions,
            budget=args.budget,
            min_chemistry=args.min_chemistry,
            owned_only=args.owned_only,
            max_iterations=args.max_iterations,
            candidate_limit=args.candidate_limit,
            min_metarating=args.min_metarating,
            include_players=args.include_player  # Pass the list of required player IDs
        )

        format_squad_output(result)

        if not result['success'] or not result.get('chemistry_valid', False):
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOptimization interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError during optimization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
"""Check owned players and their metarating positions."""
from config.database import get_database

db = get_database()

# Get owned player IDs
owned_ids = list(db.my_club.distinct('player_ea_id'))
print(f"Total owned players in my_club: {len(owned_ids)}")

# Find these players in players collection
owned_players = list(db.players.find({'ea_id': {'$in': owned_ids}}))
print(f"Owned players with metarating data: {len(owned_players)}")

# Group by metarating position
position_counts = {}
for player in owned_players:
    pos = player.get('metarating_position')
    if pos:
        position_counts[pos] = position_counts.get(pos, 0) + 1

print("\nOwned players by metarating position:")
for pos, count in sorted(position_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {pos}: {count}")

# Check players without metarating
no_meta = [p for p in owned_players if not p.get('metarating_position') or p.get('metarating', 0) == 0]
print(f"\nOwned players WITHOUT metarating: {len(no_meta)}")

# Show some CDM alternatives (CM players can play CDM)
print("\nAlternative positions for CDM:")
cm_players = [p for p in owned_players if p.get('metarating_position') == 'CM']
print(f"  CM (can play CDM): {len(cm_players)}")
cam_players = [p for p in owned_players if p.get('metarating_position') == 'CAM']
print(f"  CAM (can play CDM): {len(cam_players)}")

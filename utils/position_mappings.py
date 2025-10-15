"""
Position and role ID mappings for EA FC 26.
"""

# EA Position ID to Position Code mapping
POSITION_ID_TO_CODE = {
    0: 'GK',
    2: 'RWB',
    3: 'RB',
    5: 'CB',
    7: 'LB',
    8: 'LWB',
    10: 'CDM',
    12: 'RM',
    14: 'CM',
    16: 'LM',
    18: 'CAM',
    21: 'RF',
    23: 'RW',
    25: 'ST',
    27: 'LW',
    28: 'LF',
    29: 'CF',
}

# Position Code to EA Position ID (reverse mapping)
POSITION_CODE_TO_ID = {v: k for k, v in POSITION_ID_TO_CODE.items()}

def get_position_code(position_id: int) -> str:
    """
    Convert position ID to position code.
    
    Args:
        position_id: Numeric position ID from API
        
    Returns:
        Position code (e.g., 'GK', 'ST', 'CM') or 'UNKNOWN' if not found
        
    Examples:
        >>> get_position_code(0)
        'GK'
        >>> get_position_code(25)
        'ST'
        >>> get_position_code(999)
        'UNKNOWN'
    """
    return POSITION_ID_TO_CODE.get(position_id, 'UNKNOWN')
"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
Common constants for semantic engine
"""
from enum import Enum

class DataTier(str, Enum):
    """
    Enum class to distinguish between legacy and synthetic questions source.
    """
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
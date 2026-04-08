import json
from typing import Any, Union
from collections.abc import Hashable

def are_equivalent(obj1: Any, obj2: Any) -> bool:
    """
    Test equivalence between two objects, handling non-hashable types gracefully.
    
    Priority order:
    1. If both are hashable: use direct comparison (fast path)
    2. If types differ: return False
    3. If both are non-hashable: use JSON-serialized string comparison
    
    Args:
        obj1: First object to compare
        obj2: Second object to compare
        
    Returns:
        bool: True if objects are equivalent, False otherwise
    """
    
    # Fast path: both hashable - direct comparison
    if _is_hashable(obj1) and _is_hashable(obj2):
        return obj1 == obj2
    
    # Types don't match - can't be equivalent
    if type(obj1) is not type(obj2):
        return False
    
    # Both non-hashable - use JSON string comparison
    if not _is_hashable(obj1) and not _is_hashable(obj2):
        return _json_string_compare(obj1, obj2)
    
    # Mixed case (one hashable, one non-hashable) - can't be equivalent
    return False


def _is_hashable(obj: Any) -> bool:
    """Check if an object is hashable without raising exceptions."""
    try:
        hash(obj)
        return True
    except TypeError:
        return False


def _json_string_compare(obj1: Any, obj2: Any) -> bool:
    """
    Compare two objects by converting them to JSON strings.
    Handles common non-hashable types like dict, list, set, etc.
    """
    try:
        # Convert to JSON with sorted keys for consistent comparison
        json1 = json.dumps(obj1, sort_keys=True, default=_json_fallback)
        json2 = json.dumps(obj2, sort_keys=True, default=_json_fallback)
        return json1 == json2
    except (TypeError, ValueError, OverflowError):
        # Fallback for objects that can't be JSON serialized
        return _recursive_compare(obj1, obj2)


def _json_fallback(obj: Any) -> Any:
    """Fallback serializer for non-JSON-serializable objects."""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)  # Convert sets to sorted lists for deterministic output
    if isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    return str(obj)  # Last resort


def _recursive_compare(obj1: Any, obj2: Any) -> bool:
    """
    Recursive comparison for deeply nested structures that may fail JSON serialization.
    """
    if type(obj1) is not type(obj2):
        return False
    
    if isinstance(obj1, dict):
        if set(obj1.keys()) != set(obj2.keys()):
            return False
        return all(_recursive_compare(obj1[k], obj2[k]) for k in obj1.keys())
    
    if isinstance(obj1, (list, tuple, set, frozenset)):
        if len(obj1) != len(obj2):
            return False
        # For sets, order doesn't matter - convert to sorted list if possible
        if isinstance(obj1, (set, frozenset)):
            try:
                return sorted(obj1) == sorted(obj2)
            except TypeError:
                # Can't sort - fall back to item-by-item comparison
                list2 = list(obj2)
                for item1 in obj1:
                    found = False
                    for i, item2 in enumerate(list2):
                        if _recursive_compare(item1, item2):
                            list2.pop(i)
                            found = True
                            break
                    if not found:
                        return False
                return True
        else:
            # Lists and tuples preserve order
            return all(_recursive_compare(a, b) for a, b in zip(obj1, obj2))
    
    # Default comparison
    try:
        return obj1 == obj2
    except Exception:
        return str(obj1) == str(obj2)

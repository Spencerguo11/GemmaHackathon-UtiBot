"""Duplicate detection."""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Tuple
from models import Bill


def detect_exact_duplicates(bills: List[Bill]) -> Dict[str, List[str]]:
    """
    Detect exact duplicates by file hash.
    
    Args:
        bills: List of bills
    
    Returns:
        Dict mapping hash to list of bill_ids
    """
    hash_map = {}
    duplicates = {}
    
    for bill in bills:
        if bill.file_hash not in hash_map:
            hash_map[bill.file_hash] = []
        hash_map[bill.file_hash].append(bill.bill_id)
    
    # Only include hashes with multiple bills
    for file_hash, bill_ids in hash_map.items():
        if len(bill_ids) > 1:
            duplicates[file_hash] = bill_ids
    
    return duplicates


def detect_logical_duplicates(bills: List[Bill]) -> List[Tuple[str, str]]:
    """
    Detect logical duplicates by content.
    
    Criteria:
    - Same provider
    - Same masked account number
    - Same billing period
    - Same amount due
    - Same due date
    
    Args:
        bills: List of bills
    
    Returns:
        List of (bill_id_1, bill_id_2) tuples of potential duplicates
    """
    duplicates = []
    
    for i, bill1 in enumerate(bills):
        for bill2 in bills[i + 1:]:
            # All criteria must match
            if (
                bill1.provider_name == bill2.provider_name
                and bill1.account_number_masked == bill2.account_number_masked
                and bill1.billing_period_start == bill2.billing_period_start
                and bill1.billing_period_end == bill2.billing_period_end
                and bill1.amount_due == bill2.amount_due
                and bill1.due_date == bill2.due_date
            ):
                duplicates.append((bill1.bill_id, bill2.bill_id))
    
    return duplicates

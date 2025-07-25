"""Phone number utilities for consistent formatting and normalization."""
import re
from typing import Optional


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number to consistent format (digits only, no + prefix).
    This ensures consistent storage and comparison across the system.
    
    Special handling for Mexican mobile numbers:
    - WhatsApp format: 5213319858734 (52 + 1 + 10 digits)
    - GHL format: +523319858734 (52 + 10 digits)
    - Both normalize to: 5213319858734
    
    Args:
        phone: Phone number in any format
        
    Returns:
        Normalized phone number (digits only) or None if input is empty
        
    Examples:
        +523319858734 -> 5213319858734
        5213319858734 -> 5213319858734
        523319858734 -> 5213319858734
        +1-555-123-4567 -> 15551234567
        (555) 123-4567 -> 15551234567
    """
    if not phone:
        return None
    
    # Remove all non-digit characters (spaces, dashes, parentheses, + sign)
    phone = re.sub(r'\D', '', phone)
    
    if not phone:
        return None
    
    # Handle Mexican mobile numbers
    # If it's 52 + 10 digits (GHL format), add the 1 for mobile
    if phone.startswith('52') and len(phone) == 12 and not phone.startswith('521'):
        phone = '521' + phone[2:]
    
    # Handle 10-digit numbers without country code
    elif len(phone) == 10:
        # For Mexican numbers (3xx, 5xx, 6xx, 8xx are common mobile prefixes in Mexico)
        first_digit = phone[0]
        if first_digit in ['3', '5', '6', '8']:
            # Assume Mexican mobile number
            phone = '521' + phone
        else:
            # Assume US number without country code
            phone = '1' + phone
    
    return phone


def format_phone_for_display(phone: Optional[str]) -> Optional[str]:
    """
    Format phone number for user display with + prefix.
    
    Args:
        phone: Normalized phone number
        
    Returns:
        Phone number with + prefix for display
        
    Examples:
        523319858734 -> +523319858734
        15551234567 -> +15551234567
    """
    if not phone:
        return None
    
    # First normalize to ensure clean input
    phone = normalize_phone(phone)
    if not phone:
        return None
        
    return f"+{phone}"


def format_phone_for_whatsapp(phone: Optional[str]) -> Optional[str]:
    """
    Format phone number for WhatsApp API (no + prefix, digits only).
    
    Args:
        phone: Phone number in any format
        
    Returns:
        Phone number suitable for WhatsApp API
        
    Examples:
        +523319858734 -> 523319858734
        523319858734 -> 523319858734
    """
    return normalize_phone(phone)


def format_phone_for_ghl(phone: Optional[str]) -> Optional[str]:
    """
    Format phone number for GoHighLevel API (with + prefix).
    
    Args:
        phone: Phone number in any format
        
    Returns:
        Phone number in E.164 format for GHL
        
    Examples:
        523319858734 -> +523319858734
        +523319858734 -> +523319858734
    """
    return format_phone_for_display(phone)


def phones_match(phone1: Optional[str], phone2: Optional[str]) -> bool:
    """
    Check if two phone numbers match after normalization.
    
    Args:
        phone1: First phone number
        phone2: Second phone number
        
    Returns:
        True if phones match after normalization
        
    Examples:
        phones_match("+523319858734", "523319858734") -> True
        phones_match("+1-555-123-4567", "15551234567") -> True
    """
    if not phone1 or not phone2:
        return False
        
    return normalize_phone(phone1) == normalize_phone(phone2)
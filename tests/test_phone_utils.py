"""Tests for phone number normalization utilities."""
import pytest
from app.utils.phone_utils import (
    normalize_phone,
    format_phone_for_display,
    format_phone_for_whatsapp,
    format_phone_for_ghl,
    phones_match
)


class TestNormalizePhone:
    """Test phone normalization function."""
    
    def test_normalize_with_plus_prefix(self):
        """Test normalization of phone with + prefix."""
        assert normalize_phone("+523319858734") == "523319858734"
        assert normalize_phone("+15551234567") == "15551234567"
        assert normalize_phone("+1-555-123-4567") == "15551234567"
    
    def test_normalize_without_prefix(self):
        """Test normalization of phone without prefix."""
        assert normalize_phone("523319858734") == "523319858734"
        assert normalize_phone("5551234567") == "15551234567"  # US number
    
    def test_normalize_with_special_chars(self):
        """Test normalization with special characters."""
        assert normalize_phone("+52 331 985 8734") == "523319858734"
        assert normalize_phone("(555) 123-4567") == "15551234567"
        assert normalize_phone("+1-555-123-4567") == "15551234567"
        assert normalize_phone("52 1 331 985 8734") == "5213319858734"
    
    def test_normalize_empty_or_none(self):
        """Test normalization of empty or None values."""
        assert normalize_phone(None) is None
        assert normalize_phone("") is None
        assert normalize_phone("   ") is None
    
    def test_normalize_non_numeric(self):
        """Test normalization of non-numeric strings."""
        assert normalize_phone("abc") is None
        assert normalize_phone("+++") is None


class TestFormatPhoneForDisplay:
    """Test phone formatting for display."""
    
    def test_format_for_display(self):
        """Test formatting phone for display."""
        assert format_phone_for_display("523319858734") == "+523319858734"
        assert format_phone_for_display("15551234567") == "+15551234567"
    
    def test_format_display_already_formatted(self):
        """Test formatting already formatted phone."""
        assert format_phone_for_display("+523319858734") == "+523319858734"
    
    def test_format_display_empty(self):
        """Test formatting empty phone."""
        assert format_phone_for_display(None) is None
        assert format_phone_for_display("") is None


class TestFormatPhoneForWhatsApp:
    """Test phone formatting for WhatsApp."""
    
    def test_format_for_whatsapp(self):
        """Test formatting phone for WhatsApp API."""
        assert format_phone_for_whatsapp("+523319858734") == "523319858734"
        assert format_phone_for_whatsapp("523319858734") == "523319858734"
        assert format_phone_for_whatsapp("+1-555-123-4567") == "15551234567"
    
    def test_format_whatsapp_empty(self):
        """Test formatting empty phone for WhatsApp."""
        assert format_phone_for_whatsapp(None) is None
        assert format_phone_for_whatsapp("") is None


class TestFormatPhoneForGHL:
    """Test phone formatting for GoHighLevel."""
    
    def test_format_for_ghl(self):
        """Test formatting phone for GHL API."""
        assert format_phone_for_ghl("523319858734") == "+523319858734"
        assert format_phone_for_ghl("+523319858734") == "+523319858734"
        assert format_phone_for_ghl("15551234567") == "+15551234567"
    
    def test_format_ghl_empty(self):
        """Test formatting empty phone for GHL."""
        assert format_phone_for_ghl(None) is None
        assert format_phone_for_ghl("") is None


class TestPhonesMatch:
    """Test phone number matching."""
    
    def test_phones_match_identical(self):
        """Test matching identical phones."""
        assert phones_match("523319858734", "523319858734") is True
        assert phones_match("+523319858734", "+523319858734") is True
    
    def test_phones_match_different_formats(self):
        """Test matching phones in different formats."""
        assert phones_match("+523319858734", "523319858734") is True
        assert phones_match("+52-331-985-8734", "523319858734") is True
        assert phones_match("+52 331 985 8734", "523319858734") is True
        assert phones_match("(555) 123-4567", "15551234567") is True
    
    def test_phones_dont_match(self):
        """Test non-matching phones."""
        assert phones_match("523319858734", "523319858735") is False
        assert phones_match("523319858734", "15551234567") is False
    
    def test_phones_match_empty(self):
        """Test matching with empty values."""
        assert phones_match(None, None) is False
        assert phones_match("", "") is False
        assert phones_match("523319858734", None) is False
        assert phones_match(None, "523319858734") is False


class TestMexicanPhoneNumbers:
    """Test specific Mexican phone number cases."""
    
    def test_mexican_mobile_with_1(self):
        """Test Mexican mobile numbers with 1 after country code."""
        # WhatsApp format (no +, with 1)
        assert normalize_phone("5213319858734") == "5213319858734"
        # GHL format (with +, no 1)
        assert normalize_phone("+523319858734") == "523319858734"
        # These should match
        assert phones_match("5213319858734", "+523319858734") is False  # Different normalized forms
    
    def test_format_conversions(self):
        """Test converting between WhatsApp and GHL formats."""
        # WhatsApp sends: 5213319858734
        whatsapp_phone = "5213319858734"
        normalized = normalize_phone(whatsapp_phone)
        assert normalized == "5213319858734"
        
        # Format for GHL (needs +)
        ghl_format = format_phone_for_ghl(normalized)
        assert ghl_format == "+5213319858734"
        
        # Format back for WhatsApp (no +)
        whatsapp_format = format_phone_for_whatsapp(ghl_format)
        assert whatsapp_format == "5213319858734"
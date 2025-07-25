"""Configuration management for Vitalis Chatbot."""
import os
from typing import Optional
from functools import lru_cache
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

load_dotenv()


class Config(BaseModel):
    """Application configuration with validation."""
    
    # Flask settings
    debug: bool = Field(default=False)
    testing: bool = Field(default=False)
    port: int = Field(default=5000, ge=1024, le=65535)
    
    # WhatsApp API settings
    webhook_verify_token: str = Field(..., min_length=10)
    graph_api_token: str = Field(..., min_length=10)
    callback_uri: str = Field(...)
    
    # DeepSeek LLM settings
    deepseek_api_key: str = Field(..., min_length=10)
    llm_model: str = Field(default="deepseek-chat")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    # Firebase settings
    firebase_credentials_path: str = Field(...)
    
    # GoHighLevel OAuth settings
    ghl_client_id: str = Field(..., min_length=10)
    ghl_client_secret: str = Field(..., min_length=10)
    ghl_api_base_url: str = Field(default="https://services.leadconnectorhq.com")
    
    # Security settings
    api_key_header: str = Field(default="X-API-Key")
    api_keys: list[str] = Field(default_factory=list)
    enable_rate_limiting: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60)
    
    # Conversation settings
    conversation_ttl_hours: int = Field(default=24, ge=1, le=168)  # 1 hour to 7 days
    max_conversation_messages: int = Field(default=100, ge=10, le=1000)
    
    # Sentry APM settings
    sentry_dsn: Optional[str] = Field(default=None)
    sentry_environment: str = Field(default="production")
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Application settings
    timezone: str = Field(default="America/Mexico_City")
    default_country_code: str = Field(default="52")
    
    # Stripe settings
    stripe_secret_key: str = Field(..., min_length=10)
    stripe_webhook_secret: str = Field(..., min_length=10)
    stripe_billing_webhook_secret: Optional[str] = Field(default=None, min_length=10)
    stripe_success_url: str = Field(default="https://vitalis.com/payment/success")
    stripe_cancel_url: str = Field(default="https://vitalis.com/payment/cancel")
    
    # Subscription settings
    subscription_enforcement_enabled: bool = Field(default=False)
    subscription_grace_period_days: int = Field(default=3, ge=0, le=30)
    
    # Message deduplication settings
    enable_message_deduplication: bool = Field(default=True)
    message_deduplication_ttl_hours: int = Field(default=2)
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        
    @validator("api_keys", pre=True)
    def parse_api_keys(cls, v):
        """Parse comma-separated API keys from environment variable."""
        if isinstance(v, str):
            return [key.strip() for key in v.split(",") if key.strip()]
        return v or []
    
    @validator("debug", "testing", "enable_rate_limiting", "enable_message_deduplication", pre=True)
    def parse_bool(cls, v):
        """Parse boolean values from environment variables."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    @validator("firebase_credentials_path")
    def validate_firebase_path(cls, v):
        """Ensure Firebase credentials file exists."""
        if not os.path.exists(v):
            raise ValueError(f"Firebase credentials file not found: {v}")
        return v


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config(
        webhook_verify_token=os.getenv("WEBHOOK_VERIFY_TOKEN"),
        graph_api_token=os.getenv("GRAPH_API_TOKEN"),
        callback_uri=os.getenv("CALLBACK_URI"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        firebase_credentials_path=os.getenv("FIREBASE_CREDENTIALS_PATH"),
        ghl_client_id=os.getenv("GHL_CLIENT_ID"),
        ghl_client_secret=os.getenv("GHL_CLIENT_SECRET"),
        api_keys=os.getenv("API_KEYS", ""),
        sentry_dsn=os.getenv("SENTRY_DSN"),
        debug=os.getenv("DEBUG", "false"),
        port=int(os.getenv("PORT", "5000")),
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
        stripe_billing_webhook_secret=os.getenv("STRIPE_BILLING_WEBHOOK_SECRET"),
        subscription_enforcement_enabled=os.getenv("SUBSCRIPTION_ENFORCEMENT_ENABLED", "false"),
        subscription_grace_period_days=int(os.getenv("SUBSCRIPTION_GRACE_PERIOD_DAYS", "3")),
        enable_message_deduplication=os.getenv("ENABLE_MESSAGE_DEDUPLICATION", "true"),
        message_deduplication_ttl_hours=int(os.getenv("MESSAGE_DEDUPLICATION_TTL_HOURS", "2")),
    )
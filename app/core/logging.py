"""Logging configuration for Vitalis Chatbot."""
import logging
import sys
import json
from typing import Any, Dict
from datetime import datetime
import traceback
from functools import lru_cache


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
            
        if hasattr(record, "account_id"):
            log_data["account_id"] = record.account_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "request_id", "user_id", "account_id"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter to add context to logs."""
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add context."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(config: Any) -> None:
    """Set up logging configuration."""
    # Set log level based on debug mode
    log_level = logging.DEBUG if config.debug else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)
    
    # Set log levels for third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    
    # Configure Sentry if DSN is provided
    if config.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            
            sentry_sdk.init(
                dsn=config.sentry_dsn,
                integrations=[
                    FlaskIntegration(
                        transaction_style="endpoint"
                    ),
                    sentry_logging
                ],
                environment=config.sentry_environment,
                traces_sample_rate=config.sentry_traces_sample_rate,
                send_default_pii=False
            )
            
            logging.info("Sentry APM initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Sentry: {e}")


@lru_cache(maxsize=128)
def get_logger(name: str) -> LoggerAdapter:
    """Get a logger instance with the given name."""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, {})


def log_request(request: Any) -> Dict[str, Any]:
    """Extract relevant information from a request for logging."""
    return {
        "method": request.method,
        "path": request.path,
        "remote_addr": request.remote_addr,
        "user_agent": request.headers.get("User-Agent"),
        "request_id": request.headers.get("X-Request-ID")
    }


def log_response(response: Any, duration_ms: float) -> Dict[str, Any]:
    """Extract relevant information from a response for logging."""
    return {
        "status_code": response.status_code,
        "duration_ms": duration_ms
    }
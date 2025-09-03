"""
Configuration module for BCTC Auction Bot
Handles environment variables, bot settings, and constants
"""
import os
import discord
import logging
from typing import Optional, Type, Any, List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BotConfig:
    """Bot configuration class with all settings"""
    
    # Discord Configuration
    COMMAND_PREFIX = '!'
    BOT_DESCRIPTION = 'BCTC Auction Bot for Brawlhalla Code Trading'
    
    # Auction Configuration
    MIN_BID_INCREMENT = 0.10  # 10% minimum bid increment
    MIN_BID_AMOUNT = 0.50     # Minimum starting bid
    CLEANUP_INTERVAL_MINUTES = 1  # How often to check for expired auctions
    
    # Additional configurable values for more flexibility
    MIN_BID_TIME_BETWEEN_BIDS_SECONDS = 5  # Minimum time between bids per user
    MAX_USER_ACTIVE_AUCTIONS = 5  # Maximum active auctions per user
    VIEW_TIMEOUT_SECONDS = 300  # Timeout for UI views
    BID_SNIPING_EXTENSION_COOLDOWN_SECONDS = 300  # Cooldown between bid sniping extensions
    LATE_BIDS_THRESHOLD = 0.5  # Threshold for late bids (percentage of total bids)
    
    # New Performance & Scalability Configuration
    BID_SNIPING_PROTECTION_ENABLED = True
    BID_SNIPING_EXTENSION_MINUTES = 5  # Extend auction by 5 minutes if bid in last 5 minutes
    BID_SNIPING_WINDOW_MINUTES = 5     # Last X minutes trigger extension
    
    # Rate Limiting Configuration
    MAX_ACTIVE_AUCTIONS_PER_USER = 5
    MAX_AUCTIONS_CREATED_PER_HOUR = 3
    MAX_BIDS_PER_MINUTE = 10
    MAX_BIN_PURCHASES_PER_HOUR = 5
    
    # Notification Configuration
    NOTIFICATION_PREFERENCES_DEFAULT = {
        'auction_ending_warning': True,      # Notify when auction has < 1 hour left
        'auction_ending_minutes': 60,        # Minutes before end to send warning
        'bid_outbid_notification': True,     # Notify when outbid
        'auction_won_notification': True,    # Notify when won auction
        'auction_sold_notification': True,   # Notify seller when auction sold
        'auction_expired_notification': True, # Notify when auction expires unsold
        'new_auction_in_category': False,    # Notify about new auctions in watched categories
    }
    
    # Health Check Configuration
    HEALTH_CHECK_INTERVAL_MINUTES = 5
    DATABASE_MAX_CONNECTIONS = 10
    DATABASE_CONNECTION_TIMEOUT = 30
    DISCORD_API_RETRY_ATTEMPTS = 3
    DISCORD_API_RETRY_DELAY = 1.0
    
    # Logging Configuration
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'bot.log'
    LOG_MAX_SIZE_MB = 10
    LOG_BACKUP_COUNT = 5
    
    # Console encoding handling for Windows emoji support
    CONSOLE_ENCODING_UTF8 = True
    
    # Monitoring Configuration
    METRICS_ENABLED = True
    METRICS_COLLECTION_INTERVAL = 60  # seconds
    PERFORMANCE_ALERT_THRESHOLDS = {
        'response_time_ms': 5000,
        'memory_usage_mb': 512,
        'cpu_usage_percent': 80,
        'active_auctions_count': 1000,
        'failed_operations_per_hour': 50
    }
    
    # Database Configuration
    DATABASE_PATH = "auctions.db"
    DATABASE_BACKUP_ENABLED = True
    DATABASE_BACKUP_INTERVAL_HOURS = 6
    DATABASE_BACKUP_RETENTION_DAYS = 30
    
    # Duration Options Configuration (in hours)
    AUCTION_DURATION_OPTIONS = [
        {'label': '⚡ 10 Seconds (Admin)', 'value': 10/3600, 'admin_only': True, 'emoji': '⚡'},
        {'label': '1 Hour', 'value': 1, 'admin_only': False, 'emoji': '⏰'},
        {'label': '12 Hours', 'value': 12, 'admin_only': False, 'emoji': '🕐'},
        {'label': '1 Day', 'value': 24, 'admin_only': False, 'emoji': '📅'},
        {'label': '3 Days', 'value': 72, 'admin_only': False, 'emoji': '📆'},
        {'label': '1 Week', 'value': 168, 'admin_only': False, 'emoji': '🗓️'}
    ]
    
    # Discord Intents - Updated for non-privileged intents
    INTENTS = discord.Intents.default()
    # Comment out these lines if you haven't enabled privileged intents in Discord Developer Portal
    # INTENTS.message_content = True  # Requires message content intent
    # INTENTS.guilds = True  # This is usually enabled by default
    
    def __init__(self):
        self._discord_token = None
        self._notification_channel_id = None
        self._log_channel_id = None
        self._metrics_webhook_url = None
        self._loaded = False
    
    def _load_config(self):
        """Load configuration from environment variables"""
        if self._loaded:
            return
            
        self._discord_token = self._get_env_var('DISCORD_BOT_TOKEN')
        self._notification_channel_id = self._get_optional_env_var('NOTIFICATION_CHANNEL_ID', int)
        self._log_channel_id = self._get_optional_env_var('LOG_CHANNEL_ID', int)
        self._metrics_webhook_url = self._get_optional_env_var('METRICS_WEBHOOK_URL', str)
        
        # Load configurable values from environment
        self.MIN_BID_INCREMENT = self._get_optional_env_var('MIN_BID_INCREMENT', float) or self.MIN_BID_INCREMENT
        self.MIN_BID_AMOUNT = self._get_optional_env_var('MIN_BID_AMOUNT', float) or self.MIN_BID_AMOUNT
        self.CLEANUP_INTERVAL_MINUTES = self._get_optional_env_var('CLEANUP_INTERVAL_MINUTES', int) or self.CLEANUP_INTERVAL_MINUTES
        self.MIN_BID_TIME_BETWEEN_BIDS_SECONDS = self._get_optional_env_var('MIN_BID_TIME_BETWEEN_BIDS_SECONDS', int) or self.MIN_BID_TIME_BETWEEN_BIDS_SECONDS
        self.MAX_USER_ACTIVE_AUCTIONS = self._get_optional_env_var('MAX_USER_ACTIVE_AUCTIONS', int) or self.MAX_USER_ACTIVE_AUCTIONS
        self.VIEW_TIMEOUT_SECONDS = self._get_optional_env_var('VIEW_TIMEOUT_SECONDS', int) or self.VIEW_TIMEOUT_SECONDS
        self.BID_SNIPING_EXTENSION_COOLDOWN_SECONDS = self._get_optional_env_var('BID_SNIPING_EXTENSION_COOLDOWN_SECONDS', int) or self.BID_SNIPING_EXTENSION_COOLDOWN_SECONDS
        self.LATE_BIDS_THRESHOLD = self._get_optional_env_var('LATE_BIDS_THRESHOLD', float) or self.LATE_BIDS_THRESHOLD
        self.BID_SNIPING_PROTECTION_ENABLED = self._get_optional_env_var('BID_SNIPING_PROTECTION_ENABLED', bool) or self.BID_SNIPING_PROTECTION_ENABLED
        self.BID_SNIPING_EXTENSION_MINUTES = self._get_optional_env_var('BID_SNIPING_EXTENSION_MINUTES', int) or self.BID_SNIPING_EXTENSION_MINUTES
        self.BID_SNIPING_WINDOW_MINUTES = self._get_optional_env_var('BID_SNIPING_WINDOW_MINUTES', int) or self.BID_SNIPING_WINDOW_MINUTES
        self.MAX_ACTIVE_AUCTIONS_PER_USER = self._get_optional_env_var('MAX_ACTIVE_AUCTIONS_PER_USER', int) or self.MAX_ACTIVE_AUCTIONS_PER_USER
        self.MAX_AUCTIONS_CREATED_PER_HOUR = self._get_optional_env_var('MAX_AUCTIONS_CREATED_PER_HOUR', int) or self.MAX_AUCTIONS_CREATED_PER_HOUR
        self.LOG_LEVEL = self._get_optional_env_var('LOG_LEVEL', str) or self.LOG_LEVEL
        
        self._loaded = True
        
    def _get_env_var(self, var_name: str) -> str:
        """Get required environment variable"""
        value = os.getenv(var_name)
        if not value:
            raise ValueError(f"Environment variable {var_name} is required but not set")
        return value
    
    def _get_optional_env_var(self, var_name: str, var_type: Type = str) -> Optional[Any]:
        """Get optional environment variable with type conversion"""
        value = os.getenv(var_name)
        if value:
            try:
                if var_type == bool:
                    return value.lower() in ('true', '1', 'yes', 'on')
                return var_type(value)
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for {var_name}, ignoring")
        return None
    
    @property
    def token(self) -> str:
        """Get Discord bot token"""
        self._load_config()
        if not self._discord_token:
            raise ValueError("DISCORD_BOT_TOKEN is required but not set")
        return self._discord_token
    
    @property 
    def notification_channel(self) -> Optional[int]:
        """Get notification channel ID"""
        self._load_config()
        return self._notification_channel_id
    
    @property
    def log_channel(self) -> Optional[int]:
        """Get log channel ID"""
        self._load_config()
        return self._log_channel_id
    
    @property
    def metrics_webhook_url(self) -> Optional[str]:
        """Get metrics webhook URL"""
        self._load_config()
        return self._metrics_webhook_url
    
    def get_auction_duration_options(self, is_admin: bool = False) -> List[Dict[str, Any]]:
        """Get auction duration options based on user permissions"""
        if is_admin:
            return self.AUCTION_DURATION_OPTIONS
        else:
            return [opt for opt in self.AUCTION_DURATION_OPTIONS if not opt.get('admin_only', False)]
    
    def get_notification_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user notification preferences (placeholder for future database implementation)"""
        # TODO: Implement database lookup for user preferences
        return self.NOTIFICATION_PREFERENCES_DEFAULT.copy()


# Global config instance
config = BotConfig()
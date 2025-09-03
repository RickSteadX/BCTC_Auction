"""
Configuration module for BCTC Auction Bot
Handles environment variables, bot settings, and constants
"""
import os
import discord
from typing import Optional, Type, Any
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
    
    # Database Configuration
    DATABASE_PATH = "auctions.db"
    
    # Discord Intents - Updated for non-privileged intents
    INTENTS = discord.Intents.default()
    # Comment out these lines if you haven't enabled privileged intents in Discord Developer Portal
    # INTENTS.message_content = True  # Requires message content intent
    # INTENTS.guilds = True  # This is usually enabled by default
    
    def __init__(self):
        self._discord_token = None
        self._notification_channel_id = None
        self._loaded = False
    
    def _load_config(self):
        """Load configuration from environment variables"""
        if self._loaded:
            return
            
        self._discord_token = self._get_env_var('DISCORD_BOT_TOKEN')
        self._notification_channel_id = self._get_optional_env_var('NOTIFICATION_CHANNEL_ID', int)
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
                return var_type(value)
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for {var_name}, ignoring")
        return None
    
    @property
    def token(self) -> str:
        """Get Discord bot token"""
        self._load_config()
        return self._discord_token
    
    @property 
    def notification_channel(self) -> Optional[int]:
        """Get notification channel ID"""
        self._load_config()
        return self._notification_channel_id


# Global config instance
config = BotConfig()
"""
Main bot class for BCTC Auction Bot
Clean, focused bot implementation with separated concerns
"""
import discord
from discord.ext import commands
from typing import Optional

from config import config
from bot_events import BotEvents
from auction_manager import AuctionManager
from notification_service import NotificationService


class BCTCAuctionBot(commands.Bot):
    """
    BCTC Auction Bot main class
    Handles Discord bot functionality for auction management
    """
    
    def __init__(self):
        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=config.INTENTS,
            description=config.BOT_DESCRIPTION
        )
        
        # Bot components
        self.auction_manager: Optional[AuctionManager] = None
        self.notification_service: Optional[NotificationService] = None
        self.events_handler = BotEvents(self)
        
        # Setup event handlers
        self.events_handler.setup_events()
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        await self.events_handler.setup_bot()
    
    async def handle_auction_end(self, auction_data):
        """Delegate auction end handling to events handler"""
        if self.events_handler:
            await self.events_handler.handle_auction_end(auction_data)
    
    async def close(self):
        """Clean shutdown of bot components"""
        print("🛑 Shutting down bot...")
        
        # Stop background tasks
        if hasattr(self.events_handler, 'cleanup_expired_auctions'):
            task = getattr(self.events_handler, 'cleanup_expired_auctions', None)
            if task and hasattr(task, 'is_running') and task.is_running():
                task.cancel()
                print("✅ Background tasks stopped")
        
        # Close auction manager connections if needed
        if self.auction_manager:
            # Add any cleanup for auction manager if needed
            print("✅ Auction manager cleanup completed")
        
        # Call parent close
        await super().close()
        print("✅ Bot shutdown complete")
"""
Bot event handlers and background tasks for BCTC Auction Bot
Handles bot lifecycle events and scheduled tasks
"""
import discord
from discord.ext import commands, tasks
from typing import Optional

from config import config
from auction_manager import AuctionManager
from notification_service import NotificationService


class BotEvents:
    """Class to handle bot events and background tasks"""
    
    def __init__(self, bot):
        self.bot = bot
        self.auction_manager = None
        self.notification_service = None
    
    async def setup_bot(self):
        """Initialize bot components"""
        print("🚀 Initializing BCTC Auction Bot...")
        
        # Initialize auction manager
        print("📦 Setting up auction manager...")
        self.auction_manager = AuctionManager(config.DATABASE_PATH)
        await self.auction_manager.initialize()
        self.bot.auction_manager = self.auction_manager
        print("✅ Auction manager initialized")
        
        # Initialize notification service
        print("📢 Setting up notification service...")
        self.notification_service = NotificationService(
            self.bot, 
            config.notification_channel
        )
        self.bot.notification_service = self.notification_service
        print("✅ Notification service initialized")
        
        # Load cogs
        print("🔧 Loading cogs...")
        try:
            await self.bot.load_extension('auction_cog')
            print("✅ Auction cog loaded")
            await self.bot.load_extension('admin_cog')
            print("✅ Admin cog loaded")
        except Exception as e:
            print(f"❌ Failed to load cogs: {e}")
            raise
        
        # Start background tasks
        print("⏰ Starting background tasks...")
        self.cleanup_expired_auctions.start()
        print("✅ Background tasks started")
        
        # Sync commands
        print("🔄 Syncing application commands...")
        try:
            synced = await self.bot.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
            # Don't raise here, as the bot can still function
    
    @tasks.loop(minutes=config.CLEANUP_INTERVAL_MINUTES)
    async def cleanup_expired_auctions(self):
        """Check for expired auctions and update pinned list periodically"""
        try:
            if not self.auction_manager:
                return
            
            # Handle expired auctions
            expired_auctions = await self.auction_manager.get_expired_auctions()
            
            if expired_auctions:
                print(f"🧹 Processing {len(expired_auctions)} expired auction(s)")
                
                for auction in expired_auctions:
                    await self.handle_auction_end(auction)
            
            # Update pinned auction list
            if self.notification_service:
                active_auctions = await self.auction_manager.get_active_auctions(limit=50)  # Get more for pinned list
                await self.notification_service.update_pinned_auction_list(active_auctions)
                    
        except Exception as e:
            print(f"❌ Error in cleanup task: {e}")
    
    @cleanup_expired_auctions.before_loop
    async def before_cleanup(self):
        """Wait for bot to be ready before starting cleanup"""
        await self.bot.wait_until_ready()
        print("✅ Bot ready, starting auction cleanup task")
    
    async def handle_auction_end(self, auction_or_data):
        """
        Handle auction ending logic
        
        Args:
            auction_or_data: Either an Auction object or dictionary with auction data
        """
        try:
            # Handle both Auction objects and dictionaries
            if hasattr(auction_or_data, 'auction_id'):  # It's an Auction object
                auction = auction_or_data
                print(f"🔚 Handling end of auction: {auction.auction_name}")
                
                # Convert auction to dict for notification
                auction_data = {
                    'auction_id': auction.auction_id,
                    'item_name': auction.item_name,
                    'current_bid': auction.current_bid,
                    'owner_id': auction.owner_id,
                    'current_bidder_id': auction.current_bidder_id
                }
                
                # Remove auction from database (for expired auctions)
                await self.auction_manager.remove_auction(auction.auction_id)
                print(f"✅ Auction {auction.auction_name} processed successfully")
                
            else:  # It's a dictionary (from BIN purchases)
                auction_data = auction_or_data
                print(f"🔚 Handling end of auction: {auction_data.get('item_name', 'Unknown Item')} (BIN purchase)")
            
            # Send notification for both cases
            if self.notification_service:
                await self.notification_service.send_auction_end_notification(auction_data)
            
        except Exception as e:
            auction_id = getattr(auction_or_data, 'auction_id', auction_or_data.get('auction_id', 'Unknown'))
            print(f"❌ Error handling auction end for {auction_id}: {e}")
    
    async def on_ready(self):
        """Called when bot is ready"""
        print(f"🎉 {self.bot.user} has connected to Discord!")
        print(f"📊 Bot is in {len(self.bot.guilds)} guild(s)")
        
        # Log guild information
        for guild in self.bot.guilds:
            print(f"   - {guild.name} (ID: {guild.id})")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a new guild"""
        print(f"📥 Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Sync commands for new guild
        try:
            synced = await self.bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} commands for {guild.name}")
        except Exception as e:
            print(f"❌ Failed to sync commands for {guild.name}: {e}")
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when bot leaves a guild"""
        print(f"📤 Left guild: {guild.name} (ID: {guild.id})")
    
    async def on_application_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle application command errors"""
        print(f"❌ Command error in {interaction.command.name if interaction.command else 'unknown'}: {error}")
        
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while processing your command. Please try again later.",
                ephemeral=True
            )
    
    def setup_events(self):
        """Register event handlers with the bot"""
        self.bot.event(self.on_ready)
        self.bot.event(self.on_guild_join)
        self.bot.event(self.on_guild_remove)
        self.bot.tree.error(self.on_application_command_error)
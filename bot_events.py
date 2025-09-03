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
from monitoring import logger, metrics_collector
from notification_preferences import NotificationPreferencesManager, NotificationScheduler
from bid_sniping_protection import BidSnipingProtector, BidSnipingAnalyzer
from health_check import HealthCheckManager


class BotEvents:
    """Class to handle bot events and background tasks"""
    
    def __init__(self, bot):
        self.bot = bot
        self.auction_manager = None
        self.notification_service = None
        self.notification_preferences = None
        self.notification_scheduler = None
        self.bid_sniping_protector = None
        self.bid_sniping_analyzer = None
        self.health_check_manager = None
    
    async def setup_bot(self):
        """Initialize bot components"""
        logger.info("🚀 Initializing BCTC Auction Bot...")
        
        # Initialize auction manager
        logger.info("📦 Setting up auction manager...")
        self.auction_manager = AuctionManager(config.DATABASE_PATH)
        await self.auction_manager.initialize()
        self.bot.auction_manager = self.auction_manager
        logger.info("✅ Auction manager initialized")
        
        # Initialize notification service
        logger.info("📢 Setting up notification service...")
        self.notification_service = NotificationService(
            self.bot, 
            config.notification_channel
        )
        self.bot.notification_service = self.notification_service
        logger.info("✅ Notification service initialized")
        
        # Initialize notification preferences
        logger.info("🔔 Setting up notification preferences...")
        self.notification_preferences = NotificationPreferencesManager(config.DATABASE_PATH)
        await self.notification_preferences.initialize()
        self.bot.notification_preferences = self.notification_preferences
        logger.info("✅ Notification preferences initialized")
        
        # Initialize notification scheduler
        self.notification_scheduler = NotificationScheduler(self.notification_preferences)
        self.bot.notification_scheduler = self.notification_scheduler
        
        # Initialize bid sniping protection
        if config.BID_SNIPING_PROTECTION_ENABLED:
            logger.info("🛡️ Setting up bid sniping protection...")
            self.bid_sniping_protector = BidSnipingProtector(
                self.auction_manager, 
                self.notification_service
            )
            self.bid_sniping_analyzer = BidSnipingAnalyzer()
            self.bot.bid_sniping_protector = self.bid_sniping_protector
            self.bot.bid_sniping_analyzer = self.bid_sniping_analyzer
            logger.info("✅ Bid sniping protection initialized")
        
        # Initialize health check manager
        logger.info("🩺 Setting up health monitoring...")
        self.health_check_manager = HealthCheckManager(self.bot)
        self.bot.health_check_manager = self.health_check_manager
        logger.info("✅ Health monitoring initialized")
        
        # Setup Discord log channel if configured
        if config.log_channel:
            try:
                log_channel = self.bot.get_channel(config.log_channel)
                if log_channel:
                    logger.set_discord_channel(log_channel)
                    logger.info("✅ Discord logging channel configured")
            except Exception as e:
                logger.warning(f"Failed to setup Discord logging channel: {e}")
        
        # Load cogs
        logger.info("🔧 Loading cogs...")
        try:
            await self.bot.load_extension('auction_cog')
            logger.info("✅ Auction cog loaded")
            await self.bot.load_extension('admin_cog')
            logger.info("✅ Admin cog loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load cogs: {e}")
            raise
        
        # Start background tasks
        logger.info("⏰ Starting background tasks...")
        self.cleanup_expired_auctions.start()
        self.notification_scheduler_task.start()
        await self.health_check_manager.start_health_monitoring()
        logger.info("✅ Background tasks started")
        
        # Sync commands
        logger.info("🔄 Syncing application commands...")
        try:
            synced = await self.bot.tree.sync()
            logger.info(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")
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
                logger.info(f"🧹 Processing {len(expired_auctions)} expired auction(s)")
                metrics_collector.record_gauge('expired_auctions_processed', len(expired_auctions))
                
                for auction in expired_auctions:
                    await self.handle_auction_end(auction)
            
            # Update pinned auction list
            if self.notification_service:
                active_auctions = await self.auction_manager.get_active_auctions(limit=50)  # Get more for pinned list
                await self.notification_service.update_pinned_auction_list(active_auctions)
            
            # Cleanup old bid sniping records
            if self.bid_sniping_protector:
                await self.bid_sniping_protector.cleanup_old_extensions()
            
            # Record metrics
            metrics_collector.record_counter('cleanup_task_completed')
                    
        except Exception as e:
            logger.error(f"❌ Error in cleanup task: {e}")
            metrics_collector.record_counter('cleanup_task_errors')
    
    @cleanup_expired_auctions.before_loop
    async def before_cleanup(self):
        """Wait for bot to be ready before starting cleanup"""
        await self.bot.wait_until_ready()
        logger.info("✅ Bot ready, starting auction cleanup task")
    
    @tasks.loop(minutes=30)  # Run every 30 minutes
    async def notification_scheduler_task(self):
        """Schedule and send notification reminders"""
        try:
            if not self.notification_scheduler or not self.auction_manager:
                return
            
            # Schedule auction ending warnings
            await self.notification_scheduler.schedule_auction_ending_warnings(
                self.auction_manager, 
                self.notification_service
            )
            
            metrics_collector.record_counter('notification_scheduler_completed')
            
        except Exception as e:
            logger.error(f"❌ Error in notification scheduler: {e}")
            metrics_collector.record_counter('notification_scheduler_errors')
    
    @notification_scheduler_task.before_loop
    async def before_notification_scheduler(self):
        """Wait for bot to be ready before starting notification scheduler"""
        await self.bot.wait_until_ready()
        logger.info("✅ Bot ready, starting notification scheduler task")
    
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
                logger.info(f"🔚 Handling end of auction: {auction.auction_name}")
                
                # Analyze bidding pattern if bid sniping analyzer is available
                if self.bid_sniping_analyzer:
                    pattern_analysis = self.bid_sniping_analyzer.analyze_auction_pattern(
                        auction.auction_id, 
                        auction.end_time
                    )
                    logger.info(
                        f"Bidding pattern analysis for {auction.auction_id}",
                        pattern_analysis
                    )
                
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
                logger.info(f"✅ Auction {auction.auction_name} processed successfully")
                
            else:  # It's a dictionary (from BIN purchases)
                auction_data = auction_or_data
                logger.info(f"🔚 Handling end of auction: {auction_data.get('item_name', 'Unknown Item')} (BIN purchase)")
            
            # Send notification for both cases
            if self.notification_service:
                await self.notification_service.send_auction_end_notification(auction_data)
            
            # Record metrics
            metrics_collector.record_counter('auctions_ended')
            
        except Exception as e:
            auction_id = getattr(auction_or_data, 'auction_id', auction_or_data.get('auction_id', 'Unknown'))
            logger.error(f"❌ Error handling auction end for {auction_id}: {e}")
            metrics_collector.record_counter('auction_end_errors')
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"🎉 {self.bot.user} has connected to Discord!")
        logger.info(f"📊 Bot is in {len(self.bot.guilds)} guild(s)")
        
        # Log guild information
        for guild in self.bot.guilds:
            logger.info(f"   - {guild.name} (ID: {guild.id})")
        
        # Record metrics
        metrics_collector.record_gauge('guilds_connected', len(self.bot.guilds))
        metrics_collector.record_counter('bot_ready_events')
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a new guild"""
        logger.info(f"📥 Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Sync commands for new guild
        try:
            synced = await self.bot.tree.sync(guild=guild)
            logger.info(f"✅ Synced {len(synced)} commands for {guild.name}")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands for {guild.name}: {e}")
        
        # Update metrics
        metrics_collector.record_counter('guild_joins')
        metrics_collector.record_gauge('guilds_connected', len(self.bot.guilds))
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when bot leaves a guild"""
        logger.info(f"📤 Left guild: {guild.name} (ID: {guild.id})")
        
        # Update metrics
        metrics_collector.record_counter('guild_leaves')
        metrics_collector.record_gauge('guilds_connected', len(self.bot.guilds))
    
    async def on_application_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle application command errors"""
        command_name = interaction.command.name if interaction.command else 'unknown'
        logger.error(f"❌ Command error in {command_name}: {error}")
        
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while processing your command. Please try again later.",
                ephemeral=True
            )
        
        # Record metrics
        metrics_collector.record_counter('command_errors')
        metrics_collector.record_counter(f'command_errors_{command_name}')
    
    def setup_events(self):
        """Register event handlers with the bot"""
        self.bot.event(self.on_ready)
        self.bot.event(self.on_guild_join)
        self.bot.event(self.on_guild_remove)
        self.bot.tree.error(self.on_application_command_error)
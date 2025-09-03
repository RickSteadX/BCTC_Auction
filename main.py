#!/usr/bin/env python3
"""
BCTC Auction Bot - Main Entry Point
A Discord bot for managing Brawlhalla Code Trading Center auctions
"""
import asyncio
import signal
import sys

from bot import BCTCAuctionBot
from config import config
from monitoring import logger


def setup_signal_handlers(bot: BCTCAuctionBot):
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(bot.close())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point for the bot"""
    logger.info("🎮 BCTC Auction Bot - Starting Up")
    logger.info("=" * 40)
    
    try:
        # Validate configuration
        logger.info("🔧 Validating configuration...")
        token = config.token
        logger.info("✅ Configuration valid")
        
        # Create bot instance
        logger.info("🤖 Creating bot instance...")
        bot = BCTCAuctionBot()
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(bot)
        
        # Start the bot
        logger.info("🚀 Starting bot...")
        logger.info("=" * 40)
        
        async with bot:
            await bot.start(token)
            
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Setup instructions:")
        logger.info("1. Copy .env.example to .env")
        logger.info("2. Set DISCORD_BOT_TOKEN=your_bot_token")
        logger.info("3. Optionally set NOTIFICATION_CHANNEL_ID=your_channel_id")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
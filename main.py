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


def setup_signal_handlers(bot: BCTCAuctionBot):
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(bot.close())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point for the bot"""
    print("🎮 BCTC Auction Bot - Starting Up")
    print("=" * 40)
    
    try:
        # Validate configuration
        print("🔧 Validating configuration...")
        token = config.token
        print("✅ Configuration valid")
        
        # Create bot instance
        print("🤖 Creating bot instance...")
        bot = BCTCAuctionBot()
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(bot)
        
        # Start the bot
        print("🚀 Starting bot...")
        print("=" * 40)
        
        async with bot:
            await bot.start(token)
            
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\n💡 Setup instructions:")
        print("1. Copy .env.example to .env")
        print("2. Set DISCORD_BOT_TOKEN=your_bot_token")
        print("3. Optionally set NOTIFICATION_CHANNEL_ID=your_channel_id")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
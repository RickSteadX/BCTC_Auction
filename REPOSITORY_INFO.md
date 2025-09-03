# AUC_BCTC Repository Information

## Repository Name: AUC_BCTC
**Full Name**: Auction BCTC - Brawlhalla Code Trading Center Bot

## Project Overview
A sophisticated Discord bot designed for managing auctions within the Brawlhalla Code Trading Center (BCTC) community. This bot provides a complete auction ecosystem with modern Discord UI components and automated management features.

## Key Features Implemented

### 🏷️ Core Auction System
- **Interactive Auction Creation**: Modal-based forms with validation
- **Real-time Bidding**: 10% minimum bid increments
- **Buy-It-Now (BIN)**: Instant purchase with confirmation
- **Auction Management**: Edit, withdraw, and monitor personal auctions
- **Automated Expiration**: Background task handling

### 🔔 Advanced Notifications
- **Pinned Auction List**: Auto-updating pinned message in notification channel
- **DM Notifications**: Private messages to sellers and buyers when auctions end
- **Public Announcements**: Channel notifications for auction completion
- **Real-time Updates**: Live status updates every minute

### 👨‍💼 Admin Features
- **10-Second Testing Timer**: Admin-only quick auction duration for testing
- **Permission Validation**: Secure admin feature access
- **Enhanced Controls**: Additional management capabilities

### 🏗️ Technical Architecture
- **Modular Design**: Separated concerns across multiple files
- **Async Operations**: Non-blocking database and Discord interactions
- **Error Handling**: Comprehensive validation and error recovery
- **Type Safety**: Modern Python typing and validation

## Technology Stack
- **Python 3.8+**: Core programming language
- **discord.py 2.3.2+**: Discord API wrapper with modern UI components
- **aiosqlite**: Asynchronous SQLite database operations
- **python-dotenv**: Environment variable management

## File Structure
```
AUC_BCTC/
├── main.py                  # Bot entry point and startup logic
├── bot.py                   # Main bot class definition
├── config.py                # Configuration management
├── bot_events.py            # Event handlers and background tasks
├── notification_service.py  # Notification system
├── auction_manager.py       # Database operations and auction logic
├── auction_cog.py           # Discord commands and UI interactions
├── requirements.txt         # Python dependencies
├── .env.example            # Configuration template
├── .gitignore              # Git ignore rules
└── README.md               # Project documentation
```

## Development History
- **Initial Development**: Complete auction bot implementation
- **Feature Enhancement**: Added pinned lists, DM notifications, admin features
- **Repository Creation**: Established AUC_BCTC git repository

## Usage
1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment: Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN`
3. Run bot: `python main.py`

## Commands
- `/create` - Create new auction with modal form
- `/auctions` - Browse active auctions with pagination
- `/myauctions` - Manage personal auctions

---
*Repository created for BCTC community Discord auction management*
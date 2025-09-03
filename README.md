# BCTC Auction Bot

A Discord bot for managing Brawlhalla Code Trading Center auctions with advanced Discord UI features.

## Features

### Core Functionality
- **Auction Creation**: `/create` command with modal interface and rate limiting
- **Auction Browsing**: `/auctions` command with paginated inline button navigation
- **Auction Management**: `/myauctions` command for managing your own auctions
- **Real-time Bidding**: Interactive bid system with 10% minimum increments and anti-abuse protection
- **Buy-It-Now**: Instant purchase option with confirmation modal
- **Automatic Expiration**: Background task handling auction timeouts
- **Notifications**: Automatic notifications when auctions end

### Advanced Discord Features
- **Modals**: Rich form interfaces for auction creation and bidding
- **Select Menus**: Dropdown selection for auction duration and browsing
- **Interactive Buttons**: Bid, BIN, navigation, and management buttons  
- **Embeds**: Beautiful, information-rich auction displays
- **Ephemeral Messages**: Private responses for user interactions
- **Discord Timestamps**: Dynamic time formatting with relative timestamps

### Admin & Security Features
- **Admin Commands**: Comprehensive management tools for administrators
- **Abuse Prevention**: Rate limiting, bid validation, and spam protection
- **User Investigation**: Detailed user activity reports and statistics
- **Auction Control**: Force end, extend time, or audit specific auctions
- **System Monitoring**: Real-time statistics and health metrics
- **Security Checks**: Permission validation and ownership verification

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- Discord Application with Bot Token
- Appropriate Discord permissions for your bot

### 2. Installation

```bash
# Clone or download the project files
cd BCTC_Auction

# Install required packages
pip install -r requirements.txt
```

### 3. Configuration

1. Create a copy of `.env.example` and name it `.env`
2. Set your Discord bot token:
   ```
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   ```
3. (Optional) Set a notification channel ID for auction end notifications:
   ```
   NOTIFICATION_CHANNEL_ID=your_channel_id_here
   ```

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token to your `.env` file
4. Invite the bot to your server with these permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History
   - Add Reactions

### 5. Running the Bot

```bash
python main.py
```

## Bot Commands

### User Commands

### `/create`
Opens a modal to create a new auction with the following fields:
- **Item Name** (required): The item contained in the code
- **Quantity** (required): Number of items
- **Auction Name** (optional): Custom name (defaults to item name)
- **Description** (optional): Auction description  
- **BIN Price** (optional): Buy-It-Now price

After submitting, select duration: 1h, 12h, 24h, 3 days, or 7 days.

**Rate Limiting:**
- Maximum 5 active auctions per user
- Maximum 3 new auctions per hour (admins exempt)

### `/auctions`
Displays all active auctions in a paginated list with:
- Navigation buttons for browsing pages
- Select dropdown to view individual auctions
- Real-time bid information and time remaining

### `/myauctions`
Shows your active auctions with management options:
- Edit auction name and description
- Withdraw auctions
- View current status and bids

### Admin Commands

### `/admin_auctions`
**[ADMIN ONLY]** Comprehensive auction management interface:
- View all active auctions with detailed information
- Administrative controls for each auction
- Force end, extend time, or audit specific auctions
- Block users (planned feature)

### `/admin_stats`
**[ADMIN ONLY]** System statistics and monitoring:
- Active auction count and total value
- Unique seller and bidder counts
- BIN auction statistics
- Real-time system health metrics

### `/admin_user <user>`
**[ADMIN ONLY]** User activity investigation:
- View user's active auctions and bidding history
- Account age and server join information
- Auction value analysis
- Abuse detection insights

### `/admin_cleanup`
**[ADMIN ONLY]** Force cleanup of expired auctions:
- Manually trigger auction expiration processing
- Detailed cleanup statistics
- Error reporting for failed cleanups

## Auction Flow

### Creation Process
1. User runs `/create` command
2. Modal appears with auction details form
3. User selects duration from dropdown
4. Auction is created and added to active list

### Bidding Process  
1. Users browse auctions via `/auctions`
2. Select an auction to view details
3. Click "💰 Place Bid" to submit a bid (10% minimum increment)
4. Or click "🎯 Buy It Now" for instant purchase (if available)

### Auction Ending
- Automatic expiration based on duration
- BIN purchases end auction immediately
- Notifications sent to designated channel
- Winner and seller are mentioned in final notification

## Database

The bot uses SQLite (`auctions.db`) to store:
- Auction details and metadata
- Current bids and bidder information
- Auction status and timestamps

## File Structure

```
BCTC_Auction/
├── main.py                  # Bot entry point and startup logic
├── bot.py                   # Main bot class definition
├── config.py                # Configuration management and environment variables
├── bot_events.py            # Event handlers and background tasks
├── notification_service.py  # Auction notification system
├── auction_manager.py       # Database operations and auction logic
├── auction_cog.py           # Discord commands and UI interactions
├── admin_cog.py             # Admin commands and management tools
├── requirements.txt         # Python dependencies
├── .env.example            # Configuration template
├── test_refactored.py      # Refactoring validation script
└── README.md               # This file
```

## Error Handling

The bot includes comprehensive error handling for:
- Invalid bid amounts
- Permission checks (users can't bid on own auctions)
- Database operations
- Discord API interactions
- Auction state validation

## Security Features

- Users cannot bid on their own auctions
- Users cannot BIN their own auctions  
- Auction ownership verification for management actions
- Input validation for all user inputs
- Ephemeral messages for sensitive operations

## Customization

You can modify the following in the code:
- Minimum bid increment percentage (currently 10%)
- Minimum bid amount (currently $0.50)
- Auction duration options
- Embed colors and styling
- Notification channel behavior

## Troubleshooting

### Common Issues

1. **Bot not responding to commands**
   - Ensure bot has proper permissions
   - Check if commands are synced (restart bot)
   - Verify bot token is correct

2. **Database errors**  
   - Ensure write permissions in bot directory
   - Check if `auctions.db` is corrupted (delete to reset)

3. **Missing notifications**
   - Set `NOTIFICATION_CHANNEL_ID` in `.env`
   - Ensure bot has permissions in notification channel

### Logs
The bot prints important information to console including:
- Command sync status
- Database initialization
- Auction expiration processing
- Error messages

## Development Notes

This bot uses modern Discord.py features including:
- Application commands (slash commands)
- Views and UI components  
- Modal forms
- Select menus
- Interactive buttons
- Embed builders

The architecture is modular with clear separation between:
- Bot startup and configuration (`main.py`, `config.py`)
- Event handling and background tasks (`bot_events.py`)
- Core bot functionality (`bot.py`)
- Notification system (`notification_service.py`)
- Data management (`auction_manager.py`)  
- User interface (`auction_cog.py`)

## License

This project is provided as-is for BCTC use. Modify as needed for your community.
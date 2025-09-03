"""
Pytest configuration and fixtures for BCTC Auction Bot tests
"""
import pytest
import pytest_asyncio
import asyncio
import sys
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock
from auction_manager import AuctionManager

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def auction_manager():
    """Create initialized auction manager for tests"""
    # Use a temporary file instead of :memory: to avoid isolation issues
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name
    
    try:
        manager = AuctionManager(db_path)
        await manager.initialize()
        yield manager
    finally:
        # Clean up
        try:
            os.unlink(db_path)
        except (OSError, FileNotFoundError):
            pass

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_bot():
    """Mock Discord bot instance"""
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)
    bot.get_user = MagicMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    return bot

@pytest.fixture
def mock_guild():
    """Mock Discord guild"""
    guild = MagicMock()
    guild.id = 12345
    guild.owner_id = 99999
    guild.name = "Test Guild"
    return guild

@pytest.fixture
def mock_user():
    """Mock Discord user"""
    user = MagicMock()
    user.id = 11111
    user.display_name = "TestUser"
    user.guild_permissions.administrator = False
    return user

@pytest.fixture
def mock_admin_user():
    """Mock Discord admin user"""
    user = MagicMock()
    user.id = 22222
    user.display_name = "AdminUser"
    user.guild_permissions.administrator = True
    return user

@pytest.fixture
def mock_interaction(mock_user, mock_guild):
    """Mock Discord interaction"""
    interaction = MagicMock()
    interaction.user = mock_user
    interaction.guild = mock_guild
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction
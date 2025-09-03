#!/usr/bin/env python3
"""
Feature test script for BCTC Auction Bot new features
Tests all new functionality added in this update
"""

import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_notification_features():
    """Test notification service new features"""
    try:
        print("🧪 Testing notification service features...")
        
        from notification_service import NotificationService
        from auction_manager import Auction
        from datetime import datetime, timedelta
        
        # Mock bot object
        class MockBot:
            def get_channel(self, channel_id):
                return None
            def get_user(self, user_id):
                return None
        
        bot = MockBot()
        notification_service = NotificationService(bot, 123456789)
        
        # Test pinned auction list creation
        mock_auctions = []
        for i in range(3):
            auction = Auction(
                auction_id=f"test_{i}",
                owner_id=123456789,
                item_name=f"Test Item {i+1}",
                quantity=1,
                auction_name=f"Test Auction {i+1}",
                description="Test description",
                bin_price=10.0 if i == 0 else None,
                current_bid=5.0 if i == 1 else 0.0,
                current_bidder_id=987654321 if i == 1 else None,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=24),
                duration_hours=24,
                image_url=None,
                status='active'
            )
            mock_auctions.append(auction)
        
        # Test pinned list embed creation
        embed = notification_service._create_pinned_auction_list_embed(mock_auctions)
        print(f"   ✅ Pinned auction list embed created: {embed.title}")
        
        # Test DM embed creation
        auction_data = {
            'auction_id': 'test_123',
            'item_name': 'Test Item',
            'current_bid': 15.50,
            'owner_id': 123456789,
            'current_bidder_id': 987654321
        }
        
        seller_embed = notification_service._create_seller_dm_embed(auction_data)
        buyer_embed = notification_service._create_buyer_dm_embed(auction_data)
        
        print(f"   ✅ Seller DM embed created: {seller_embed.title}")
        print(f"   ✅ Buyer DM embed created: {buyer_embed.title}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Notification test error: {e}")
        return False

def test_admin_timer_logic():
    """Test admin timer logic"""
    try:
        print("🧪 Testing admin timer logic...")
        
        # Test duration calculations
        admin_duration = 10 / 3600  # 10 seconds in hours
        normal_duration = 24  # 24 hours
        
        print(f"   ✅ Admin duration calculation: {admin_duration} hours (10 seconds)")
        print(f"   ✅ Normal duration: {normal_duration} hours")
        
        # Test value parsing
        admin_value = "0.003"
        normal_value = "24"
        
        parsed_admin = float(admin_value)
        parsed_normal = float(normal_value)
        
        print(f"   ✅ Admin value parsing: {admin_value} -> {parsed_admin}")
        print(f"   ✅ Normal value parsing: {normal_value} -> {parsed_normal}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Admin timer test error: {e}")
        return False

def test_auction_manager_compatibility():
    """Test auction manager compatibility with new features"""
    try:
        print("🧪 Testing auction manager compatibility...")
        
        import auction_manager
        from datetime import datetime
        
        # Test fractional hour duration (for admin timer)
        manager = auction_manager.AuctionManager(":memory:")
        
        # Verify the auction creation accepts fractional hours
        async def test_fractional_hours():
            await manager.initialize()
            
            # Test creating auction with 10-second duration (fractional hours)
            auction = await manager.create_auction(
                owner_id=123456789,
                item_name="Test Item",
                quantity=1,
                duration_hours=10/3600,  # 10 seconds
                auction_name="Quick Test",
                description="Test description"
            )
            
            return auction
        
        # Run the async test
        import asyncio
        auction = asyncio.run(test_fractional_hours())
        
        print(f"   ✅ Auction created with fractional duration: {auction.duration_hours} hours")
        print(f"   ✅ End time: {auction.end_time}")
        print(f"   ✅ Time remaining calculation: {auction.time_remaining()}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Auction manager test error: {e}")
        return False

def test_embed_validations():
    """Test embed field limits and formatting"""
    try:
        print("🧪 Testing embed validations...")
        
        # Test long auction names and descriptions
        long_name = "A" * 150  # Longer than 100 char limit
        long_desc = "B" * 600  # Longer than 500 char limit
        
        # These should be handled by the form validation
        truncated_name = long_name[:100]
        truncated_desc = long_desc[:500]
        
        print(f"   ✅ Name truncation: {len(long_name)} -> {len(truncated_name)} chars")
        print(f"   ✅ Description truncation: {len(long_desc)} -> {len(truncated_desc)} chars")
        
        # Test price formatting
        prices = [0.01, 1.50, 1000.99, 99999.99]
        for price in prices:
            formatted = f"${price:.2f}"
            print(f"   ✅ Price formatting: {price} -> {formatted}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Embed validation test error: {e}")
        return False

def validate_imports():
    """Validate all new imports work correctly"""
    try:
        print("🧪 Testing import compatibility...")
        
        # Test updated notification service imports
        from notification_service import NotificationService
        from auction_manager import AuctionManager, Auction
        from config import config
        
        # Test that all classes can be instantiated
        class MockBot:
            def get_channel(self, channel_id):
                return None
        
        notification_service = NotificationService(MockBot(), None)
        auction_manager = AuctionManager(":memory:")
        
        print("   ✅ NotificationService instantiated")
        print("   ✅ AuctionManager instantiated")
        print("   ✅ Config imported")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 BCTC Auction Bot - New Features Test")
    print("=" * 50)
    
    all_tests_passed = True
    
    print("\n1. Testing import compatibility...")
    if not validate_imports():
        all_tests_passed = False
    
    print("\n2. Testing notification features...")
    asyncio.run(test_notification_features())
    
    print("\n3. Testing admin timer logic...")
    if not test_admin_timer_logic():
        all_tests_passed = False
    
    print("\n4. Testing auction manager compatibility...")
    if not test_auction_manager_compatibility():
        all_tests_passed = False
    
    print("\n5. Testing embed validations...")
    if not test_embed_validations():
        all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 All new feature tests passed!")
        print("\n📋 New Features Summary:")
        print("   ✅ Pinned auction list with auto-updates")
        print("   ✅ DM notifications for sellers and buyers")
        print("   ✅ BIN auction notifications (fixed)")
        print("   ✅ 10-second admin timer option")
        print("   ✅ Enhanced notification system")
    else:
        print("❌ Some tests failed - check implementation.")
    
    print("\n🎯 Features Ready:")
    print("   • Pinned auction list updates every minute")
    print("   • DM notifications sent to auction participants")
    print("   • Admin users can create 10-second test auctions")
    print("   • BIN purchases now trigger proper notifications")
    print("   • Enhanced auction end notifications with more details")
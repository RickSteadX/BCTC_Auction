"""
User notification preferences system for BCTC Auction Bot
Manages customizable notification settings for users
"""
import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from config import config
from monitoring import logger, metrics_collector, get_performance_timer


@dataclass
class NotificationPreference:
    """User notification preference setting"""
    user_id: int
    preference_type: str
    enabled: bool
    settings: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data


class NotificationPreferencesManager:
    """Manages user notification preferences"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def initialize(self):
        """Initialize the notification preferences database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    user_id INTEGER,
                    preference_type TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    settings TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, preference_type)
                )
            """)
            
            # Create indexes for better query performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_preferences_user_id 
                ON notification_preferences(user_id)
            """)
            
            await db.commit()
            logger.info("Notification preferences database initialized")
    
    async def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get all notification preferences for a user"""
        with get_performance_timer("get_user_preferences"):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT preference_type, enabled, settings FROM notification_preferences WHERE user_id = ?",
                        (user_id,)
                    ) as cursor:
                        rows = await cursor.fetchall()
                
                # Start with default preferences
                preferences = config.NOTIFICATION_PREFERENCES_DEFAULT.copy()
                
                # Override with user's custom settings
                for row in rows:
                    preference_type, enabled, settings_json = row
                    preferences[preference_type] = enabled
                    
                    # If there are additional settings, merge them
                    if settings_json:
                        try:
                            settings = json.loads(settings_json)
                            if isinstance(settings, dict):
                                # Merge settings into preference name with underscore
                                for key, value in settings.items():
                                    preferences[f"{preference_type}_{key}"] = value
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in notification settings for user {user_id}, preference {preference_type}")
                
                metrics_collector.record_counter("notification_preferences_retrieved")
                return preferences
                
            except Exception as e:
                logger.error(f"Failed to get notification preferences for user {user_id}: {e}")
                metrics_collector.record_counter("notification_preferences_errors")
                return config.NOTIFICATION_PREFERENCES_DEFAULT.copy()
    
    async def update_user_preference(
        self, 
        user_id: int, 
        preference_type: str, 
        enabled: bool, 
        settings: Dict[str, Any] = None
    ) -> bool:
        """Update a specific notification preference for a user"""
        with get_performance_timer("update_user_preference"):
            try:
                current_time = datetime.now().isoformat()
                settings_json = json.dumps(settings) if settings else None
                
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO notification_preferences 
                        (user_id, preference_type, enabled, settings, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 
                                COALESCE((SELECT created_at FROM notification_preferences 
                                         WHERE user_id = ? AND preference_type = ?), ?), 
                                ?)
                    """, (
                        user_id, preference_type, enabled, settings_json,
                        user_id, preference_type, current_time, current_time
                    ))
                    await db.commit()
                
                logger.info(
                    f"Updated notification preference for user {user_id}",
                    {"preference_type": preference_type, "enabled": enabled}
                )
                metrics_collector.record_counter("notification_preferences_updated")
                return True
                
            except Exception as e:
                logger.error(
                    f"Failed to update notification preference for user {user_id}: {e}",
                    {"preference_type": preference_type, "enabled": enabled}
                )
                metrics_collector.record_counter("notification_preferences_update_errors")
                return False
    
    async def bulk_update_preferences(self, user_id: int, preferences: Dict[str, Any]) -> bool:
        """Update multiple notification preferences for a user"""
        with get_performance_timer("bulk_update_preferences"):
            try:
                current_time = datetime.now().isoformat()
                
                async with aiosqlite.connect(self.db_path) as db:
                    for preference_type, enabled in preferences.items():
                        if preference_type in config.NOTIFICATION_PREFERENCES_DEFAULT:
                            await db.execute("""
                                INSERT OR REPLACE INTO notification_preferences 
                                (user_id, preference_type, enabled, settings, created_at, updated_at)
                                VALUES (?, ?, ?, NULL, 
                                        COALESCE((SELECT created_at FROM notification_preferences 
                                                 WHERE user_id = ? AND preference_type = ?), ?), 
                                        ?)
                            """, (
                                user_id, preference_type, enabled,
                                user_id, preference_type, current_time, current_time
                            ))
                    
                    await db.commit()
                
                logger.info(f"Bulk updated notification preferences for user {user_id}")
                metrics_collector.record_counter("notification_preferences_bulk_updated")
                return True
                
            except Exception as e:
                logger.error(f"Failed to bulk update notification preferences for user {user_id}: {e}")
                metrics_collector.record_counter("notification_preferences_bulk_update_errors")
                return False
    
    async def should_send_notification(self, user_id: int, notification_type: str) -> bool:
        """Check if a notification should be sent to a user"""
        preferences = await self.get_user_preferences(user_id)
        return preferences.get(notification_type, True)  # Default to True if not found
    
    async def get_users_with_preference(self, preference_type: str, enabled: bool = True) -> List[int]:
        """Get all users who have a specific preference enabled/disabled"""
        with get_performance_timer("get_users_with_preference"):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT user_id FROM notification_preferences WHERE preference_type = ? AND enabled = ?",
                        (preference_type, enabled)
                    ) as cursor:
                        rows = await cursor.fetchall()
                
                return [row[0] for row in rows]
                
            except Exception as e:
                logger.error(f"Failed to get users with preference {preference_type}: {e}")
                return []
    
    async def cleanup_old_preferences(self, days_old: int = 90) -> int:
        """Clean up old, unused notification preferences"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM notification_preferences WHERE updated_at < ?",
                    (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                await db.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old notification preferences")
                metrics_collector.record_counter("notification_preferences_cleaned", deleted_count)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old notification preferences: {e}")
            return 0


class NotificationScheduler:
    """Schedules and manages notification delivery"""
    
    def __init__(self, preferences_manager: NotificationPreferencesManager):
        self.preferences_manager = preferences_manager
        self.pending_notifications: List[Dict[str, Any]] = []
        
    async def schedule_auction_ending_warnings(self, auction_manager, notification_service):
        """Schedule warnings for auctions ending soon"""
        try:
            active_auctions = await auction_manager.get_active_auctions(limit=100)
            current_time = datetime.now()
            
            for auction in active_auctions:
                time_remaining = auction.end_time - current_time
                minutes_remaining = time_remaining.total_seconds() / 60
                
                # Check if we should send an ending warning
                if 30 <= minutes_remaining <= 60:  # 30-60 minutes remaining
                    await self._send_auction_ending_warning(auction, notification_service)
                    
        except Exception as e:
            logger.error(f"Failed to schedule auction ending warnings: {e}")
    
    async def _send_auction_ending_warning(self, auction, notification_service):
        """Send auction ending warning to interested users"""
        try:
            # Check seller preference
            seller_preferences = await self.preferences_manager.get_user_preferences(auction.owner_id)
            if seller_preferences.get('auction_ending_warning', True):
                # Send warning to seller
                await notification_service.send_auction_ending_warning(auction, auction.owner_id)
            
            # Check current bidder preference (if any)
            if auction.current_bidder_id:
                bidder_preferences = await self.preferences_manager.get_user_preferences(auction.current_bidder_id)
                if bidder_preferences.get('auction_ending_warning', True):
                    await notification_service.send_auction_ending_warning(auction, auction.current_bidder_id)
                    
            metrics_collector.record_counter("auction_ending_warnings_sent")
            
        except Exception as e:
            logger.error(f"Failed to send auction ending warning for auction {auction.auction_id}: {e}")
    
    async def notify_bid_outbid(self, auction, previous_bidder_id, notification_service):
        """Notify user when they've been outbid"""
        if not previous_bidder_id:
            return
            
        try:
            preferences = await self.preferences_manager.get_user_preferences(previous_bidder_id)
            if preferences.get('bid_outbid_notification', True):
                await notification_service.send_outbid_notification(auction, previous_bidder_id)
                metrics_collector.record_counter("outbid_notifications_sent")
                
        except Exception as e:
            logger.error(f"Failed to send outbid notification: {e}")
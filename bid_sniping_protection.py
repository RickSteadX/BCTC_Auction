"""
Bid sniping protection system for BCTC Auction Bot
Extends auction time when bids are placed in the final minutes
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from config import config
from monitoring import logger, metrics_collector, get_performance_timer


@dataclass
class BidSnipingEvent:
    """Data structure for bid sniping events"""
    auction_id: str
    bidder_id: int
    bid_amount: float
    time_remaining_minutes: float
    extended: bool = False
    extension_minutes: int = 0


class BidSnipingProtector:
    """Manages bid sniping protection for auctions"""
    
    def __init__(self, auction_manager, notification_service):
        self.auction_manager = auction_manager
        self.notification_service = notification_service
        self.recent_extensions: Dict[str, datetime] = {}  # Track recent extensions
        
    async def handle_bid_placed(
        self, 
        auction_id: str, 
        bidder_id: int, 
        bid_amount: float
    ) -> Optional[BidSnipingEvent]:
        """
        Handle a bid placement and check for sniping protection
        Returns BidSnipingEvent if protection was triggered
        """
        if not config.BID_SNIPING_PROTECTION_ENABLED:
            return None
            
        with get_performance_timer("bid_sniping_check"):
            try:
                auction = await self.auction_manager.get_auction(auction_id)
                if not auction or auction.status != 'active':
                    return None
                
                current_time = datetime.now()
                time_remaining = auction.end_time - current_time
                minutes_remaining = time_remaining.total_seconds() / 60
                
                # Create bid sniping event record
                sniping_event = BidSnipingEvent(
                    auction_id=auction_id,
                    bidder_id=bidder_id,
                    bid_amount=bid_amount,
                    time_remaining_minutes=minutes_remaining
                )
                
                # Check if bid was placed in the sniping window
                if minutes_remaining <= config.BID_SNIPING_WINDOW_MINUTES:
                    logger.info(
                        f"Bid placed in sniping window for auction {auction_id}",
                        {
                            "bidder_id": bidder_id,
                            "bid_amount": bid_amount,
                            "minutes_remaining": minutes_remaining,
                            "sniping_window": config.BID_SNIPING_WINDOW_MINUTES
                        }
                    )
                    
                    # Check if we should extend the auction
                    if await self._should_extend_auction(auction_id, current_time):
                        extended = await self._extend_auction(auction_id, config.BID_SNIPING_EXTENSION_MINUTES)
                        
                        if extended:
                            sniping_event.extended = True
                            sniping_event.extension_minutes = config.BID_SNIPING_EXTENSION_MINUTES
                            
                            # Record the extension
                            self.recent_extensions[auction_id] = current_time
                            
                            # Notify about the extension
                            await self._notify_auction_extended(auction, sniping_event)
                            
                            metrics_collector.record_counter("bid_sniping_extensions")
                            logger.info(
                                f"Auction {auction_id} extended due to bid sniping protection",
                                {"extension_minutes": config.BID_SNIPING_EXTENSION_MINUTES}
                            )
                
                metrics_collector.record_counter("bid_sniping_checks")
                return sniping_event
                
            except Exception as e:
                logger.error(f"Error in bid sniping protection for auction {auction_id}: {e}")
                metrics_collector.record_counter("bid_sniping_errors")
                return None
    
    async def _should_extend_auction(self, auction_id: str, current_time: datetime) -> bool:
        """
        Determine if an auction should be extended
        Prevents multiple extensions in a short period
        """
        # Check if auction was recently extended
        last_extension = self.recent_extensions.get(auction_id)
        if last_extension:
            time_since_extension = current_time - last_extension
            if time_since_extension.total_seconds() < config.BID_SNIPING_EXTENSION_COOLDOWN_SECONDS:  # Configurable cooldown
                logger.debug(f"Auction {auction_id} not extended - recent extension within cooldown")
                return False
        
        return True
    
    async def _extend_auction(self, auction_id: str, extension_minutes: int) -> bool:
        """Extend an auction by the specified number of minutes"""
        try:
            # Use the auction manager's extend_auction method if it exists
            if hasattr(self.auction_manager, 'extend_auction'):
                return await self.auction_manager.extend_auction(auction_id, extension_minutes / 60)
            else:
                # Fallback: manually update the auction end time
                auction = await self.auction_manager.get_auction(auction_id)
                if auction:
                    new_end_time = auction.end_time + timedelta(minutes=extension_minutes)
                    new_duration = auction.duration_hours + (extension_minutes / 60)
                    
                    # Update the auction in the database
                    success = await self._update_auction_end_time(auction_id, new_end_time, new_duration)
                    return success
                    
            return False
            
        except Exception as e:
            logger.error(f"Failed to extend auction {auction_id}: {e}")
            return False
    
    async def _update_auction_end_time(self, auction_id: str, new_end_time: datetime, new_duration: float) -> bool:
        """Update auction end time in database"""
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.auction_manager.db_path) as db:
                await db.execute(
                    "UPDATE auctions SET end_time = ?, duration_hours = ? WHERE auction_id = ?",
                    (new_end_time.isoformat(), new_duration, auction_id)
                )
                await db.commit()
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to update auction end time for {auction_id}: {e}")
            return False
    
    async def _notify_auction_extended(self, auction, sniping_event: BidSnipingEvent):
        """Send notifications about auction extension"""
        try:
            # Notify the auction owner
            if self.notification_service:
                await self.notification_service.send_auction_extension_notification(
                    auction, sniping_event
                )
            
            # Log to monitoring
            logger.info(
                f"Auction extension notification sent for auction {auction.auction_id}",
                {
                    "owner_id": auction.owner_id,
                    "bidder_id": sniping_event.bidder_id,
                    "extension_minutes": sniping_event.extension_minutes
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to send auction extension notification: {e}")
    
    async def cleanup_old_extensions(self, hours_old: int = 24):
        """Clean up old extension records"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_old)
            
            # Remove old extension records
            old_extensions = [
                auction_id for auction_id, extension_time in self.recent_extensions.items()
                if extension_time < cutoff_time
            ]
            
            for auction_id in old_extensions:
                del self.recent_extensions[auction_id]
            
            if old_extensions:
                logger.debug(f"Cleaned up {len(old_extensions)} old extension records")
                
        except Exception as e:
            logger.error(f"Error cleaning up old extension records: {e}")
    
    def get_sniping_statistics(self) -> Dict[str, Any]:
        """Get statistics about bid sniping protection"""
        metrics = metrics_collector.get_metrics_summary()
        
        return {
            "protection_enabled": config.BID_SNIPING_PROTECTION_ENABLED,
            "sniping_window_minutes": config.BID_SNIPING_WINDOW_MINUTES,
            "extension_minutes": config.BID_SNIPING_EXTENSION_MINUTES,
            "total_checks": metrics['counters'].get('bid_sniping_checks', 0),
            "total_extensions": metrics['counters'].get('bid_sniping_extensions', 0),
            "total_errors": metrics['counters'].get('bid_sniping_errors', 0),
            "active_extensions": len(self.recent_extensions),
            "extension_success_rate": self._calculate_success_rate(metrics)
        }
    
    def _calculate_success_rate(self, metrics: Dict[str, Any]) -> float:
        """Calculate bid sniping protection success rate"""
        checks = metrics['counters'].get('bid_sniping_checks', 0)
        errors = metrics['counters'].get('bid_sniping_errors', 0)
        
        if checks == 0:
            return 100.0
            
        return ((checks - errors) / checks) * 100.0


class BidSnipingAnalyzer:
    """Analyzes bidding patterns to detect potential sniping attempts"""
    
    def __init__(self):
        self.bid_patterns: Dict[str, list] = {}  # auction_id -> list of bid timestamps
        
    def record_bid(self, auction_id: str, bidder_id: int, timestamp: datetime):
        """Record a bid for pattern analysis"""
        if auction_id not in self.bid_patterns:
            self.bid_patterns[auction_id] = []
            
        self.bid_patterns[auction_id].append({
            'bidder_id': bidder_id,
            'timestamp': timestamp,
            'minute_remaining': None  # Will be calculated when auction ends
        })
    
    def analyze_auction_pattern(self, auction_id: str, auction_end_time: datetime) -> Dict[str, Any]:
        """Analyze bidding pattern for an auction after it ends"""
        if auction_id not in self.bid_patterns:
            return {"pattern_type": "no_bids"}
            
        bids = self.bid_patterns[auction_id]
        
        # Calculate minutes remaining for each bid
        for bid in bids:
            time_remaining = auction_end_time - bid['timestamp']
            bid['minutes_remaining'] = time_remaining.total_seconds() / 60
        
        # Analyze pattern
        late_bids = [bid for bid in bids if bid['minutes_remaining'] <= 5]
        very_late_bids = [bid for bid in bids if bid['minutes_remaining'] <= 1]
        
        pattern_analysis = {
            "total_bids": len(bids),
            "late_bids_count": len(late_bids),
            "very_late_bids_count": len(very_late_bids),
            "sniping_detected": len(very_late_bids) > 0,
            "pattern_type": self._classify_pattern(bids, late_bids, very_late_bids),
            "bid_distribution": self._analyze_bid_distribution(bids)
        }
        
        # Clean up old data
        del self.bid_patterns[auction_id]
        
        return pattern_analysis
    
    def _classify_pattern(self, all_bids: list, late_bids: list, very_late_bids: list) -> str:
        """Classify the bidding pattern"""
        if len(all_bids) == 0:
            return "no_bids"
        elif len(very_late_bids) > 0:
            return "sniping_detected"
        elif len(late_bids) > len(all_bids) * config.LATE_BIDS_THRESHOLD:
            return "last_minute_rush"
        elif len(all_bids) > 10:
            return "competitive_bidding"
        else:
            return "normal_bidding"
    
    def _analyze_bid_distribution(self, bids: list) -> Dict[str, int]:
        """Analyze the distribution of bids over time"""
        distribution = {
            "first_hour": 0,
            "mid_auction": 0,
            "last_hour": 0,
            "last_15_minutes": 0,
            "last_5_minutes": 0
        }
        
        for bid in bids:
            minutes_remaining = bid.get('minutes_remaining', 0)
            
            if minutes_remaining <= 5:
                distribution["last_5_minutes"] += 1
            elif minutes_remaining <= 15:
                distribution["last_15_minutes"] += 1
            elif minutes_remaining <= 60:
                distribution["last_hour"] += 1
            elif minutes_remaining >= (24 * 60 - 60):  # First hour of 24h auction
                distribution["first_hour"] += 1
            else:
                distribution["mid_auction"] += 1
        
        return distribution
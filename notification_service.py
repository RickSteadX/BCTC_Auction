"""
Notification service module for BCTC Auction Bot
Handles auction end notifications, messaging, and pinned auction lists
"""
import discord
from typing import Dict, Any, Optional, List
from auction_manager import Auction
from monitoring import logger, metrics_collector, get_performance_timer


class NotificationService:
    """Service class for handling notifications"""
    
    def __init__(self, bot: discord.Client, notification_channel_id: Optional[int] = None):
        self.bot = bot
        self.notification_channel_id = notification_channel_id
        self.pinned_message_id: Optional[int] = None  # Store the pinned auction list message ID
    
    async def send_auction_end_notification(self, auction_data: Dict[str, Any]) -> bool:
        """Send notification when an auction ends"""
        try:
            # Send public notification
            public_sent = await self._send_public_auction_end_notification(auction_data)
            
            # Send DM notifications
            await self._send_dm_notifications_for_auction_end(auction_data)
            
            return public_sent
            
        except Exception as e:
            print(f"Error in auction end notification process: {e}")
            return False
    
    async def _send_public_auction_end_notification(self, auction_data: Dict[str, Any]) -> bool:
        """Send public notification to the notification channel"""
        try:
            if not self.notification_channel_id:
                print("No notification channel configured, skipping notification")
                return False
                
            channel = self.bot.get_channel(self.notification_channel_id)
            if not channel or not hasattr(channel, 'send'):
                print(f"Notification channel not found or invalid: {self.notification_channel_id}")
                return False
            
            embed = self._create_auction_end_embed(auction_data)
            await channel.send(embed=embed)
            
            print(f"Auction end notification sent for: {auction_data.get('item_name', 'Unknown Item')}")
            return True
            
        except Exception as e:
            print(f"Error sending public auction end notification: {e}")
            return False
    
    async def _send_dm_notifications_for_auction_end(self, auction_data: Dict[str, Any]):
        """Send DM notifications to seller and buyer"""
        try:
            seller_id = auction_data.get('owner_id')
            buyer_id = auction_data.get('current_bidder_id')
            
            # Send notification to seller
            if seller_id:
                seller_embed = self._create_seller_dm_embed(auction_data)
                await self.send_dm_notification(seller_id, seller_embed)
            
            # Send notification to buyer (if there was one)
            if buyer_id and buyer_id != seller_id:
                buyer_embed = self._create_buyer_dm_embed(auction_data)
                await self.send_dm_notification(buyer_id, buyer_embed)
                
        except Exception as e:
            print(f"Error sending DM notifications: {e}")
    
    async def send_auction_created_notification(self, auction: Auction) -> bool:
        """
        Send notification when a new auction is created
        
        Args:
            auction: Auction object
            
        Returns:
            bool: True if notification was sent successfully
        """
        try:
            if not self.notification_channel_id:
                return False
                
            channel = self.bot.get_channel(self.notification_channel_id)
            if not channel or not hasattr(channel, 'send'):
                return False
            
            embed = self._create_auction_created_embed(auction)
            await channel.send(embed=embed)
            
            print(f"New auction notification sent: {auction.auction_name}")
            return True
            
        except Exception as e:
            print(f"Error sending auction created notification: {e}")
            return False
    
    def _create_auction_end_embed(self, auction_data: Dict[str, Any]) -> discord.Embed:
        """Create embed for auction end notification"""
        has_winner = auction_data.get('current_bid', 0) > 0
        
        embed = discord.Embed(
            title="🔨 Auction Ended",
            description=f"**{auction_data.get('item_name', 'Unknown Item')}** auction has ended!",
            color=0x00ff00 if has_winner else 0xff6b6b
        )
        
        # Add auction details
        embed.add_field(
            name="📦 Item", 
            value=auction_data.get('item_name', 'Unknown'), 
            inline=True
        )
        
        final_price = auction_data.get('current_bid', 0)
        embed.add_field(
            name="💰 Final Price", 
            value=f"${final_price:.2f}" if final_price > 0 else "No bids", 
            inline=True
        )
        
        embed.add_field(
            name="👤 Seller", 
            value=f"<@{auction_data.get('owner_id', 0)}>", 
            inline=True
        )
        
        # Add winner if there was a bid
        if auction_data.get('current_bidder_id'):
            embed.add_field(
                name="🏆 Winner", 
                value=f"<@{auction_data.get('current_bidder_id')}>", 
                inline=True
            )
            embed.add_field(name="📈 Status", value="**SOLD**", inline=True)
        else:
            embed.add_field(name="📈 Status", value="**UNSOLD**", inline=True)
        
        # Add timestamp
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=f"Auction ID: {auction_data.get('auction_id', 'Unknown')}")
        
        return embed
    
    def _create_auction_created_embed(self, auction: Auction) -> discord.Embed:
        """Create embed for new auction notification"""
        embed = discord.Embed(
            title="🆕 New Auction Created",
            description=f"**{auction.auction_name}** is now live!",
            color=0x00d4aa
        )
        
        embed.add_field(name="📦 Item", value=auction.item_name, inline=True)
        embed.add_field(name="🔢 Quantity", value=str(auction.quantity), inline=True)
        embed.add_field(name="👤 Seller", value=f"<@{auction.owner_id}>", inline=True)
        
        if auction.bin_price:
            embed.add_field(name="🎯 BIN Price", value=f"${auction.bin_price:.2f}", inline=True)
        
        embed.add_field(
            name="⏰ Ends", 
            value=f"<t:{int(auction.end_time.timestamp())}:R>", 
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Duration", 
            value=f"{auction.duration_hours} hours", 
            inline=True
        )
        
        if auction.description:
            embed.add_field(name="📝 Description", value=auction.description, inline=False)
        
        # Add image if provided
        if auction.image_url:
            embed.set_image(url=auction.image_url)
        
        embed.timestamp = auction.start_time
        embed.set_footer(text=f"Use /auctions to view and bid • ID: {auction.auction_id}")
        
        return embed
    
    def set_notification_channel(self, channel_id: int):
        """Update the notification channel ID"""
        self.notification_channel_id = channel_id
    
    async def send_dm_notification(self, user_id: int, embed: discord.Embed) -> bool:
        """Send a DM notification to a user"""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                user = await self.bot.fetch_user(user_id)
            
            await user.send(embed=embed)
            print(f"DM notification sent to user {user_id}")
            return True
            
        except discord.Forbidden:
            print(f"Cannot send DM to user {user_id} - DMs disabled or not mutual")
            return False
        except Exception as e:
            print(f"Error sending DM to user {user_id}: {e}")
            return False
    
    async def update_pinned_auction_list(self, auctions: List[Auction]) -> bool:
        """Update the auction list message by deleting and re-sending (without pinning)"""
        try:
            if not self.notification_channel_id:
                return False
                
            channel = self.bot.get_channel(self.notification_channel_id)
            if not channel or not hasattr(channel, 'send'):
                return False
            
            embed = self._create_pinned_auction_list_embed(auctions)
            
            # Delete existing message if it exists
            if self.pinned_message_id:
                try:
                    old_message = await channel.fetch_message(self.pinned_message_id)
                    await old_message.delete()
                    print(f"Deleted old auction list message: {self.pinned_message_id}")
                except discord.NotFound:
                    # Message was already deleted, that's fine
                    pass
                except Exception as e:
                    print(f"Error deleting old message: {e}")
                    # Continue anyway, we'll create a new one
                
                # Reset the stored message ID
                self.pinned_message_id = None
            
            # Create new message (without pinning)
            message = await channel.send(embed=embed)
            
            # Store the message ID for future deletion
            self.pinned_message_id = message.id
            print(f"Created new auction list message: {message.id}")
            return True
                
        except Exception as e:
            print(f"Error updating auction list: {e}")
            return False
    
    def _create_pinned_auction_list_embed(self, auctions: List[Auction]) -> discord.Embed:
        """Create embed for auction list (no buttons)"""
        embed = discord.Embed(
            title="📋 Active Auctions List",
            description="Live auction status (updates every minute)",
            color=0x0099ff
        )
        
        if not auctions:
            embed.add_field(
                name="No Active Auctions", 
                value="Use `/create` to start an auction!", 
                inline=False
            )
            embed.set_footer(text="🔄 Updates automatically")
            return embed
        
        # Sort auctions by time remaining (soonest first)
        sorted_auctions = sorted(auctions, key=lambda a: a.end_time)
        
        auction_lines = []
        for i, auction in enumerate(sorted_auctions[:10]):  # Limit to 10 auctions
            time_left = auction.time_remaining()
            current_bid = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            bin_info = f" | BIN: ${auction.bin_price:.2f}" if auction.bin_price else ""
            
            auction_lines.append(
                f"**{i+1}.** {auction.auction_name}\n"
                f"└ {auction.item_name} | {current_bid}{bin_info} | {time_left}"
            )
        
        embed.add_field(
            name=f"📋 {len(sorted_auctions)} Active Auction{'s' if len(sorted_auctions) != 1 else ''}",
            value="\n\n".join(auction_lines),
            inline=False
        )
        
        if len(sorted_auctions) > 10:
            embed.add_field(
                name="📝 Note", 
                value=f"Showing first 10 of {len(sorted_auctions)} auctions. Use `/auctions` to see all.",
                inline=False
            )
        
        embed.set_footer(text=f"🔄 Last updated: {discord.utils.format_dt(discord.utils.utcnow(), 'T')} | Use /auctions to bid | Updates every minute")
        
        return embed
    
    def _create_seller_dm_embed(self, auction_data: Dict[str, Any]) -> discord.Embed:
        """Create DM embed for auction seller"""
        has_winner = auction_data.get('current_bid', 0) > 0
        
        embed = discord.Embed(
            title="📧 Your Auction Has Ended",
            description=f"Your auction for **{auction_data.get('item_name', 'Unknown Item')}** has concluded!",
            color=0x00ff00 if has_winner else 0xff6b6b
        )
        
        final_price = auction_data.get('current_bid', 0)
        embed.add_field(
            name="💰 Final Sale Price", 
            value=f"${final_price:.2f}" if final_price > 0 else "No bids received", 
            inline=True
        )
        
        if auction_data.get('current_bidder_id'):
            embed.add_field(
                name="🏆 Winning Buyer", 
                value=f"<@{auction_data.get('current_bidder_id')}>", 
                inline=True
            )
            embed.add_field(
                name="📝 Next Steps", 
                value="Please coordinate with the buyer to complete the trade!", 
                inline=False
            )
        else:
            embed.add_field(
                name="😢 Result", 
                value="Your auction ended without any bids. Consider adjusting your pricing or duration for future auctions.", 
                inline=False
            )
        
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=f"Auction ID: {auction_data.get('auction_id', 'Unknown')}")
        
        return embed
    
    def _create_buyer_dm_embed(self, auction_data: Dict[str, Any]) -> discord.Embed:
        """Create DM embed for auction winner"""
        embed = discord.Embed(
            title="🎉 Congratulations! You Won the Auction",
            description=f"You've successfully won the auction for **{auction_data.get('item_name', 'Unknown Item')}**!",
            color=0x00ff00
        )
        
        final_price = auction_data.get('current_bid', 0)
        embed.add_field(
            name="💰 Your Winning Bid", 
            value=f"${final_price:.2f}", 
            inline=True
        )
        
        embed.add_field(
            name="👤 Seller", 
            value=f"<@{auction_data.get('owner_id', 0)}>", 
            inline=True
        )
        
        embed.add_field(
            name="📝 Next Steps", 
            value="Please contact the seller to arrange payment and code delivery. Be sure to follow BCTC trading guidelines!", 
            inline=False
        )
        
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=f"Auction ID: {auction_data.get('auction_id', 'Unknown')}")
        
        return embed
    
    async def send_auction_ending_warning(self, auction: Auction, user_id: int) -> bool:
        """Send warning that auction is ending soon"""
        try:
            embed = discord.Embed(
                title="⏰ Auction Ending Soon!",
                description=f"The auction for **{auction.item_name}** is ending in less than 1 hour!",
                color=0xffaa00
            )
            
            embed.add_field(name="📦 Item", value=auction.item_name, inline=True)
            embed.add_field(name="💰 Current Bid", value=f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids", inline=True)
            embed.add_field(name="⏰ Time Left", value=auction.time_remaining(), inline=True)
            
            if auction.bin_price:
                embed.add_field(name="🎯 BIN Price", value=f"${auction.bin_price:.2f}", inline=True)
            
            embed.add_field(name="🏁 Ends", value=f"<t:{int(auction.end_time.timestamp())}:R>", inline=True)
            embed.set_footer(text=f"Auction ID: {auction.auction_id}")
            
            await self.send_dm_notification(user_id, embed)
            metrics_collector.record_counter("auction_ending_warnings_sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send auction ending warning: {e}")
            return False
    
    async def send_outbid_notification(self, auction: Auction, user_id: int) -> bool:
        """Send notification when user has been outbid"""
        try:
            embed = discord.Embed(
                title="💔 You've Been Outbid!",
                description=f"Someone has placed a higher bid on **{auction.item_name}**.",
                color=0xff6b6b
            )
            
            embed.add_field(name="📦 Item", value=auction.item_name, inline=True)
            embed.add_field(name="💰 New High Bid", value=f"${auction.current_bid:.2f}", inline=True)
            embed.add_field(name="⏰ Time Left", value=auction.time_remaining(), inline=True)
            
            min_bid = max(config.MIN_BID_AMOUNT, auction.current_bid * (1 + config.MIN_BID_INCREMENT))
            embed.add_field(name="💡 Minimum Bid", value=f"${min_bid:.2f}", inline=True)
            
            if auction.bin_price:
                embed.add_field(name="🎯 BIN Price", value=f"${auction.bin_price:.2f}", inline=True)
            
            embed.add_field(name="🏁 Ends", value=f"<t:{int(auction.end_time.timestamp())}:R>", inline=True)
            embed.set_footer(text=f"Use /auctions to place a new bid • ID: {auction.auction_id}")
            
            await self.send_dm_notification(user_id, embed)
            metrics_collector.record_counter("outbid_notifications_sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send outbid notification: {e}")
            return False
    
    async def send_auction_extension_notification(self, auction: Auction, sniping_event) -> bool:
        """Send notification about auction extension due to bid sniping protection"""
        try:
            if not self.notification_channel_id:
                return False
                
            channel = self.bot.get_channel(self.notification_channel_id)
            if not channel or not hasattr(channel, 'send'):
                return False
            
            embed = discord.Embed(
                title="🛡️ Auction Extended - Bid Sniping Protection",
                description=f"Auction for **{auction.item_name}** has been extended!",
                color=0x0099ff
            )
            
            embed.add_field(name="📦 Item", value=auction.item_name, inline=True)
            embed.add_field(name="💰 Current Bid", value=f"${sniping_event.bid_amount:.2f}", inline=True)
            embed.add_field(name="👤 Bidder", value=f"<@{sniping_event.bidder_id}>", inline=True)
            
            embed.add_field(
                name="⏰ Extension", 
                value=f"+{sniping_event.extension_minutes} minutes", 
                inline=True
            )
            
            embed.add_field(
                name="🕐 Time Remaining", 
                value=f"{sniping_event.time_remaining_minutes:.1f} minutes when bid placed", 
                inline=True
            )
            
            embed.add_field(name="🏁 New End Time", value=f"<t:{int(auction.end_time.timestamp())}:R>", inline=True)
            
            embed.set_footer(text=f"Auction ID: {auction.auction_id}")
            
            await channel.send(embed=embed)
            
            # Also send DM to auction owner
            owner_embed = discord.Embed(
                title="🛡️ Your Auction Has Been Extended",
                description=f"Your auction for **{auction.item_name}** was extended due to a late bid.",
                color=0x0099ff
            )
            owner_embed.add_field(name="💰 New Bid", value=f"${sniping_event.bid_amount:.2f}", inline=True)
            owner_embed.add_field(name="⏰ Extension", value=f"+{sniping_event.extension_minutes} minutes", inline=True)
            owner_embed.set_footer(text=f"Auction ID: {auction.auction_id}")
            
            await self.send_dm_notification(auction.owner_id, owner_embed)
            
            metrics_collector.record_counter("auction_extension_notifications_sent")
            logger.info(f"Auction extension notification sent for {auction.auction_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send auction extension notification: {e}")
            return False
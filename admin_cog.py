"""
Admin tools for BCTC Auction Bot
Provides management and abuse prevention features for administrators
"""
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Union
import asyncio
import json
from datetime import datetime, timedelta
from auction_manager import AuctionManager, Auction
from monitoring import logger, metrics_collector, get_performance_timer
from config import config


def is_admin():
    """Check if user has administrator permissions or is server owner"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user is server owner
        if hasattr(interaction, 'guild') and interaction.guild:
            if interaction.guild.owner_id == interaction.user.id:
                return True
        
        # Check if user has administrator permissions
        if interaction.user.guild_permissions.administrator:
            return True
            
        # If neither, send helpful error message
        await interaction.response.send_message(
            "❌ **Access Denied**\n"
            "You need administrator permissions or server ownership to use admin commands.\n"
            f"Your permissions: `{interaction.user.guild_permissions.value}`\n"
            "Use `/admin_test` to check your admin status.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)


class AdminAuctionListView(discord.ui.View):
    """Admin view for managing auctions with enhanced controls"""
    
    def __init__(self, auctions: List[Auction], page: int = 0):
        super().__init__(timeout=config.VIEW_TIMEOUT_SECONDS)
        self.auctions = auctions
        self.page = page
        self.per_page = 5
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "admin_prev_page":
                    item.disabled = self.page <= 0
                elif item.custom_id == "admin_next_page":
                    item.disabled = self.page >= total_pages - 1
    
    def get_page_auctions(self) -> List[Auction]:
        """Get auctions for current page"""
        start = self.page * self.per_page
        end = start + self.per_page
        return self.auctions[start:end]
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="admin_prev_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            embed = self.create_admin_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary, custom_id="admin_next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        if self.page < total_pages - 1:
            self.page += 1
            self.update_buttons()
            embed = self.create_admin_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.select(placeholder="Select an auction to manage...")
    async def auction_admin_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        auction_id = select.values[0]
        bot = interaction.client
        auction = await bot.auction_manager.get_auction(auction_id)
        
        if auction:
            view = AdminAuctionControlView(auction)
            embed = view.create_admin_control_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Auction not found.",
                ephemeral=True
            )
    
    def create_admin_list_embed(self) -> discord.Embed:
        """Create admin auction list embed"""
        embed = discord.Embed(
            title="🛡️ Admin Auction Management",
            description="Administrative control panel for active auctions",
            color=0xff6b35
        )
        
        page_auctions = self.get_page_auctions()
        if not page_auctions:
            embed.description = "No active auctions found."
            return embed
        
        # Update select menu options
        options = []
        for auction in page_auctions:
            time_left = auction.time_remaining()
            bid_text = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            owner_text = f"Owner: <@{auction.owner_id}>"
            
            options.append(discord.SelectOption(
                label=auction.auction_name[:50],  # Truncate for readability
                description=f"{bid_text} | {time_left} | {owner_text}"[:100],
                value=auction.auction_id
            ))
        
        # Update select menu
        select = self.children[2]  # The select menu is the third child
        select.options = options
        
        # Add auction details to embed
        for i, auction in enumerate(page_auctions):
            time_left = auction.time_remaining()
            current_bid = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            bin_info = f" (BIN: ${auction.bin_price:.2f})" if auction.bin_price else ""
            
            embed.add_field(
                name=f"{i+1}. {auction.auction_name}",
                value=(
                    f"**Owner:** <@{auction.owner_id}>\n"
                    f"**Item:** {auction.item_name}\n"
                    f"**Current Bid:** {current_bid}{bin_info}\n"
                    f"**Time Left:** {time_left}\n"
                    f"**ID:** `{auction.auction_id[:8]}...`"
                ),
                inline=False
            )
        
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • Total Auctions: {len(self.auctions)}")
        
        return embed


class AdminAuctionControlView(discord.ui.View):
    """Individual auction control view for admins"""
    
    def __init__(self, auction: Auction):
        super().__init__(timeout=config.VIEW_TIMEOUT_SECONDS)
        self.auction = auction
    
    @discord.ui.button(label="🛑 Force End", style=discord.ButtonStyle.danger)
    async def force_end_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Force end an auction immediately"""
        modal = ForceEndConfirmationModal(self.auction)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⏰ Extend Time", style=discord.ButtonStyle.primary)
    async def extend_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Extend auction duration"""
        modal = ExtendAuctionModal(self.auction)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🚫 Block User", style=discord.ButtonStyle.secondary)
    async def block_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Block the auction owner from creating new auctions"""
        await interaction.response.send_message(
            f"⚠️ **User Blocking Feature**\n"
            f"Would you like to block <@{self.auction.owner_id}> from creating auctions?\n"
            f"*This feature requires database schema update to implement user blocking.*",
            ephemeral=True
        )
    
    @discord.ui.button(label="📊 Audit Log", style=discord.ButtonStyle.success)
    async def audit_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed audit information"""
        embed = self.create_audit_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def create_admin_control_embed(self) -> discord.Embed:
        """Create admin control embed"""
        embed = discord.Embed(
            title=f"🛡️ Admin Control: {self.auction.auction_name}",
            description="Administrative controls for this auction",
            color=0xff6b35
        )
        
        # Auction details
        embed.add_field(name="📦 Item", value=self.auction.item_name, inline=True)
        embed.add_field(name="🔢 Quantity", value=str(self.auction.quantity), inline=True)
        embed.add_field(name="👤 Owner", value=f"<@{self.auction.owner_id}>", inline=True)
        
        # Financial details
        current_bid = f"${self.auction.current_bid:.2f}" if self.auction.current_bid > 0 else "No bids"
        embed.add_field(name="💰 Current Bid", value=current_bid, inline=True)
        if self.auction.bin_price:
            embed.add_field(name="🎯 BIN Price", value=f"${self.auction.bin_price:.2f}", inline=True)
        if self.auction.current_bidder_id:
            embed.add_field(name="🏆 Top Bidder", value=f"<@{self.auction.current_bidder_id}>", inline=True)
        
        # Time information
        embed.add_field(name="⏰ Time Left", value=self.auction.time_remaining(), inline=True)
        embed.add_field(name="📅 Started", value=f"<t:{int(self.auction.start_time.timestamp())}:R>", inline=True)
        embed.add_field(name="🏁 Ends", value=f"<t:{int(self.auction.end_time.timestamp())}:R>", inline=True)
        
        # Admin info
        embed.add_field(name="🆔 Auction ID", value=f"`{self.auction.auction_id}`", inline=False)
        
        return embed
    
    def create_audit_embed(self) -> discord.Embed:
        """Create detailed audit information embed"""
        embed = discord.Embed(
            title=f"📊 Audit Report: {self.auction.auction_name}",
            description="Detailed auction information for administrative review",
            color=0x4a90e2
        )
        
        # Basic information
        embed.add_field(name="🆔 Full Auction ID", value=f"`{self.auction.auction_id}`", inline=False)
        embed.add_field(name="👤 Owner ID", value=f"`{self.auction.owner_id}`", inline=True)
        embed.add_field(name="📦 Item Name", value=self.auction.item_name, inline=True)
        embed.add_field(name="🔢 Quantity", value=str(self.auction.quantity), inline=True)
        
        # Financial audit
        embed.add_field(name="💰 Current Bid", value=f"${self.auction.current_bid:.2f}", inline=True)
        embed.add_field(name="🏆 Bidder ID", value=f"`{self.auction.current_bidder_id}`" if self.auction.current_bidder_id else "None", inline=True)
        embed.add_field(name="🎯 BIN Price", value=f"${self.auction.bin_price:.2f}" if self.auction.bin_price else "Not set", inline=True)
        
        # Time audit
        embed.add_field(name="📅 Start Time", value=f"<t:{int(self.auction.start_time.timestamp())}:F>", inline=False)
        embed.add_field(name="🏁 End Time", value=f"<t:{int(self.auction.end_time.timestamp())}:F>", inline=False)
        embed.add_field(name="⏱️ Duration", value=f"{self.auction.duration_hours} hours", inline=True)
        embed.add_field(name="📊 Status", value=self.auction.status.title(), inline=True)
        embed.add_field(name="⏰ Remaining", value=self.auction.time_remaining(), inline=True)
        
        # Additional info
        if self.auction.description:
            embed.add_field(name="📝 Description", value=self.auction.description[:200] + "..." if len(self.auction.description) > 200 else self.auction.description, inline=False)
        
        embed.timestamp = datetime.now()
        embed.set_footer(text="Admin Audit Report • Confidential")
        
        return embed


class ForceEndConfirmationModal(discord.ui.Modal):
    """Confirmation modal for force ending an auction"""
    
    def __init__(self, auction: Auction):
        super().__init__(title='Force End Auction')
        self.auction = auction
        
        self.reason = discord.ui.TextInput(
            label='Reason for Force Ending',
            placeholder='Enter reason for administrative action...',
            required=True,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        
        self.confirmation = discord.ui.TextInput(
            label=f'Type "FORCE END" to confirm',
            placeholder='Type exactly: FORCE END',
            required=True,
            max_length=20
        )
        
        self.add_item(self.reason)
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.strip().upper() != "FORCE END":
            await interaction.response.send_message(
                "❌ Confirmation text incorrect. Please type exactly: FORCE END",
                ephemeral=True
            )
            return
        
        try:
            bot = interaction.client
            
            # End the auction
            await bot.auction_manager.end_auction(self.auction.auction_id)
            
            # Create audit log embed
            embed = discord.Embed(
                title="🛑 Auction Force Ended",
                description=f"Auction **{self.auction.auction_name}** has been force ended by admin.",
                color=0xff4444
            )
            embed.add_field(name="Admin", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="Reason", value=self.reason.value, inline=False)
            embed.add_field(name="Original Owner", value=f"<@{self.auction.owner_id}>", inline=True)
            embed.add_field(name="Final Bid", value=f"${self.auction.current_bid:.2f}" if self.auction.current_bid > 0 else "No bids", inline=True)
            embed.timestamp = datetime.now()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Trigger auction end handling
            await bot.handle_auction_end(self.auction)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to force end auction: {str(e)}",
                ephemeral=True
            )


class ExtendAuctionModal(discord.ui.Modal):
    """Modal for extending auction duration"""
    
    def __init__(self, auction: Auction):
        super().__init__(title='Extend Auction Duration')
        self.auction = auction
        
        self.hours = discord.ui.TextInput(
            label='Hours to Add',
            placeholder='Enter number of hours to extend...',
            required=True,
            max_length=10
        )
        
        self.reason = discord.ui.TextInput(
            label='Reason for Extension',
            placeholder='Enter reason for administrative action...',
            required=True,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.hours)
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours_to_add = float(self.hours.value)
            if hours_to_add <= 0:
                raise ValueError("Hours must be positive")
            
            bot = interaction.client
            
            # Update auction in database using the new extend method
            success = await bot.auction_manager.extend_auction(self.auction.auction_id, hours_to_add)
            
            if not success:
                await interaction.response.send_message(
                    "❌ Failed to extend auction - auction not found.",
                    ephemeral=True
                )
                return
            
            # Calculate new end time for display
            new_end_time = self.auction.end_time + timedelta(hours=hours_to_add)
            
            embed = discord.Embed(
                title="⏰ Auction Extended",
                description=f"Auction **{self.auction.auction_name}** has been extended.",
                color=0x00ff00
            )
            embed.add_field(name="Admin", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="Extension", value=f"+{hours_to_add} hours", inline=True)
            embed.add_field(name="New End Time", value=f"<t:{int(new_end_time.timestamp())}:F>", inline=False)
            embed.add_field(name="Reason", value=self.reason.value, inline=False)
            embed.timestamp = datetime.now()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid hours value! Please enter a valid positive number.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to extend auction: {str(e)}",
                ephemeral=True
            )


class AdminCog(commands.Cog):
    """Admin commands for auction management and abuse prevention"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="admin_test", description="[ADMIN] Test admin permissions")
    async def admin_test(self, interaction: discord.Interaction):
        """Test command to check admin access without decorator"""
        # Manual permission check with detailed feedback
        is_owner = interaction.guild and interaction.guild.owner_id == interaction.user.id
        has_admin = interaction.user.guild_permissions.administrator
        
        embed = discord.Embed(
            title="🔧 Admin Permission Test",
            description="Checking your admin status...",
            color=0x00ff00 if (is_owner or has_admin) else 0xff0000
        )
        
        embed.add_field(name="Server Owner", value="✅ Yes" if is_owner else "❌ No", inline=True)
        embed.add_field(name="Administrator", value="✅ Yes" if has_admin else "❌ No", inline=True)
        embed.add_field(name="Access Level", value="🛡️ Admin" if (is_owner or has_admin) else "👤 User", inline=True)
        
        embed.add_field(name="User ID", value=f"`{interaction.user.id}`", inline=True)
        embed.add_field(name="Guild ID", value=f"`{interaction.guild.id if interaction.guild else 'None'}`", inline=True)
        embed.add_field(name="Owner ID", value=f"`{interaction.guild.owner_id if interaction.guild else 'None'}`", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="admin_sync", description="[ADMIN] Sync bot commands")
    async def admin_sync(self, interaction: discord.Interaction):
        """Manually sync bot commands - no permission check for troubleshooting"""
        try:
            synced = await self.bot.tree.sync()
            embed = discord.Embed(
                title="🔄 Commands Synced",
                description=f"Successfully synced {len(synced)} command(s) to Discord.",
                color=0x00ff00
            )
            
            # List synced commands
            command_list = [f"• {cmd.name}" for cmd in synced]
            if command_list:
                embed.add_field(
                    name="Synced Commands",
                    value="\n".join(command_list[:10]) + ("\n..." if len(command_list) > 10 else ""),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to sync commands: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_auctions", description="[ADMIN] View and manage all active auctions")
    @is_admin()
    async def admin_auctions(self, interaction: discord.Interaction):
        """Admin command to view and manage all auctions"""
        auctions = await self.bot.auction_manager.get_active_auctions(limit=50)
        
        if not auctions:
            embed = discord.Embed(
                title="🛡️ Admin Auction Management",
                description="No active auctions found.",
                color=0xff6b35
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = AdminAuctionListView(auctions)
        embed = view.create_admin_list_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="admin_stats", description="[ADMIN] View auction system statistics")
    @is_admin()
    async def admin_stats(self, interaction: discord.Interaction):
        """Show system statistics"""
        try:
            # Get statistics from database
            auction_manager = self.bot.auction_manager
            
            # Count active auctions
            active_auctions = await auction_manager.get_active_auctions(limit=1000)
            
            # Get recent activity (simplified - would need database schema changes for full tracking)
            embed = discord.Embed(
                title="📊 Auction System Statistics",
                description="Current system status and activity",
                color=0x4a90e2
            )
            
            embed.add_field(name="🏷️ Active Auctions", value=str(len(active_auctions)), inline=True)
            
            # Calculate total value
            total_value = sum(auction.current_bid for auction in active_auctions)
            embed.add_field(name="💰 Total Active Value", value=f"${total_value:.2f}", inline=True)
            
            # Count auctions with bids
            auctions_with_bids = len([a for a in active_auctions if a.current_bid > 0])
            embed.add_field(name="🎯 Auctions with Bids", value=str(auctions_with_bids), inline=True)
            
            # Count BIN auctions
            bin_auctions = len([a for a in active_auctions if a.bin_price])
            embed.add_field(name="⚡ BIN Auctions", value=str(bin_auctions), inline=True)
            
            # Unique sellers
            unique_sellers = len(set(auction.owner_id for auction in active_auctions))
            embed.add_field(name="👥 Active Sellers", value=str(unique_sellers), inline=True)
            
            # Unique bidders
            unique_bidders = len(set(auction.current_bidder_id for auction in active_auctions if auction.current_bidder_id))
            embed.add_field(name="🏆 Active Bidders", value=str(unique_bidders), inline=True)
            
            embed.timestamp = datetime.now()
            embed.set_footer(text="Admin Statistics • Real-time Data")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to generate statistics: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_user", description="[ADMIN] View user's auction activity")
    @app_commands.describe(user="User to investigate")
    @is_admin()
    async def admin_user(self, interaction: discord.Interaction, user: discord.Member):
        """View user's auction activity"""
        try:
            # Get user's auctions
            user_auctions = await self.bot.auction_manager.get_user_auctions(user.id)
            
            # Get auctions where user is bidding
            all_auctions = await self.bot.auction_manager.get_active_auctions(limit=1000)
            bidding_auctions = [a for a in all_auctions if a.current_bidder_id == user.id]
            
            embed = discord.Embed(
                title=f"👤 User Report: {user.display_name}",
                description=f"Auction activity for <@{user.id}>",
                color=0x9b59b6
            )
            
            embed.add_field(name="🏷️ Active Auctions", value=str(len(user_auctions)), inline=True)
            embed.add_field(name="🎯 Currently Bidding", value=str(len(bidding_auctions)), inline=True)
            
            # Calculate total value of user's auctions
            user_auction_value = sum(auction.current_bid for auction in user_auctions)
            embed.add_field(name="💰 Total Auction Value", value=f"${user_auction_value:.2f}", inline=True)
            
            # Show user's recent auctions
            if user_auctions:
                auction_list = []
                for auction in user_auctions[:5]:  # Show max 5
                    bid_text = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
                    auction_list.append(f"• {auction.auction_name} - {bid_text}")
                
                embed.add_field(
                    name="📋 Recent Auctions",
                    value="\n".join(auction_list) or "None",
                    inline=False
                )
            
            # Show bidding activity
            if bidding_auctions:
                bidding_list = []
                for auction in bidding_auctions[:5]:  # Show max 5
                    bidding_list.append(f"• {auction.auction_name} - ${auction.current_bid:.2f}")
                
                embed.add_field(
                    name="🏆 Current Bids",
                    value="\n".join(bidding_list) or "None",
                    inline=False
                )
            
            embed.add_field(name="🆔 User ID", value=f"`{user.id}`", inline=True)
            embed.add_field(name="📅 Account Created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
            embed.add_field(name="📥 Joined Server", value=f"<t:{int(user.joined_at.timestamp())}:R>", inline=True)
            
            embed.timestamp = datetime.now()
            embed.set_footer(text="Admin User Report • Confidential")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to generate user report: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_cleanup", description="[ADMIN] Force cleanup expired auctions")
    @is_admin()
    async def admin_cleanup(self, interaction: discord.Interaction):
        """Force cleanup of expired auctions"""
        try:
            # Get expired auctions
            expired_auctions = await self.bot.auction_manager.get_expired_auctions()
            
            if not expired_auctions:
                embed = discord.Embed(
                    title="🧹 Cleanup Complete",
                    description="No expired auctions found to clean up.",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Process expired auctions
            processed = 0
            for auction in expired_auctions:
                try:
                    await self.bot.handle_auction_end(auction)
                    processed += 1
                except Exception as e:
                    print(f"Error processing expired auction {auction.auction_id}: {e}")
            
            embed = discord.Embed(
                title="🧹 Cleanup Complete",
                description=f"Processed {processed} expired auction(s).",
                color=0x00ff00
            )
            embed.add_field(name="Found", value=str(len(expired_auctions)), inline=True)
            embed.add_field(name="Processed", value=str(processed), inline=True)
            embed.add_field(name="Failed", value=str(len(expired_auctions) - processed), inline=True)
            embed.timestamp = datetime.now()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to perform cleanup: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_health", description="[ADMIN] Check system health status")
    @is_admin()
    async def admin_health(self, interaction: discord.Interaction):
        """Check system health status"""
        try:
            # Perform manual health check
            if hasattr(self.bot, 'health_check_manager') and self.bot.health_check_manager:
                health_data = await self.bot.health_check_manager.manual_health_check()
                
                embed = discord.Embed(
                    title="🩺 System Health Status",
                    color=0x00ff00 if health_data['summary']['overall_health'] else 0xff0000
                )
                
                # Overall status
                overall_status = "✅ Healthy" if health_data['summary']['overall_health'] else "❌ Unhealthy"
                embed.add_field(name="Overall Status", value=overall_status, inline=True)
                
                # Service status
                healthy_services = health_data['summary']['health_metrics']['services_healthy']
                total_services = health_data['summary']['health_metrics']['services_total']
                embed.add_field(name="Services", value=f"{healthy_services}/{total_services} healthy", inline=True)
                
                # Health percentage
                health_percentage = health_data['summary']['health_metrics']['overall_percentage']
                embed.add_field(name="Health Score", value=f"{health_percentage:.1f}%", inline=True)
                
                # Individual service status
                service_status = []
                for service_name, status_data in health_data['results'].items():
                    status_icon = "✅" if status_data['is_healthy'] else "❌"
                    response_time = ""
                    if status_data.get('response_time_ms'):
                        response_time = f" ({status_data['response_time_ms']:.1f}ms)"
                    service_status.append(f"{status_icon} {service_name}{response_time}")
                
                embed.add_field(
                    name="Service Details",
                    value="\n".join(service_status) if service_status else "No services",
                    inline=False
                )
                
                # Active alerts
                active_alerts = health_data['summary']['active_alerts']
                if active_alerts:
                    alert_list = []
                    for alert in active_alerts[:5]:  # Show max 5 alerts
                        alert_list.append(f"⚠️ {alert['service_name']}: {alert['message'][:50]}...")
                    
                    embed.add_field(
                        name="Active Alerts",
                        value="\n".join(alert_list),
                        inline=False
                    )
                
                embed.timestamp = datetime.now()
                embed.set_footer(text="Health Check • Admin Only")
                
            else:
                embed = discord.Embed(
                    title="❌ Health Monitoring Unavailable",
                    description="Health check manager not initialized.",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Failed to check health status: {e}")
            await interaction.response.send_message(
                f"❌ Failed to check health status: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_metrics", description="[ADMIN] View system metrics and performance")
    @is_admin()
    async def admin_metrics(self, interaction: discord.Interaction):
        """View system metrics and performance data"""
        try:
            metrics_summary = metrics_collector.get_metrics_summary()
            
            embed = discord.Embed(
                title="📊 System Metrics",
                description="Performance and usage statistics",
                color=0x3498db
            )
            
            # Counter metrics
            if metrics_summary['counters']:
                counter_list = []
                for name, value in list(metrics_summary['counters'].items())[:10]:  # Show top 10
                    counter_list.append(f"{name}: {value}")
                
                embed.add_field(
                    name="Event Counters",
                    value="\n".join(counter_list) if counter_list else "None",
                    inline=True
                )
            
            # Gauge metrics
            if metrics_summary['gauges']:
                gauge_list = []
                for name, value in list(metrics_summary['gauges'].items())[:10]:  # Show top 10
                    if isinstance(value, float):
                        gauge_list.append(f"{name}: {value:.2f}")
                    else:
                        gauge_list.append(f"{name}: {value}")
                
                embed.add_field(
                    name="Current Values",
                    value="\n".join(gauge_list) if gauge_list else "None",
                    inline=True
                )
            
            # Timer metrics (performance)
            if metrics_summary['timers']:
                timer_list = []
                for name, stats in list(metrics_summary['timers'].items())[:5]:  # Show top 5
                    timer_list.append(f"{name}: {stats['avg']:.1f}ms avg ({stats['count']} calls)")
                
                embed.add_field(
                    name="Performance Timers",
                    value="\n".join(timer_list) if timer_list else "None",
                    inline=False
                )
            
            # Bid sniping statistics if available
            if hasattr(self.bot, 'bid_sniping_protector') and self.bot.bid_sniping_protector:
                sniping_stats = self.bot.bid_sniping_protector.get_sniping_statistics()
                embed.add_field(
                    name="🛡️ Bid Sniping Protection",
                    value=f"Status: {'Enabled' if sniping_stats['protection_enabled'] else 'Disabled'}\n"
                          f"Extensions: {sniping_stats['total_extensions']}\n"
                          f"Success Rate: {sniping_stats['extension_success_rate']:.1f}%",
                    inline=True
                )
            
            embed.timestamp = datetime.now()
            embed.set_footer(text="System Metrics • Admin Only")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            await interaction.response.send_message(
                f"❌ Failed to retrieve metrics: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="admin_config", description="[ADMIN] View current bot configuration")
    @is_admin()
    async def admin_config(self, interaction: discord.Interaction):
        """View current bot configuration"""
        try:
            embed = discord.Embed(
                title="⚙️ Bot Configuration",
                description="Current system settings",
                color=0x95a5a6
            )
            
            # Auction settings
            embed.add_field(
                name="Auction Settings",
                value=f"Min Bid Increment: {config.MIN_BID_INCREMENT*100:.0f}%\n"
                      f"Min Bid Amount: ${config.MIN_BID_AMOUNT:.2f}\n"
                      f"Cleanup Interval: {config.CLEANUP_INTERVAL_MINUTES} min",
                inline=True
            )
            
            # Bid sniping protection
            embed.add_field(
                name="🛡️ Bid Sniping Protection",
                value=f"Enabled: {config.BID_SNIPING_PROTECTION_ENABLED}\n"
                      f"Window: {config.BID_SNIPING_WINDOW_MINUTES} min\n"
                      f"Extension: {config.BID_SNIPING_EXTENSION_MINUTES} min",
                inline=True
            )
            
            # Rate limiting
            embed.add_field(
                name="Rate Limiting",
                value=f"Max Active Auctions: {config.MAX_ACTIVE_AUCTIONS_PER_USER}\n"
                      f"Max Created/Hour: {config.MAX_AUCTIONS_CREATED_PER_HOUR}\n"
                      f"Max Bids/Min: {config.MAX_BIDS_PER_MINUTE}",
                inline=True
            )
            
            # Health monitoring
            embed.add_field(
                name="Health Monitoring",
                value=f"Check Interval: {config.HEALTH_CHECK_INTERVAL_MINUTES} min\n"
                      f"Metrics Enabled: {config.METRICS_ENABLED}\n"
                      f"Log Level: {config.LOG_LEVEL}",
                inline=True
            )
            
            # Channel configuration
            notification_channel = "Not set"
            if config.notification_channel:
                channel = self.bot.get_channel(config.notification_channel)
                notification_channel = f"#{channel.name}" if channel else f"ID: {config.notification_channel}"
            
            log_channel = "Not set"
            if config.log_channel:
                channel = self.bot.get_channel(config.log_channel)
                log_channel = f"#{channel.name}" if channel else f"ID: {config.log_channel}"
            
            embed.add_field(
                name="Channels",
                value=f"Notifications: {notification_channel}\n"
                      f"Logs: {log_channel}",
                inline=True
            )
            
            # Database settings
            embed.add_field(
                name="Database",
                value=f"Path: {config.DATABASE_PATH}\n"
                      f"Backup Enabled: {config.DATABASE_BACKUP_ENABLED}\n"
                      f"Backup Interval: {config.DATABASE_BACKUP_INTERVAL_HOURS}h",
                inline=True
            )
            
            embed.timestamp = datetime.now()
            embed.set_footer(text="Configuration • Admin Only")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Failed to get configuration: {e}")
            await interaction.response.send_message(
                f"❌ Failed to retrieve configuration: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
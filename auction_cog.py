import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Union
import asyncio
from datetime import timedelta
from auction_manager import AuctionManager, Auction

class AuctionCreationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='Create New Auction')
        
        self.item_name = discord.ui.TextInput(
            label='Item Name',
            placeholder='Enter the item contained in the code...',
            required=True,
            max_length=100
        )
        
        self.quantity = discord.ui.TextInput(
            label='Quantity',
            placeholder='Enter quantity...',
            required=True,
            max_length=10
        )
        
        self.auction_name = discord.ui.TextInput(
            label='Auction Name (Optional)',
            placeholder='Leave empty to use item name...',
            required=False,
            max_length=100
        )
        
        self.description = discord.ui.TextInput(
            label='Description (Optional)',
            placeholder='Enter auction description...',
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.bin_price = discord.ui.TextInput(
            label='Buy-It-Now Price (Optional)',
            placeholder='Enter BIN price in dollars...',
            required=False,
            max_length=20
        )
        
        self.add_item(self.item_name)
        self.add_item(self.quantity)
        self.add_item(self.auction_name)
        self.add_item(self.description)
        self.add_item(self.bin_price)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate quantity
            try:
                quantity = int(self.quantity.value)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid quantity! Please enter a positive integer.",
                    ephemeral=True
                )
                return
            
            # Validate BIN price if provided
            bin_price = None
            if self.bin_price.value.strip():
                try:
                    bin_price = float(self.bin_price.value)
                    if bin_price <= 0:
                        raise ValueError("BIN price must be positive")
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Invalid BIN price! Please enter a valid number.",
                        ephemeral=True
                    )
                    return
            
            # Store the form data in the view for duration selection
            duration_view = DurationSelectionView(
                item_name=self.item_name.value,
                quantity=quantity,
                auction_name=self.auction_name.value if self.auction_name.value.strip() else None,
                description=self.description.value,
                bin_price=bin_price,
                user=interaction.user
            )
            
            embed = discord.Embed(
                title="⏰ Select Auction Duration",
                description="Choose how long your auction should run:",
                color=0x0099ff
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=duration_view,
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )

class DurationSelectionView(discord.ui.View):
    def __init__(self, item_name: str, quantity: int, auction_name: Optional[str],
                 description: str, bin_price: Optional[float], user: Union[discord.User, discord.Member]):
        super().__init__(timeout=300)
        self.item_name = item_name
        self.quantity = quantity
        self.auction_name = auction_name
        self.description = description
        self.bin_price = bin_price
        self.user = user
    
    @discord.ui.select(
        placeholder="Choose auction duration...",
        options=[
            discord.SelectOption(label="⚡ 10 Seconds (Admin)", value="0.003", emoji="⚡", description="Admin-only testing duration"),
            discord.SelectOption(label="1 Hour", value="1", emoji="⏰"),
            discord.SelectOption(label="12 Hours", value="12", emoji="🕐"),
            discord.SelectOption(label="1 Day", value="24", emoji="📅"),
            discord.SelectOption(label="3 Days", value="72", emoji="📆"),
            discord.SelectOption(label="1 Week", value="168", emoji="🗓️")
        ]
    )
    async def duration_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        try:
            duration_value = select.values[0]
            
            # Handle admin timer (10 seconds)
            if duration_value == "0.003":
                # Check if user has admin permissions or is server owner
                is_admin = (interaction.guild and interaction.guild.owner_id == interaction.user.id) or \
                          interaction.user.guild_permissions.administrator
                
                if not is_admin:
                    await interaction.response.send_message(
                        "❌ You need administrator permissions or server ownership to use the 10-second timer!",
                        ephemeral=True
                    )
                    return
                duration_hours = 10 / 3600  # 10 seconds in hours
                display_duration = "10 seconds"
            else:
                duration_hours = float(duration_value)
                display_duration = f"{int(duration_hours)} hour{'s' if duration_hours != 1 else ''}"
            
            bot = interaction.client
            
            # Create the auction
            auction = await bot.auction_manager.create_auction(
                owner_id=interaction.user.id,
                item_name=self.item_name,
                quantity=self.quantity,
                duration_hours=duration_hours,
                auction_name=self.auction_name,
                description=self.description,
                bin_price=self.bin_price
            )
            
            embed = discord.Embed(
                title="✅ Auction Created Successfully!",
                description=f"Your auction for **{self.item_name}** has been created.",
                color=0x00ff00
            )
            embed.add_field(name="Auction ID", value=f"`{auction.auction_id}`", inline=False)
            embed.add_field(name="Duration", value=display_duration, inline=True)
            embed.add_field(name="End Time", value=f"<t:{int(auction.end_time.timestamp())}:R>", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to create auction: {str(e)}",
                ephemeral=True
            )

class AuctionListView(discord.ui.View):
    def __init__(self, auctions: List[Auction], page: int = 0):
        super().__init__(timeout=300)
        self.auctions = auctions
        self.page = page
        self.per_page = 5
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        
        # Find buttons and update their disabled state
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "prev_page":
                    item.disabled = self.page <= 0
                elif item.custom_id == "next_page":
                    item.disabled = self.page >= total_pages - 1
    
    def get_page_auctions(self) -> List[Auction]:
        """Get auctions for current page"""
        start = self.page * self.per_page
        end = start + self.per_page
        return self.auctions[start:end]
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            embed = self.create_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        if self.page < total_pages - 1:
            self.page += 1
            self.update_buttons()
            embed = self.create_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.select(placeholder="Select an auction to view...")
    async def auction_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        auction_id = select.values[0]
        bot = interaction.client
        auction = await bot.auction_manager.get_auction(auction_id)
        
        if auction and auction.status == 'active' and not auction.is_expired():
            view = AuctionDetailView(auction)
            embed = view.create_auction_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Auction not found or no longer active.",
                ephemeral=True
            )
    
    def create_list_embed(self) -> discord.Embed:
        """Create embed for auction list"""
        embed = discord.Embed(
            title="🏷️ Active Auctions - BCTC",
            description="Browse current auctions below:",
            color=0x0099ff
        )
        
        page_auctions = self.get_page_auctions()
        if not page_auctions:
            embed.description = "No active auctions found."
            return embed
        
        # Update select menu options
        options = []
        for auction in page_auctions:
            time_left = auction.time_remaining()
            bin_text = f" | BIN: ${auction.bin_price:.2f}" if auction.bin_price else ""
            bid_text = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            
            options.append(discord.SelectOption(
                label=auction.auction_name[:100],  # Truncate if too long
                description=f"Current: {bid_text} | Time: {time_left}{bin_text}"[:100],
                value=auction.auction_id
            ))
        
        # Update select menu
        select = self.children[2]  # The select menu is the third child
        select.options = options
        
        # Add auction summary to embed
        for i, auction in enumerate(page_auctions):
            time_left = auction.time_remaining()
            current_bid = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            bin_info = f" (BIN: ${auction.bin_price:.2f})" if auction.bin_price else ""
            
            embed.add_field(
                name=f"{i+1}. {auction.auction_name}",
                value=f"**Item:** {auction.item_name}\n**Current Bid:** {current_bid}{bin_info}\n**Time Left:** {time_left}",
                inline=False
            )
        
        total_pages = (len(self.auctions) + self.per_page - 1) // self.per_page
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • Total Auctions: {len(self.auctions)}")
        
        return embed

class AuctionDetailView(discord.ui.View):
    def __init__(self, auction: Auction):
        super().__init__(timeout=300)
        self.auction = auction
        
        # Disable BIN button if no BIN price set
        if not auction.bin_price:
            bin_button = [item for item in self.children if item.custom_id == "bin_button"][0]
            bin_button.disabled = True
            bin_button.label = "No BIN Price Set"
    
    @discord.ui.button(label="💰 Place Bid", style=discord.ButtonStyle.primary, custom_id="bid_button")
    async def place_bid(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Calculate minimum bid (10% more than current bid, minimum $0.50)
        min_bid = max(0.50, self.auction.current_bid * 1.10)
        
        # Check if user is already the highest bidder
        if self.auction.current_bidder_id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You are already the highest bidder!",
                ephemeral=True
            )
            return
        
        # Check if user is the auction owner
        if self.auction.owner_id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot bid on your own auction!",
                ephemeral=True
            )
            return
        
        modal = BidModal(self.auction, min_bid)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🎯 Buy It Now", style=discord.ButtonStyle.success, custom_id="bin_button")
    async def buy_it_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.auction.bin_price:
            await interaction.response.send_message(
                "❌ This auction has no Buy It Now price.",
                ephemeral=True
            )
            return
        
        # Check if user is the auction owner
        if self.auction.owner_id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot buy your own auction!",
                ephemeral=True
            )
            return
        
        modal = BINConfirmationModal(self.auction)
        await interaction.response.send_modal(modal)
    
    def create_auction_embed(self) -> discord.Embed:
        """Create detailed auction embed"""
        embed = discord.Embed(
            title=f"🏷️ {self.auction.auction_name}",
            description=self.auction.description or "No description provided",
            color=0x0099ff
        )
        
        # First row
        embed.add_field(name="📦 Item", value=self.auction.item_name, inline=True)
        embed.add_field(name="🔢 Quantity", value=str(self.auction.quantity), inline=True)
        embed.add_field(name="💰 Current Bid", value=f"${self.auction.current_bid:.2f}" if self.auction.current_bid > 0 else "No bids", inline=True)
        
        # Second row
        if self.auction.bin_price:
            embed.add_field(name="🎯 BIN Price", value=f"${self.auction.bin_price:.2f}", inline=True)
        embed.add_field(name="👤 Owner", value=f"<@{self.auction.owner_id}>", inline=True)
        embed.add_field(name="⏰ Time Left", value=self.auction.time_remaining(), inline=True)
        
        # Third row - timestamps
        embed.add_field(name="📅 Started", value=f"<t:{int(self.auction.start_time.timestamp())}:F>", inline=True)
        embed.add_field(name="🏁 Ends", value=f"<t:{int(self.auction.end_time.timestamp())}:F>", inline=True)
        embed.add_field(name="📊 Duration", value=f"{self.auction.duration_hours} hours", inline=True)
        
        if self.auction.current_bidder_id:
            embed.add_field(name="🏆 Current Leader", value=f"<@{self.auction.current_bidder_id}>", inline=False)
        
        # Add image if provided
        if self.auction.image_url:
            embed.set_image(url=self.auction.image_url)
        
        embed.set_footer(text=f"Auction ID: {self.auction.auction_id}")
        
        return embed

class BidModal(discord.ui.Modal):
    def __init__(self, auction: Auction, min_bid: float):
        super().__init__(title='Place Your Bid')
        self.auction = auction
        self.min_bid = min_bid
        
        self.bid_input = discord.ui.TextInput(
            label=f'Bid Amount (Minimum: ${min_bid:.2f})',
            placeholder=f'Enter your bid amount...',
            required=True,
            max_length=20
        )
        self.add_item(self.bid_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bid_amount = float(self.bid_input.value)
            
            if bid_amount < self.min_bid:
                await interaction.response.send_message(
                    f"❌ Bid too low! Minimum bid is ${self.min_bid:.2f}",
                    ephemeral=True
                )
                return
            
            # Anti-abuse checks
            # Check for suspicious bidding patterns (very high bids)
            if bid_amount > self.auction.current_bid * 10 and bid_amount > 100:
                # Flag suspicious high bid
                embed = discord.Embed(
                    title="⚠️ High Bid Warning",
                    description=f"Your bid of ${bid_amount:.2f} is significantly higher than the current bid of ${self.auction.current_bid:.2f}. Please confirm this is intentional.",
                    color=0xffaa00
                )
                embed.add_field(name="Current Bid", value=f"${self.auction.current_bid:.2f}", inline=True)
                embed.add_field(name="Your Bid", value=f"${bid_amount:.2f}", inline=True)
                embed.add_field(name="Difference", value=f"${bid_amount - self.auction.current_bid:.2f}", inline=True)
                embed.set_footer(text="If this was intentional, place the bid again to confirm.")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check for rapid bidding (potential bot)
            if hasattr(interaction.user, '_last_bid_time'):
                import time
                time_since_last = time.time() - interaction.user._last_bid_time
                if time_since_last < 5:  # Less than 5 seconds
                    await interaction.response.send_message(
                        "❌ Please wait at least 5 seconds between bids to prevent spam.",
                        ephemeral=True
                    )
                    return
            
            # Update last bid time for rate limiting
            import time
            interaction.user._last_bid_time = time.time()
            
            # Update the auction
            bot = interaction.client
            await bot.auction_manager.update_auction_bid(
                self.auction.auction_id,
                bid_amount,
                interaction.user.id
            )
            
            embed = discord.Embed(
                title="✅ Bid Placed Successfully!",
                description=f"You have placed a bid of **${bid_amount:.2f}** on **{self.auction.auction_name}**",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid bid amount! Please enter a valid number.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to place bid: {str(e)}",
                ephemeral=True
            )

class BINConfirmationModal(discord.ui.Modal):
    def __init__(self, auction: Auction):
        super().__init__(title='Buy It Now Confirmation')
        self.auction = auction
        
        self.confirmation = discord.ui.TextInput(
            label=f'Type "CONFIRM BUY" to purchase for ${auction.bin_price:.2f}',
            placeholder='Type exactly: CONFIRM BUY',
            required=True,
            max_length=50
        )
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.strip().upper() != "CONFIRM BUY":
            await interaction.response.send_message(
                "❌ Confirmation text incorrect. Please type exactly: CONFIRM BUY",
                ephemeral=True
            )
            return
        
        try:
            bot = interaction.client
            
            # End the auction with BIN purchase
            await bot.auction_manager.update_auction_bid(
                self.auction.auction_id,
                self.auction.bin_price,
                interaction.user.id
            )
            await bot.auction_manager.end_auction(self.auction.auction_id)
            
            embed = discord.Embed(
                title="🎯 Buy It Now - Purchase Complete!",
                description=f"You have successfully purchased **{self.auction.auction_name}** for **${self.auction.bin_price:.2f}**",
                color=0x00ff00
            )
            embed.add_field(name="Item", value=self.auction.item_name, inline=True)
            embed.add_field(name="Quantity", value=str(self.auction.quantity), inline=True)
            embed.add_field(name="Seller", value=f"<@{self.auction.owner_id}>", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Handle auction end notification
            await bot.handle_auction_end({
                'auction_id': self.auction.auction_id,
                'item_name': self.auction.item_name,
                'current_bid': self.auction.bin_price,
                'owner_id': self.auction.owner_id,
                'current_bidder_id': interaction.user.id
            })
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to complete purchase: {str(e)}",
                ephemeral=True
            )

class AuctionEditModal(discord.ui.Modal):
    def __init__(self, auction: Auction):
        super().__init__(title='Edit Auction Details')
        self.auction = auction
        
        self.auction_name = discord.ui.TextInput(
            label='Auction Name',
            default=auction.auction_name,
            required=True,
            max_length=100
        )
        
        self.description = discord.ui.TextInput(
            label='Description',
            default=auction.description,
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.add_item(self.auction_name)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bot = interaction.client
            await bot.auction_manager.update_auction_details(
                self.auction.auction_id,
                self.auction_name.value,
                self.description.value
            )
            
            embed = discord.Embed(
                title="✅ Auction Updated Successfully!",
                description="Your auction details have been updated.",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update auction: {str(e)}",
                ephemeral=True
            )

class UserAuctionView(discord.ui.View):
    def __init__(self, auctions: List[Auction]):
        super().__init__(timeout=300)
        self.auctions = auctions
        
        if not auctions:
            # No auctions, disable all buttons
            for item in self.children:
                item.disabled = True
    
    @discord.ui.select(placeholder="Select an auction to manage...")
    async def auction_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        auction_id = select.values[0]
        bot = interaction.client
        auction = await bot.auction_manager.get_auction(auction_id)
        
        if auction and auction.status == 'active':
            view = AuctionManagementView(auction)
            embed = view.create_management_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Auction not found or no longer active.",
                ephemeral=True
            )
    
    def create_user_auctions_embed(self) -> discord.Embed:
        """Create embed for user's auctions"""
        embed = discord.Embed(
            title="📋 Your Active Auctions",
            color=0x0099ff
        )
        
        if not self.auctions:
            embed.description = "You have no active auctions."
            return embed
        
        # Update select menu options
        options = []
        for auction in self.auctions:
            time_left = auction.time_remaining()
            bid_text = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            
            options.append(discord.SelectOption(
                label=auction.auction_name[:100],
                description=f"Current: {bid_text} | Time: {time_left}"[:100],
                value=auction.auction_id
            ))
        
        # Update select menu
        select = self.children[0]
        select.options = options
        
        for i, auction in enumerate(self.auctions):
            time_left = auction.time_remaining()
            current_bid = f"${auction.current_bid:.2f}" if auction.current_bid > 0 else "No bids"
            
            embed.add_field(
                name=f"{i+1}. {auction.auction_name}",
                value=f"**Item:** {auction.item_name}\n**Current Bid:** {current_bid}\n**Time Left:** {time_left}",
                inline=False
            )
        
        embed.set_footer(text=f"Total Active Auctions: {len(self.auctions)}")
        return embed

class AuctionManagementView(discord.ui.View):
    def __init__(self, auction: Auction):
        super().__init__(timeout=300)
        self.auction = auction
    
    @discord.ui.button(label="✏️ Edit Details", style=discord.ButtonStyle.primary)
    async def edit_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AuctionEditModal(self.auction)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Withdraw", style=discord.ButtonStyle.danger)
    async def withdraw_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        success = await bot.auction_manager.withdraw_auction(self.auction.auction_id, interaction.user.id)
        
        if success:
            embed = discord.Embed(
                title="✅ Auction Withdrawn",
                description=f"Your auction **{self.auction.auction_name}** has been withdrawn.",
                color=0xff9900
            )
        else:
            embed = discord.Embed(
                title="❌ Withdrawal Failed",
                description="Failed to withdraw auction. You may not be the owner.",
                color=0xff0000
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def create_management_embed(self) -> discord.Embed:
        """Create management embed for auction"""
        embed = discord.Embed(
            title=f"⚙️ Manage: {self.auction.auction_name}",
            description="Choose an action below:",
            color=0xff9900
        )
        
        embed.add_field(name="📦 Item", value=self.auction.item_name, inline=True)
        embed.add_field(name="💰 Current Bid", value=f"${self.auction.current_bid:.2f}" if self.auction.current_bid > 0 else "No bids", inline=True)
        embed.add_field(name="⏰ Time Left", value=self.auction.time_remaining(), inline=True)
        
        return embed

class AuctionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="create", description="Create a new auction")
    async def create_auction(self, interaction: discord.Interaction):
        """Create a new auction using a modal with rate limiting"""
        try:
            # Check rate limiting - max 5 active auctions per user
            user_auction_count = await self.bot.auction_manager.get_user_auction_count(interaction.user.id)
            if user_auction_count >= 5:
                embed = discord.Embed(
                    title="❌ Auction Limit Reached",
                    description="You can have a maximum of 5 active auctions at once. Please wait for some to end or withdraw existing auctions.",
                    color=0xff4444
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check for recent auction spam (max 3 auctions in last hour)
            recent_auctions = await self.bot.auction_manager.get_user_recent_auctions(interaction.user.id, hours=1)
            
            # Check if user is admin or server owner (exempt from rate limiting)
            is_admin = (interaction.guild and interaction.guild.owner_id == interaction.user.id) or \
                      interaction.user.guild_permissions.administrator
            
            if len(recent_auctions) >= 3 and not is_admin:
                embed = discord.Embed(
                    title="❌ Rate Limit Exceeded",
                    description="You can only create 3 auctions per hour. Please wait before creating another auction.",
                    color=0xff4444
                )
                embed.add_field(
                    name="Next Available",
                    value=f"<t:{int((recent_auctions[0].start_time + timedelta(hours=1)).timestamp())}:R>",
                    inline=True
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            modal = AuctionCreationModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="auctions", description="View all active auctions")
    async def list_auctions(self, interaction: discord.Interaction):
        """List all active auctions with navigation"""
        auctions = await self.bot.auction_manager.get_active_auctions()
        
        if not auctions:
            embed = discord.Embed(
                title="🏷️ Active Auctions - BCTC",
                description="No active auctions found.",
                color=0x0099ff
            )
            await interaction.response.send_message(embed=embed)
            return
        
        view = AuctionListView(auctions)
        embed = view.create_list_embed()
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="myauctions", description="Manage your active auctions")
    async def my_auctions(self, interaction: discord.Interaction):
        """View and manage user's auctions"""
        auctions = await self.bot.auction_manager.get_user_auctions(interaction.user.id)
        
        view = UserAuctionView(auctions)
        embed = view.create_user_auctions_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AuctionCog(bot))
import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

@dataclass
class Auction:
    auction_id: str
    owner_id: int
    item_name: str
    quantity: int
    auction_name: str
    description: str
    bin_price: Optional[float]
    current_bid: float
    current_bidder_id: Optional[int]
    start_time: datetime
    end_time: datetime
    duration_hours: int
    image_url: Optional[str]
    status: str  # 'active', 'ended', 'withdrawn'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert auction to dictionary for JSON serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Auction':
        """Create auction from dictionary"""
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if auction has expired"""
        return datetime.now() >= self.end_time
    
    def time_remaining(self) -> str:
        """Get formatted time remaining"""
        if self.is_expired():
            return "Expired"
        
        remaining = self.end_time - datetime.now()
        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

class AuctionManager:
    def __init__(self, db_path: str = "auctions.db"):
        self.db_path = db_path
        
    async def initialize(self):
        """Initialize the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auctions (
                    auction_id TEXT PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    auction_name TEXT NOT NULL,
                    description TEXT,
                    bin_price REAL,
                    current_bid REAL DEFAULT 0,
                    current_bidder_id INTEGER,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_hours INTEGER NOT NULL,
                    image_url TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            await db.commit()
    
    async def create_auction(self, owner_id: int, item_name: str, quantity: int, 
                           duration_hours: int, auction_name: Optional[str] = None,
                           description: str = "", bin_price: Optional[float] = None,
                           image_url: Optional[str] = None) -> Auction:
        """Create a new auction"""
        auction_id = str(uuid.uuid4())
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        if not auction_name:
            auction_name = item_name
        
        auction = Auction(
            auction_id=auction_id,
            owner_id=owner_id,
            item_name=item_name,
            quantity=quantity,
            auction_name=auction_name,
            description=description,
            bin_price=bin_price,
            current_bid=0.0,
            current_bidder_id=None,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration_hours,
            image_url=image_url,
            status='active'
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO auctions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                auction.auction_id, auction.owner_id, auction.item_name, auction.quantity,
                auction.auction_name, auction.description, auction.bin_price,
                auction.current_bid, auction.current_bidder_id,
                auction.start_time.isoformat(), auction.end_time.isoformat(),
                auction.duration_hours, auction.image_url, auction.status
            ))
            await db.commit()
        
        return auction
    
    async def get_auction(self, auction_id: str) -> Optional[Auction]:
        """Get auction by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM auctions WHERE auction_id = ?", (auction_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_auction(row)
        return None
    
    async def get_active_auctions(self, limit: int = 10, offset: int = 0) -> List[Auction]:
        """Get active auctions with pagination"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM auctions WHERE status = 'active' ORDER BY start_time DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_auction(row) for row in rows]
    
    async def get_user_auctions(self, user_id: int) -> List[Auction]:
        """Get all auctions for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM auctions WHERE owner_id = ? AND status = 'active' ORDER BY start_time DESC",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_auction(row) for row in rows]
    
    async def update_auction_bid(self, auction_id: str, new_bid: float, bidder_id: int) -> bool:
        """Update auction bid"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE auctions SET current_bid = ?, current_bidder_id = ?
                WHERE auction_id = ?
            """, (new_bid, bidder_id, auction_id))
            await db.commit()
            return True
    
    async def update_auction_details(self, auction_id: str, auction_name: str, description: str) -> bool:
        """Update auction name and description"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE auctions SET auction_name = ?, description = ?
                WHERE auction_id = ?
            """, (auction_name, description, auction_id))
            await db.commit()
            return True
    
    async def withdraw_auction(self, auction_id: str, user_id: int) -> bool:
        """Withdraw an auction (only by owner)"""
        auction = await self.get_auction(auction_id)
        if not auction or auction.owner_id != user_id:
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE auctions SET status = 'withdrawn'
                WHERE auction_id = ?
            """, (auction_id,))
            await db.commit()
            return True
    
    async def end_auction(self, auction_id: str) -> bool:
        """End an auction"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE auctions SET status = 'ended'
                WHERE auction_id = ?
            """, (auction_id,))
            await db.commit()
            return True
    
    async def remove_auction(self, auction_id: str):
        """Remove auction from database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM auctions WHERE auction_id = ?", (auction_id,))
            await db.commit()
    
    async def get_user_auction_count(self, user_id: int) -> int:
        """Get count of active auctions for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM auctions WHERE owner_id = ? AND status = 'active'",
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
    
    async def get_user_recent_auctions(self, user_id: int, hours: int = 24) -> List[Auction]:
        """Get user's recent auctions within specified hours"""
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM auctions WHERE owner_id = ? AND start_time >= ? ORDER BY start_time DESC",
                (user_id, cutoff_time)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_auction(row) for row in rows]
    
    async def get_auction_statistics(self) -> dict:
        """Get comprehensive auction statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Count by status
            async with db.execute("SELECT status, COUNT(*) FROM auctions GROUP BY status") as cursor:
                status_counts = await cursor.fetchall()
                stats['by_status'] = {row[0]: row[1] for row in status_counts}
            
            # Active auction value
            async with db.execute(
                "SELECT SUM(current_bid) FROM auctions WHERE status = 'active'"
            ) as cursor:
                result = await cursor.fetchone()
                stats['active_value'] = result[0] if result[0] else 0.0
            
            # Count unique users
            async with db.execute(
                "SELECT COUNT(DISTINCT owner_id) FROM auctions WHERE status = 'active'"
            ) as cursor:
                result = await cursor.fetchone()
                stats['unique_sellers'] = result[0] if result else 0
            
            # Count unique bidders
            async with db.execute(
                "SELECT COUNT(DISTINCT current_bidder_id) FROM auctions WHERE status = 'active' AND current_bidder_id IS NOT NULL"
            ) as cursor:
                result = await cursor.fetchone()
                stats['unique_bidders'] = result[0] if result else 0
            
            return stats
    
    async def force_end_auction(self, auction_id: str, reason: str = "Administrative action") -> bool:
        """Force end an auction with admin reason"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE auctions SET status = 'ended' WHERE auction_id = ?",
                (auction_id,)
            )
            await db.commit()
            return True
    
    async def extend_auction(self, auction_id: str, additional_hours: float) -> bool:
        """Extend auction duration by specified hours"""
        auction = await self.get_auction(auction_id)
        if not auction:
            return False
        
        new_end_time = auction.end_time + timedelta(hours=additional_hours)
        new_duration = auction.duration_hours + additional_hours
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE auctions SET end_time = ?, duration_hours = ? WHERE auction_id = ?",
                (new_end_time.isoformat(), new_duration, auction_id)
            )
            await db.commit()
            return True
    
    async def get_expired_auctions(self) -> List[Auction]:
        """Get all expired active auctions"""
        current_time = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM auctions WHERE status = 'active' AND end_time <= ?",
                (current_time,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_auction(row) for row in rows]
    
    def _row_to_auction(self, row) -> Auction:
        """Convert database row to Auction object"""
        return Auction(
            auction_id=row[0],
            owner_id=row[1],
            item_name=row[2],
            quantity=row[3],
            auction_name=row[4],
            description=row[5],
            bin_price=row[6],
            current_bid=row[7],
            current_bidder_id=row[8],
            start_time=datetime.fromisoformat(row[9]),
            end_time=datetime.fromisoformat(row[10]),
            duration_hours=row[11],
            image_url=row[12],
            status=row[13]
        )
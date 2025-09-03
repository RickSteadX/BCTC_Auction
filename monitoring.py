"""
Monitoring and logging system for BCTC Auction Bot
Provides structured logging, metrics collection, and health monitoring
"""
import asyncio
import json
import logging
import logging.handlers
import time
import psutil
import discord
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

from config import config


@dataclass
class MetricData:
    """Data structure for storing metrics"""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric_name': self.metric_name,
            'value': self.value,
            'tags': self.tags or {}
        }


@dataclass
class HealthStatus:
    """Health check status"""
    service_name: str
    is_healthy: bool
    message: str
    last_check: datetime
    response_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """Collects and stores performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        
    def record_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Record a counter metric"""
        self.counters[name] += value
        self.metrics[name].append(MetricData(
            timestamp=datetime.now(),
            metric_name=name,
            value=value,
            tags=tags
        ))
    
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a gauge metric"""
        self.gauges[name] = value
        self.metrics[name].append(MetricData(
            timestamp=datetime.now(),
            metric_name=name,
            value=value,
            tags=tags
        ))
    
    def record_timer(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None):
        """Record a timer metric"""
        self.timers[name].append(duration_ms)
        # Keep only last 100 timer values
        if len(self.timers[name]) > 100:
            self.timers[name] = self.timers[name][-100:]
        
        self.metrics[name].append(MetricData(
            timestamp=datetime.now(),
            metric_name=name,
            value=duration_ms,
            tags=tags
        ))
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        summary = {
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'timers': {}
        }
        
        for name, values in self.timers.items():
            if values:
                summary['timers'][name] = {
                    'count': len(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'p95': sorted(values)[int(len(values) * 0.95)] if len(values) > 20 else max(values)
                }
        
        return summary


class HealthChecker:
    """Performs health checks on various system components"""
    
    def __init__(self, bot):
        self.bot = bot
        self.health_status: Dict[str, HealthStatus] = {}
        
    async def check_database_health(self) -> HealthStatus:
        """Check database connectivity and performance"""
        start_time = time.time()
        try:
            if hasattr(self.bot, 'auction_manager') and self.bot.auction_manager:
                # Simple database query to test connectivity
                await self.bot.auction_manager.get_active_auctions(limit=1)
                response_time = (time.time() - start_time) * 1000
                
                return HealthStatus(
                    service_name="database",
                    is_healthy=True,
                    message="Database connection healthy",
                    last_check=datetime.now(),
                    response_time_ms=response_time
                )
            else:
                return HealthStatus(
                    service_name="database",
                    is_healthy=False,
                    message="Auction manager not initialized",
                    last_check=datetime.now()
                )
                
        except Exception as e:
            return HealthStatus(
                service_name="database",
                is_healthy=False,
                message=f"Database error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_discord_api_health(self) -> HealthStatus:
        """Check Discord API connectivity"""
        start_time = time.time()
        try:
            # Test Discord API with a simple operation
            await self.bot.fetch_user(self.bot.user.id)
            response_time = (time.time() - start_time) * 1000
            
            return HealthStatus(
                service_name="discord_api",
                is_healthy=True,
                message="Discord API connection healthy",
                last_check=datetime.now(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            return HealthStatus(
                service_name="discord_api",
                is_healthy=False,
                message=f"Discord API error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def check_system_resources(self) -> HealthStatus:
        """Check system resource usage"""
        try:
            memory_usage = psutil.virtual_memory()
            cpu_usage = psutil.cpu_percent(interval=1)
            disk_usage = psutil.disk_usage('/')
            
            memory_mb = memory_usage.used / 1024 / 1024
            disk_free_gb = disk_usage.free / 1024 / 1024 / 1024
            
            # Check against thresholds
            memory_threshold = config.PERFORMANCE_ALERT_THRESHOLDS['memory_usage_mb']
            cpu_threshold = config.PERFORMANCE_ALERT_THRESHOLDS['cpu_usage_percent']
            
            is_healthy = (
                memory_mb < memory_threshold and 
                cpu_usage < cpu_threshold and 
                disk_free_gb > 1.0  # At least 1GB free
            )
            
            message = f"Memory: {memory_mb:.1f}MB, CPU: {cpu_usage:.1f}%, Disk: {disk_free_gb:.1f}GB free"
            
            return HealthStatus(
                service_name="system_resources",
                is_healthy=is_healthy,
                message=message,
                last_check=datetime.now()
            )
            
        except Exception as e:
            return HealthStatus(
                service_name="system_resources",
                is_healthy=False,
                message=f"System check error: {str(e)}",
                last_check=datetime.now()
            )
    
    async def run_all_checks(self) -> Dict[str, HealthStatus]:
        """Run all health checks"""
        checks = [
            self.check_database_health(),
            self.check_discord_api_health(),
            self.check_system_resources()
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, HealthStatus):
                self.health_status[result.service_name] = result
        
        return self.health_status


class StructuredLogger:
    """Enhanced logging with structured output and Discord integration"""
    
    def __init__(self, name: str = "BCTC_Auction"):
        self.logger = logging.getLogger(name)
        self.setup_logging()
        self.discord_log_channel: Optional[discord.TextChannel] = None
        
    def setup_logging(self):
        """Configure logging with file rotation and formatting"""
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
            
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(config.LOG_FORMAT)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=config.LOG_MAX_SIZE_MB * 1024 * 1024,
            backupCount=config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(config.LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def set_discord_channel(self, channel: discord.TextChannel):
        """Set Discord channel for log messages"""
        self.discord_log_channel = channel
    
    async def log_to_discord(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Send log messages to Discord channel"""
        if not self.discord_log_channel:
            return
            
        try:
            color_map = {
                'ERROR': 0xff0000,
                'WARNING': 0xffaa00,
                'INFO': 0x0099ff,
                'DEBUG': 0x808080
            }
            
            embed = discord.Embed(
                title=f"{level} - BCTC Auction Bot",
                description=message[:2000],  # Discord limit
                color=color_map.get(level, 0x0099ff),
                timestamp=datetime.now()
            )
            
            if extra_data:
                for key, value in extra_data.items():
                    embed.add_field(name=key, value=str(value)[:1024], inline=True)
            
            await self.discord_log_channel.send(embed=embed)
            
        except Exception as e:
            # Don't let Discord logging failures break the application
            self.logger.error(f"Failed to send log to Discord: {e}")
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None, discord_log: bool = False):
        """Log info message"""
        if extra_data:
            self.logger.info(f"{message} | Data: {json.dumps(extra_data)}")
        else:
            self.logger.info(message)
            
        if discord_log:
            asyncio.create_task(self.log_to_discord('INFO', message, extra_data))
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None, discord_log: bool = True):
        """Log warning message"""
        if extra_data:
            self.logger.warning(f"{message} | Data: {json.dumps(extra_data)}")
        else:
            self.logger.warning(message)
            
        if discord_log:
            asyncio.create_task(self.log_to_discord('WARNING', message, extra_data))
    
    def error(self, message: str, extra_data: Dict[str, Any] = None, discord_log: bool = True):
        """Log error message"""
        if extra_data:
            self.logger.error(f"{message} | Data: {json.dumps(extra_data)}")
        else:
            self.logger.error(message)
            
        if discord_log:
            asyncio.create_task(self.log_to_discord('ERROR', message, extra_data))
    
    def debug(self, message: str, extra_data: Dict[str, Any] = None):
        """Log debug message"""
        if extra_data:
            self.logger.debug(f"{message} | Data: {json.dumps(extra_data)}")
        else:
            self.logger.debug(message)


class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, metrics_collector: MetricsCollector, logger: StructuredLogger):
        self.operation_name = operation_name
        self.metrics_collector = metrics_collector
        self.logger = logger
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.metrics_collector.record_timer(self.operation_name, duration_ms)
            
            # Log slow operations
            if duration_ms > config.PERFORMANCE_ALERT_THRESHOLDS['response_time_ms']:
                self.logger.warning(
                    f"Slow operation detected: {self.operation_name}",
                    {'duration_ms': duration_ms, 'threshold_ms': config.PERFORMANCE_ALERT_THRESHOLDS['response_time_ms']}
                )


# Global instances
metrics_collector = MetricsCollector()
logger = StructuredLogger()


def get_performance_timer(operation_name: str) -> PerformanceTimer:
    """Get a performance timer for an operation"""
    return PerformanceTimer(operation_name, metrics_collector, logger)
"""
Health check system for BCTC Auction Bot
Provides comprehensive health monitoring and alerting
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

import discord
from discord.ext import tasks

from config import config
from monitoring import logger, metrics_collector, HealthChecker, HealthStatus


class HealthLevel(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthAlert:
    """Health alert data structure"""
    service_name: str
    level: HealthLevel
    message: str
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['level'] = self.level.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolution_time:
            data['resolution_time'] = self.resolution_time.isoformat()
        return data


class HealthCheckManager:
    """Manages comprehensive health checks and alerting"""
    
    def __init__(self, bot):
        self.bot = bot
        self.health_checker = HealthChecker(bot)
        self.active_alerts: Dict[str, HealthAlert] = {}
        self.health_history: List[Dict[str, Any]] = []
        self.alert_handlers: List[Callable] = []
        
        # Health check thresholds
        self.thresholds = {
            'database_response_time_ms': 1000,
            'discord_api_response_time_ms': 2000,
            'memory_usage_mb': config.PERFORMANCE_ALERT_THRESHOLDS['memory_usage_mb'],
            'cpu_usage_percent': config.PERFORMANCE_ALERT_THRESHOLDS['cpu_usage_percent'],
            'auction_processing_errors': 5,  # per hour
            'failed_notifications': 10  # per hour
        }
    
    def add_alert_handler(self, handler: Callable[[HealthAlert], None]):
        """Add a custom alert handler"""
        self.alert_handlers.append(handler)
    
    async def start_health_monitoring(self):
        """Start the health monitoring background task"""
        if not self.health_check_task.is_running():
            self.health_check_task.start()
            logger.info("Health monitoring started")
    
    async def stop_health_monitoring(self):
        """Stop the health monitoring background task"""
        if self.health_check_task.is_running():
            self.health_check_task.cancel()
            logger.info("Health monitoring stopped")
    
    @tasks.loop(minutes=config.HEALTH_CHECK_INTERVAL_MINUTES)
    async def health_check_task(self):
        """Periodic health check task"""
        try:
            await self.run_comprehensive_health_check()
        except Exception as e:
            logger.error(f"Error in health check task: {e}")
    
    @health_check_task.before_loop
    async def before_health_check(self):
        """Wait for bot to be ready before starting health checks"""
        await self.bot.wait_until_ready()
        logger.info("Health check task ready to start")
    
    async def run_comprehensive_health_check(self) -> Dict[str, HealthStatus]:
        """Run all health checks and process results"""
        logger.debug("Running comprehensive health check")
        
        # Run standard health checks
        health_results = await self.health_checker.run_all_checks()
        
        # Add custom health checks
        custom_checks = await self._run_custom_health_checks()
        health_results.update(custom_checks)
        
        # Process results and generate alerts
        await self._process_health_results(health_results)
        
        # Record health status in history
        self._record_health_history(health_results)
        
        # Update metrics
        self._update_health_metrics(health_results)
        
        return health_results
    
    async def _run_custom_health_checks(self) -> Dict[str, HealthStatus]:
        """Run custom health checks specific to auction bot"""
        custom_checks = {}
        
        # Check auction processing health
        auction_health = await self._check_auction_processing_health()
        custom_checks['auction_processing'] = auction_health
        
        # Check notification system health
        notification_health = await self._check_notification_system_health()
        custom_checks['notification_system'] = notification_health
        
        # Check background tasks health
        tasks_health = await self._check_background_tasks_health()
        custom_checks['background_tasks'] = tasks_health
        
        return custom_checks
    
    async def _check_auction_processing_health(self) -> HealthStatus:
        """Check auction processing system health"""
        try:
            if not hasattr(self.bot, 'auction_manager') or not self.bot.auction_manager:
                return HealthStatus(
                    service_name="auction_processing",
                    is_healthy=False,
                    message="Auction manager not initialized",
                    last_check=datetime.now()
                )
            
            # Check recent auction creation/updates
            start_time = datetime.now()
            active_auctions = await self.bot.auction_manager.get_active_auctions(limit=5)
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Check for stuck auctions (should have been cleaned up)
            expired_auctions = await self.bot.auction_manager.get_expired_auctions()
            
            is_healthy = (
                response_time < self.thresholds['database_response_time_ms'] and
                len(expired_auctions) < 10  # Shouldn't have many expired auctions
            )
            
            message = f"Response time: {response_time:.1f}ms, Active: {len(active_auctions)}, Expired: {len(expired_auctions)}"
            
            return HealthStatus(
                service_name="auction_processing",
                is_healthy=is_healthy,
                message=message,
                last_check=datetime.now(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            return HealthStatus(
                service_name="auction_processing",
                is_healthy=False,
                message=f"Auction processing check failed: {str(e)}",
                last_check=datetime.now()
            )
    
    async def _check_notification_system_health(self) -> HealthStatus:
        """Check notification system health"""
        try:
            if not hasattr(self.bot, 'notification_service') or not self.bot.notification_service:
                return HealthStatus(
                    service_name="notification_system",
                    is_healthy=False,
                    message="Notification service not initialized",
                    last_check=datetime.now()
                )
            
            # Check notification channel accessibility
            channel_id = config.notification_channel
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    return HealthStatus(
                        service_name="notification_system",
                        is_healthy=False,
                        message=f"Notification channel {channel_id} not accessible",
                        last_check=datetime.now()
                    )
            
            # Check recent notification errors from metrics
            metrics = metrics_collector.get_metrics_summary()
            notification_errors = metrics['counters'].get('notification_errors', 0)
            
            # Get error rate over last hour (simplified check)
            is_healthy = notification_errors < self.thresholds['failed_notifications']
            
            return HealthStatus(
                service_name="notification_system",
                is_healthy=is_healthy,
                message=f"Recent errors: {notification_errors}, Channel accessible: {channel_id is not None}",
                last_check=datetime.now()
            )
            
        except Exception as e:
            return HealthStatus(
                service_name="notification_system",
                is_healthy=False,
                message=f"Notification system check failed: {str(e)}",
                last_check=datetime.now()
            )
    
    async def _check_background_tasks_health(self) -> HealthStatus:
        """Check background tasks health"""
        try:
            # Check if cleanup task is running
            cleanup_running = False
            if hasattr(self.bot, 'events_handler') and self.bot.events_handler:
                cleanup_task = getattr(self.bot.events_handler, 'cleanup_expired_auctions', None)
                if cleanup_task and hasattr(cleanup_task, 'is_running'):
                    cleanup_running = cleanup_task.is_running()
            
            # Check health monitoring task
            health_monitoring_running = self.health_check_task.is_running()
            
            is_healthy = cleanup_running and health_monitoring_running
            
            message = f"Cleanup task: {'running' if cleanup_running else 'stopped'}, Health monitoring: {'running' if health_monitoring_running else 'stopped'}"
            
            return HealthStatus(
                service_name="background_tasks",
                is_healthy=is_healthy,
                message=message,
                last_check=datetime.now()
            )
            
        except Exception as e:
            return HealthStatus(
                service_name="background_tasks",
                is_healthy=False,
                message=f"Background tasks check failed: {str(e)}",
                last_check=datetime.now()
            )
    
    async def _process_health_results(self, health_results: Dict[str, HealthStatus]):
        """Process health check results and generate alerts"""
        for service_name, status in health_results.items():
            await self._process_service_health(service_name, status)
    
    async def _process_service_health(self, service_name: str, status: HealthStatus):
        """Process health status for a specific service"""
        current_alert = self.active_alerts.get(service_name)
        
        if not status.is_healthy:
            # Determine alert level
            level = self._determine_alert_level(service_name, status)
            
            if current_alert:
                # Update existing alert if level changed
                if current_alert.level != level:
                    current_alert.level = level
                    current_alert.message = status.message
                    current_alert.timestamp = datetime.now()
                    await self._send_alert(current_alert)
            else:
                # Create new alert
                alert = HealthAlert(
                    service_name=service_name,
                    level=level,
                    message=status.message,
                    timestamp=datetime.now()
                )
                self.active_alerts[service_name] = alert
                await self._send_alert(alert)
        else:
            # Service is healthy - resolve any active alerts
            if current_alert and not current_alert.resolved:
                current_alert.resolved = True
                current_alert.resolution_time = datetime.now()
                
                # Send resolution notification
                resolution_alert = HealthAlert(
                    service_name=service_name,
                    level=HealthLevel.HEALTHY,
                    message=f"Service recovered: {status.message}",
                    timestamp=datetime.now()
                )
                await self._send_alert(resolution_alert)
                
                # Remove from active alerts
                del self.active_alerts[service_name]
    
    def _determine_alert_level(self, service_name: str, status: HealthStatus) -> HealthLevel:
        """Determine the appropriate alert level for a service"""
        if service_name in ['database', 'discord_api']:
            return HealthLevel.CRITICAL
        elif service_name in ['auction_processing', 'notification_system']:
            return HealthLevel.WARNING
        else:
            return HealthLevel.WARNING
    
    async def _send_alert(self, alert: HealthAlert):
        """Send health alert through configured channels"""
        logger.warning(
            f"Health alert: {alert.service_name}",
            {
                "level": alert.level.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            },
            discord_log=True
        )
        
        # Call custom alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert) if asyncio.iscoroutinefunction(handler) else handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
        
        # Record alert in metrics
        metrics_collector.record_counter(f"health_alerts_{alert.level.value}")
    
    def _record_health_history(self, health_results: Dict[str, HealthStatus]):
        """Record health check results in history"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'results': {name: status.to_dict() for name, status in health_results.items()}
        }
        
        self.health_history.append(history_entry)
        
        # Keep only last 100 entries
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
    
    def _update_health_metrics(self, health_results: Dict[str, HealthStatus]):
        """Update health metrics"""
        healthy_services = sum(1 for status in health_results.values() if status.is_healthy)
        total_services = len(health_results)
        
        metrics_collector.record_gauge('health_services_healthy', healthy_services)
        metrics_collector.record_gauge('health_services_total', total_services)
        metrics_collector.record_gauge('health_overall_percentage', (healthy_services / total_services) * 100)
        
        # Record individual service health
        for service_name, status in health_results.items():
            metrics_collector.record_gauge(f'health_{service_name}', 1 if status.is_healthy else 0)
            
            if status.response_time_ms:
                metrics_collector.record_timer(f'health_{service_name}_response_time', status.response_time_ms)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        metrics = metrics_collector.get_metrics_summary()
        
        return {
            'overall_health': len(self.active_alerts) == 0,
            'active_alerts': [alert.to_dict() for alert in self.active_alerts.values()],
            'health_metrics': {
                'services_healthy': metrics['gauges'].get('health_services_healthy', 0),
                'services_total': metrics['gauges'].get('health_services_total', 0),
                'overall_percentage': metrics['gauges'].get('health_overall_percentage', 0)
            },
            'recent_history': self.health_history[-10:] if self.health_history else []
        }
    
    async def manual_health_check(self) -> Dict[str, Any]:
        """Perform manual health check and return results"""
        health_results = await self.run_comprehensive_health_check()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'results': {name: status.to_dict() for name, status in health_results.items()},
            'summary': self.get_health_summary()
        }
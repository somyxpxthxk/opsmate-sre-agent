"""
Metrics Store
=============
Shared in-memory metrics store simulating Prometheus-style telemetry
for all Paytm microservices. Thread-safe and importable across modules.

Each service tracks: latency_p99, error_rate, rps, memory_mb, status, and
per-bank-rail health (for UPI Gateway).
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Literal

ServiceStatus = Literal["healthy", "degraded", "down"]


@dataclass
class ServiceMetrics:
    """Real-time metrics for a single microservice."""
    name: str
    display_name: str
    port: int
    latency_p99_ms: float = 45.0
    error_rate_pct: float = 0.1
    requests_per_sec: float = 1200.0
    memory_mb: float = 256.0
    cpu_pct: float = 12.0
    status: ServiceStatus = "healthy"
    uptime_seconds: float = 86400.0
    last_deploy_time: str = "2026-09-18T10:00:00+05:30"
    active_connections: int = 48
    # Track incident injection state
    chaos_active: bool = False
    chaos_type: str = ""


@dataclass
class BankRailMetrics:
    """Health metrics for an individual bank UPI rail."""
    bank_name: str
    bank_code: str
    latency_ms: float = 120.0
    error_rate_pct: float = 0.3
    success_rate_pct: float = 99.7
    status: ServiceStatus = "healthy"
    traffic_weight_pct: float = 25.0  # % of total traffic routed here


class MetricsStore:
    """
    Central metrics registry. Singleton pattern ensures all tools
    and the chaos engine share the same state.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._start_time = time.time()

        # --- Service Metrics ---
        self.services: dict[str, ServiceMetrics] = {
            "upi-gateway": ServiceMetrics(
                name="upi-gateway",
                display_name="UPI Gateway",
                port=8001,
                latency_p99_ms=85.0,
                error_rate_pct=0.2,
                requests_per_sec=3400.0,
                memory_mb=512.0,
                cpu_pct=34.0,
                active_connections=120,
            ),
            "settlement-engine": ServiceMetrics(
                name="settlement-engine",
                display_name="Settlement Engine",
                port=8002,
                latency_p99_ms=45.0,
                error_rate_pct=0.1,
                requests_per_sec=800.0,
                memory_mb=384.0,
                cpu_pct=18.0,
                active_connections=45,
            ),
            "auth-service": ServiceMetrics(
                name="auth-service",
                display_name="Auth Service",
                port=8003,
                latency_p99_ms=22.0,
                error_rate_pct=0.05,
                requests_per_sec=5200.0,
                memory_mb=192.0,
                cpu_pct=8.0,
                active_connections=200,
            ),
            "merchant-service": ServiceMetrics(
                name="merchant-service",
                display_name="Merchant Service",
                port=8004,
                latency_p99_ms=38.0,
                error_rate_pct=0.08,
                requests_per_sec=1100.0,
                memory_mb=280.0,
                cpu_pct=15.0,
                active_connections=60,
            ),
        }

        # --- Bank Rail Metrics (UPI Gateway sub-components) ---
        self.bank_rails: dict[str, BankRailMetrics] = {
            "HDFC": BankRailMetrics("HDFC Bank", "HDFC", latency_ms=95.0, traffic_weight_pct=30.0),
            "AXIS": BankRailMetrics("Axis Bank", "AXIS", latency_ms=110.0, traffic_weight_pct=25.0),
            "SBI": BankRailMetrics("State Bank of India", "SBI", latency_ms=130.0, traffic_weight_pct=25.0),
            "YES": BankRailMetrics("YES Bank", "YES", latency_ms=105.0, traffic_weight_pct=20.0),
        }

        # --- Incident Timeline (for post-mortem generation) ---
        self.incident_timeline: list[dict] = []

    def get_service(self, name: str) -> ServiceMetrics | None:
        return self.services.get(name)

    def get_all_services_summary(self) -> dict:
        """Returns a JSON-serializable summary of all services."""
        return {
            name: {
                "display_name": s.display_name,
                "status": s.status,
                "latency_p99_ms": s.latency_p99_ms,
                "error_rate_pct": s.error_rate_pct,
                "rps": s.requests_per_sec,
                "memory_mb": s.memory_mb,
                "cpu_pct": s.cpu_pct,
                "active_connections": s.active_connections,
                "chaos_active": s.chaos_active,
            }
            for name, s in self.services.items()
        }

    def get_bank_rails_summary(self) -> dict:
        """Returns a JSON-serializable summary of bank rail health."""
        return {
            code: {
                "bank_name": r.bank_name,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "error_rate_pct": r.error_rate_pct,
                "success_rate_pct": r.success_rate_pct,
                "traffic_weight_pct": r.traffic_weight_pct,
            }
            for code, r in self.bank_rails.items()
        }

    def log_incident_event(self, event_type: str, detail: str):
        """Append an event to the incident timeline for post-mortem generation."""
        self.incident_timeline.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "elapsed_sec": round(time.time() - self._start_time, 1),
            "type": event_type,
            "detail": detail,
        })

    def reset_all(self):
        """Reset all metrics to healthy defaults."""
        self._initialized = False
        self.__init__()

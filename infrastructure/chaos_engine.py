"""
Chaos Engine
=============
Injects real, observable failures into the simulated Paytm infrastructure.
Each chaos scenario modifies the MetricsStore, appends error logs, and
optionally swaps source code files so the agent discovers genuine anomalies.

Supported Scenarios:
    1. bank_node_timeout  — Axis Bank UPI rail returns 504s
    2. bad_deployment     — PR #892 introduces an unindexed DB query
    3. auth_token_expiry  — JWT signing key expired, 401s cascade
    4. settlement_deadlock — Settlement DB locked, payouts stuck
    5. memory_leak        — Gradual OOM in merchant-service
"""

import os
import time
import json
import random
from infrastructure.metrics_store import MetricsStore

# Base path for log files
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
SERVICES_DIR = os.path.join(os.path.dirname(__file__), "..", "services")

# Store original file contents for rollback
_original_files: dict[str, str] = {}


def _append_log(service_name: str, lines: list[str]):
    """Append lines to a service's log file."""
    log_path = os.path.join(LOG_DIR, f"{service_name}.log")
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    with open(log_path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"[{timestamp}] {line}\n")


def _swap_source_file(service: str, filename: str, bad_content: str):
    """Replace a source file with buggy content (stores original for rollback)."""
    file_path = os.path.join(SERVICES_DIR, service, filename)
    key = f"{service}/{filename}"
    if key not in _original_files and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            _original_files[key] = f.read()
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_content)


def _restore_source_file(service: str, filename: str):
    """Restore a source file to its original content."""
    key = f"{service}/{filename}"
    if key in _original_files:
        file_path = os.path.join(SERVICES_DIR, service, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(_original_files[key])
        del _original_files[key]


# =========================================================================
# CHAOS SCENARIO 1: Bank Node Timeout (Axis Bank UPI rail)
# =========================================================================

def inject_bank_node_timeout():
    """Simulates Axis Bank UPI node returning 504 Gateway Timeouts."""
    store = MetricsStore()

    # Degrade UPI Gateway
    svc = store.services["upi-gateway"]
    svc.latency_p99_ms = 1240.0
    svc.error_rate_pct = 14.2
    svc.status = "degraded"
    svc.chaos_active = True
    svc.chaos_type = "bank_node_timeout"

    # Tank the Axis Bank rail specifically
    rail = store.bank_rails["AXIS"]
    rail.latency_ms = 8500.0
    rail.error_rate_pct = 68.5
    rail.success_rate_pct = 31.5
    rail.status = "down"

    # Log realistic errors
    _append_log("upi-gateway", [
        "ERROR [bank_router] Axis Bank rail health check FAILED — connection timeout after 15000ms",
        "ERROR [bank_router] POST https://upi.axis.internal/v2/process returned HTTP 504 (Gateway Timeout)",
        "ERROR [bank_router] Axis Bank rail: 34 consecutive failures, circuit breaker OPEN",
        "WARN  [bank_router] Rerouting 0% of Axis traffic — no failover configured for automatic switch",
        "ERROR [transaction_handler] TXN-928471: UPI collect request failed — downstream bank timeout (AXIS, RRN: 632847291038)",
        "ERROR [transaction_handler] TXN-928472: Payment failed for MID-10002 (Annapurna Sweets) — bank rail AXIS unresponsive",
        "ERROR [transaction_handler] TXN-928473: Merchant MID-10003 payment stuck — AXIS rail circuit breaker OPEN",
        "ERROR [transaction_handler] TXN-928475: Callback timeout for RRN 632847291042 — NPCI acknowledgment not received",
        "WARN  [metrics] UPI Gateway error_rate breach: 14.2% (threshold: 5.0%)",
        "WARN  [metrics] UPI Gateway p99 latency breach: 1240ms (threshold: 500ms)",
        "ERROR [settlement_feed] Settlement batch STLMT-9042 for AXIS merchants DELAYED — upstream transactions pending",
    ])

    store.log_incident_event("CHAOS_INJECTED", "bank_node_timeout: Axis Bank UPI rail returning 504 Gateway Timeouts")
    return {"status": "chaos_injected", "scenario": "bank_node_timeout", "detail": "Axis Bank UPI rail is down with 504 timeouts"}


# =========================================================================
# CHAOS SCENARIO 2: Bad Deployment (unindexed SQL query in settlement-engine)
# =========================================================================

def inject_bad_deployment():
    """Simulates PR #892 deploying a buggy unindexed SQL query that exhausts the DB connection pool."""
    store = MetricsStore()

    # Degrade Settlement Engine
    svc = store.services["settlement-engine"]
    svc.latency_p99_ms = 4800.0
    svc.error_rate_pct = 22.5
    svc.status = "degraded"
    svc.memory_mb = 890.0
    svc.cpu_pct = 92.0
    svc.active_connections = 50  # Pool exhausted
    svc.chaos_active = True
    svc.chaos_type = "bad_deployment"

    # Swap the db.py source file to contain the buggy query
    buggy_db = '''"""
Settlement Engine — Database Layer
===================================
Handles all database operations for merchant settlements.
Uses SQLite with connection pooling for reliability.

WARNING: PR #892 (a3f8b21) modified the get_pending_settlements query.
"""

import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger("settlement-engine.db")

DB_PATH = "infrastructure/data/settlements.db"
MAX_CONNECTIONS = 50

# Connection pool
_pool = []
_active_connections = 0


@contextmanager
def get_connection():
    """Get a connection from the pool."""
    global _active_connections
    if _active_connections >= MAX_CONNECTIONS:
        raise ConnectionError(
            f"ConnectionPoolExhausted: All {MAX_CONNECTIONS} connections are in use. "
            f"Cannot acquire new connection. Active queries may be blocking the pool."
        )
    _active_connections += 1
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
        _active_connections -= 1


def get_pending_settlements(status="PENDING", merchant_id=None):
    """
    Fetch pending settlements from the database.
    
    BUG (PR #892, commit a3f8b21): Removed the WHERE clause filter.
    This causes a full table scan on the settlements table (2.4M rows),
    exhausting the connection pool and causing cascading timeouts.
    
    Previous (correct) query:
        SELECT * FROM settlements WHERE status = ? AND merchant_id = ?
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # BUG: Full table scan — no WHERE clause, no index
        cursor.execute("SELECT * FROM settlements")  # <-- THIS IS THE BUG
        return cursor.fetchall()


def update_settlement_status(settlement_id, new_status, reason=""):
    """Update the status of a settlement record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE settlements SET status = ?, reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, reason, settlement_id)
        )
        conn.commit()
        logger.info(f"Settlement {settlement_id} updated to {new_status}")


def get_settlement_stats():
    """Get aggregate settlement statistics."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*), SUM(amount) FROM settlements GROUP BY status"
        )
        return cursor.fetchall()
'''
    _swap_source_file("settlement-engine", "db.py", buggy_db)

    # Log realistic errors
    _append_log("settlement-engine", [
        "ERROR [db] ConnectionPoolExhausted: All 50 connections are in use. Cannot acquire new connection.",
        "ERROR [db] Query execution timeout: 'SELECT * FROM settlements' — full table scan on 2.4M rows",
        "ERROR [db] Connection pool saturation: 50/50 active connections, 12 requests queued",
        "ERROR [main] POST /settle/batch returned 500 — database connection pool exhausted",
        "ERROR [main] Settlement batch STLMT-9043 FAILED: ConnectionPoolExhausted after 30s timeout",
        "ERROR [main] Settlement batch STLMT-9044 FAILED: ConnectionPoolExhausted — merchant payouts delayed",
        "WARN  [metrics] Settlement Engine memory usage: 890MB (threshold: 512MB) — possible memory pressure from large result sets",
        "WARN  [metrics] Settlement Engine CPU: 92% (threshold: 80%) — full table scan consuming compute",
        "ERROR [main] Merchant MID-10001 (Sharma Kirana Store) payout of ₹18,500 STUCK in PENDING state",
        "ERROR [main] 847 merchant settlements delayed across STLMT-9043, STLMT-9044, STLMT-9045",
        "INFO  [deploy] Deployment detected: commit a3f8b21 (PR #892) by priya.sharma at 21:45:00 — 'feat: add bulk settlement batch processing'",
    ])

    store.log_incident_event("CHAOS_INJECTED", "bad_deployment: PR #892 (a3f8b21) deployed unindexed full table scan in settlement-engine/db.py")
    return {"status": "chaos_injected", "scenario": "bad_deployment", "detail": "PR #892 deployed buggy unindexed query in settlement-engine"}


# =========================================================================
# CHAOS SCENARIO 3: Auth Token Expiry (cascading 401s across all services)
# =========================================================================

def inject_auth_token_expiry():
    """Simulates JWT signing key expiry causing cascading 401 Unauthorized errors."""
    store = MetricsStore()

    # Auth service itself is technically "running" but rejecting all tokens
    auth = store.services["auth-service"]
    auth.error_rate_pct = 95.0
    auth.status = "degraded"
    auth.chaos_active = True
    auth.chaos_type = "auth_token_expiry"

    # Cascade: all other services get 401s when calling auth
    for name in ["upi-gateway", "settlement-engine", "merchant-service"]:
        svc = store.services[name]
        svc.error_rate_pct = min(svc.error_rate_pct + 45.0, 98.0)
        svc.status = "degraded"
        svc.chaos_active = True
        svc.chaos_type = "auth_cascade"

    _append_log("auth-service", [
        "ERROR [jwt_handler] JWT signature verification FAILED — signing key 'paytm-jwt-key-2026-q3' has expired",
        "ERROR [jwt_handler] Token validation error: ExpiredSignatureError — key rotation happened 8 minutes ago but dependent services still use old key",
        "ERROR [main] 401 Unauthorized: /auth/verify — invalid token signature (caller: upi-gateway)",
        "ERROR [main] 401 Unauthorized: /auth/verify — invalid token signature (caller: settlement-engine)",
        "ERROR [main] 401 Unauthorized: /auth/verify — invalid token signature (caller: merchant-service)",
        "WARN  [main] 4,218 token verification failures in last 5 minutes",
        "INFO  [config] Current signing key: 'paytm-jwt-key-2026-q3' (set by PR #890, commit b1d9f44)",
        "WARN  [main] Key rotation PR #890 reduced JWT_EXPIRY_HOURS from 24 to 8 — tokens issued before rotation are now invalid",
    ])

    for svc_name in ["upi-gateway", "settlement-engine", "merchant-service"]:
        _append_log(svc_name, [
            f"ERROR [auth_middleware] 401 Unauthorized from auth-service: token signature invalid",
            f"ERROR [auth_middleware] Failed to authenticate request — auth-service rejecting all tokens",
            f"ERROR [main] Request processing halted — cannot verify merchant/user identity",
            f"WARN  [main] Cascading auth failure detected — auth-service may have rotated keys",
        ])

    store.log_incident_event("CHAOS_INJECTED", "auth_token_expiry: JWT signing key expired, cascading 401s across all services")
    return {"status": "chaos_injected", "scenario": "auth_token_expiry", "detail": "JWT key expired, all services returning 401"}


# =========================================================================
# CHAOS SCENARIO 4: Settlement Deadlock
# =========================================================================

def inject_settlement_deadlock():
    """Simulates a database deadlock in the settlement engine."""
    store = MetricsStore()

    svc = store.services["settlement-engine"]
    svc.latency_p99_ms = 30000.0  # 30 second timeouts
    svc.error_rate_pct = 35.0
    svc.status = "degraded"
    svc.active_connections = 50
    svc.chaos_active = True
    svc.chaos_type = "settlement_deadlock"

    _append_log("settlement-engine", [
        "ERROR [db] SQLITE_BUSY: database table 'settlements' is locked — concurrent write conflict",
        "ERROR [db] Transaction deadlock detected: TXN-A holds row lock on STLMT-9041, waiting for STLMT-9042; TXN-B holds row lock on STLMT-9042, waiting for STLMT-9041",
        "ERROR [db] Deadlock timeout after 30000ms — aborting transaction TXN-A",
        "ERROR [main] Settlement batch processing HALTED — database deadlock preventing all writes",
        "ERROR [main] 1,247 merchant payouts stuck in PROCESSING state — cannot commit or rollback",
        "WARN  [metrics] Settlement queue depth: 3,412 (normal: <100) — backlog growing at 200 txn/min",
        "ERROR [main] Merchant MID-10006 (Gupta Medical Store) — ₹28,500 daily settlement BLOCKED",
        "ERROR [main] Merchant MID-10014 (Fresh Fruit Corner) — ₹16,800 daily settlement BLOCKED",
    ])

    store.log_incident_event("CHAOS_INJECTED", "settlement_deadlock: Database deadlock in settlement-engine preventing all payouts")
    return {"status": "chaos_injected", "scenario": "settlement_deadlock", "detail": "Settlement DB deadlocked, merchant payouts stuck"}


# =========================================================================
# CHAOS SCENARIO 5: Memory Leak
# =========================================================================

def inject_memory_leak():
    """Simulates a gradual memory leak in merchant-service."""
    store = MetricsStore()

    svc = store.services["merchant-service"]
    svc.memory_mb = 1820.0  # Way above normal 280MB
    svc.cpu_pct = 78.0
    svc.latency_p99_ms = 650.0
    svc.status = "degraded"
    svc.chaos_active = True
    svc.chaos_type = "memory_leak"

    _append_log("merchant-service", [
        "WARN  [gc] Heap memory usage: 1820MB / 2048MB (88.9%) — approaching OOM threshold",
        "WARN  [gc] GC pause time: 1.8s (normal: <50ms) — stop-the-world collection under memory pressure",
        "ERROR [gc] Failed to allocate 64MB for merchant profile cache — OutOfMemoryError imminent",
        "WARN  [main] Response times degraded: p99 = 650ms (normal: 38ms) — GC pauses causing latency spikes",
        "ERROR [cache] Merchant profile cache size: 1.2GB (limit: 512MB) — cache eviction not working, possible leak in LRU implementation",
        "WARN  [main] Process RSS growing at ~50MB/hour since last deployment — memory leak suspected",
        "ERROR [main] OOM kill risk: merchant-service will be terminated by kernel if memory exceeds 2048MB",
    ])

    store.log_incident_event("CHAOS_INJECTED", "memory_leak: merchant-service memory at 1820MB/2048MB, OOM imminent")
    return {"status": "chaos_injected", "scenario": "memory_leak", "detail": "Merchant service memory leak, 1820MB/2048MB, OOM imminent"}


# =========================================================================
# RESOLUTION FUNCTIONS (Called by agent's remediation tool)
# =========================================================================

def resolve_bank_node_timeout(reroute_to: str = "HDFC"):
    """Resolve by rerouting traffic away from Axis Bank rail."""
    store = MetricsStore()

    # Fix UPI Gateway
    svc = store.services["upi-gateway"]
    svc.latency_p99_ms = 95.0
    svc.error_rate_pct = 0.3
    svc.status = "healthy"
    svc.chaos_active = False
    svc.chaos_type = ""

    # Mark Axis as isolated, boost the reroute target
    store.bank_rails["AXIS"].status = "down"
    store.bank_rails["AXIS"].traffic_weight_pct = 0.0
    store.bank_rails[reroute_to].traffic_weight_pct += 25.0

    _append_log("upi-gateway", [
        f"INFO  [bank_router] Traffic reroute executed: AXIS rail traffic (25%) shifted to {reroute_to} rail",
        f"INFO  [bank_router] AXIS rail isolated — circuit breaker locked OPEN until manual review",
        f"INFO  [metrics] UPI Gateway error_rate recovered: 14.2% → 0.3%",
        f"INFO  [metrics] UPI Gateway p99 latency recovered: 1240ms → 95ms",
        f"INFO  [transaction_handler] Transaction processing resumed — all active bank rails healthy",
    ])

    store.log_incident_event("REMEDIATION_EXECUTED", f"Traffic rerouted from AXIS to {reroute_to}. UPI Gateway recovered.")
    return {"status": "resolved", "action": "reroute_traffic", "detail": f"Axis Bank rail isolated, traffic shifted to {reroute_to}"}


def resolve_bad_deployment():
    """Resolve by rolling back PR #892 (restoring the original db.py)."""
    store = MetricsStore()

    svc = store.services["settlement-engine"]
    svc.latency_p99_ms = 45.0
    svc.error_rate_pct = 0.1
    svc.status = "healthy"
    svc.memory_mb = 384.0
    svc.cpu_pct = 18.0
    svc.active_connections = 45
    svc.chaos_active = False
    svc.chaos_type = ""

    # Restore the original source file
    _restore_source_file("settlement-engine", "db.py")

    _append_log("settlement-engine", [
        "INFO  [deploy] ROLLBACK executed: commit a3f8b21 (PR #892) reverted to previous version v2.4.1",
        "INFO  [db] Connection pool recovered: 50/50 → 45/50 active connections",
        "INFO  [db] Query restored: 'SELECT * FROM settlements WHERE status = ? AND merchant_id = ?' with proper index",
        "INFO  [main] Settlement batch processing resumed — STLMT-9043 retry initiated",
        "INFO  [metrics] Settlement Engine error_rate recovered: 22.5% → 0.1%",
        "INFO  [metrics] Settlement Engine memory recovered: 890MB → 384MB",
    ])

    store.log_incident_event("REMEDIATION_EXECUTED", "PR #892 rolled back. Settlement engine recovered.")
    return {"status": "resolved", "action": "rollback_deployment", "detail": "PR #892 (a3f8b21) rolled back, settlement-engine restored"}


def resolve_auth_token_expiry():
    """Resolve by rotating the JWT signing key and forcing token refresh."""
    store = MetricsStore()

    # Fix auth service
    auth = store.services["auth-service"]
    auth.error_rate_pct = 0.05
    auth.status = "healthy"
    auth.chaos_active = False
    auth.chaos_type = ""

    # Fix cascading failures
    for name in ["upi-gateway", "settlement-engine", "merchant-service"]:
        svc = store.services[name]
        svc.error_rate_pct = max(svc.error_rate_pct - 45.0, 0.1)
        svc.status = "healthy"
        svc.chaos_active = False
        svc.chaos_type = ""

    _append_log("auth-service", [
        "INFO  [jwt_handler] JWT signing key rotated: 'paytm-jwt-key-2026-q3' → 'paytm-jwt-key-2026-q3-emergency'",
        "INFO  [jwt_handler] All dependent services notified to refresh tokens",
        "INFO  [main] Token verification success rate recovered: 5% → 99.95%",
    ])

    for svc_name in ["upi-gateway", "settlement-engine", "merchant-service"]:
        _append_log(svc_name, [
            "INFO  [auth_middleware] Token refresh successful — new signing key accepted",
            "INFO  [main] Service recovered from auth cascade failure",
        ])

    store.log_incident_event("REMEDIATION_EXECUTED", "JWT key rotated, all services recovered from auth cascade.")
    return {"status": "resolved", "action": "rotate_jwt_key", "detail": "JWT key rotated, auth cascade resolved"}


def resolve_settlement_deadlock():
    """Resolve by killing deadlocked transactions and restarting the service."""
    store = MetricsStore()

    svc = store.services["settlement-engine"]
    svc.latency_p99_ms = 45.0
    svc.error_rate_pct = 0.1
    svc.status = "healthy"
    svc.active_connections = 45
    svc.chaos_active = False
    svc.chaos_type = ""

    _append_log("settlement-engine", [
        "INFO  [db] Deadlocked transactions TXN-A and TXN-B terminated",
        "INFO  [db] Database lock released — WAL checkpoint completed",
        "INFO  [main] Service restarted — settlement queue draining at 500 txn/min",
        "INFO  [main] 1,247 stuck settlements moved back to PENDING for retry",
        "INFO  [metrics] Settlement Engine recovered: latency 30000ms → 45ms",
    ])

    store.log_incident_event("REMEDIATION_EXECUTED", "Settlement deadlock resolved, service restarted.")
    return {"status": "resolved", "action": "restart_service", "detail": "Deadlocked transactions killed, settlement-engine restarted"}


def resolve_memory_leak():
    """Resolve by restarting the merchant-service container."""
    store = MetricsStore()

    svc = store.services["merchant-service"]
    svc.memory_mb = 280.0
    svc.cpu_pct = 15.0
    svc.latency_p99_ms = 38.0
    svc.status = "healthy"
    svc.chaos_active = False
    svc.chaos_type = ""

    _append_log("merchant-service", [
        "INFO  [main] Service restart initiated — graceful shutdown with 30s drain",
        "INFO  [gc] Memory released: 1820MB → 280MB after container restart",
        "INFO  [cache] Merchant profile cache rebuilt with proper LRU eviction (max: 512MB)",
        "INFO  [main] Service healthy — p99 latency recovered: 650ms → 38ms",
        "WARN  [main] TODO: Investigate LRU cache eviction bug — JIRA ticket PAYTM-8842 created",
    ])

    store.log_incident_event("REMEDIATION_EXECUTED", "Merchant-service restarted, memory leak cleared.")
    return {"status": "resolved", "action": "restart_service", "detail": "Merchant-service restarted, memory recovered to 280MB"}


# =========================================================================
# DISPATCH MAP
# =========================================================================

CHAOS_SCENARIOS = {
    "bank_node_timeout": inject_bank_node_timeout,
    "bad_deployment": inject_bad_deployment,
    "auth_token_expiry": inject_auth_token_expiry,
    "settlement_deadlock": inject_settlement_deadlock,
    "memory_leak": inject_memory_leak,
}

RESOLUTION_MAP = {
    "bank_node_timeout": resolve_bank_node_timeout,
    "bad_deployment": resolve_bad_deployment,
    "auth_token_expiry": resolve_auth_token_expiry,
    "auth_cascade": resolve_auth_token_expiry,  # alias
    "settlement_deadlock": resolve_settlement_deadlock,
    "memory_leak": resolve_memory_leak,
}


def inject_chaos(scenario: str) -> dict:
    """Inject a named chaos scenario."""
    if scenario not in CHAOS_SCENARIOS:
        return {"error": f"Unknown scenario: {scenario}. Available: {list(CHAOS_SCENARIOS.keys())}"}
    return CHAOS_SCENARIOS[scenario]()


def resolve_chaos(scenario: str, **kwargs) -> dict:
    """Resolve a named chaos scenario."""
    if scenario not in RESOLUTION_MAP:
        return {"error": f"Unknown scenario: {scenario}. Available: {list(RESOLUTION_MAP.keys())}"}
    return RESOLUTION_MAP[scenario](**kwargs)


def resolve_all():
    """Reset everything to healthy state."""
    store = MetricsStore()
    store.reset_all()
    # Restore any swapped source files
    for key in list(_original_files.keys()):
        service, filename = key.split("/", 1)
        _restore_source_file(service, filename)
    return {"status": "all_resolved"}

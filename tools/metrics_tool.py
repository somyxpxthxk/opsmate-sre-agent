"""
Agent Tools: Metrics & Telemetry
Provides the agent access to the real-time MetricsStore.
"""

from infrastructure.metrics_store import MetricsStore

def get_service_metrics(service_name: str) -> str:
    """Fetch real-time metrics (latency, error rate, memory, CPU) for a specific service."""
    store = MetricsStore()
    svc = store.get_service(service_name)
    if not svc:
        return f"Error: Service '{service_name}' not found."
    
    return (
        f"Metrics for {svc.display_name} (Port {svc.port}):\n"
        f"  Status: {svc.status}\n"
        f"  Latency (p99): {svc.latency_p99_ms}ms\n"
        f"  Error Rate: {svc.error_rate_pct}%\n"
        f"  RPS: {svc.requests_per_sec}\n"
        f"  Memory: {svc.memory_mb}MB\n"
        f"  CPU: {svc.cpu_pct}%\n"
        f"  Active Connections: {svc.active_connections}\n"
        f"  Uptime: {svc.uptime_seconds}s"
    )

def get_all_services_health() -> str:
    """Get a high-level health summary of all services."""
    store = MetricsStore()
    summary = store.get_all_services_summary()
    
    lines = ["System Health Summary:"]
    for name, data in summary.items():
        status_marker = "🟢" if data["status"] == "healthy" else "🔴" if data["status"] == "down" else "🟡"
        lines.append(f"{status_marker} {data['display_name']} ({name}): {data['status'].upper()} | Err: {data['error_rate_pct']}% | p99: {data['latency_p99_ms']}ms")
    
    return "\n".join(lines)

def get_bank_rail_health() -> str:
    """Fetch health metrics for all upstream UPI bank rails (HDFC, AXIS, SBI, YES)."""
    store = MetricsStore()
    summary = store.get_bank_rails_summary()
    
    lines = ["UPI Bank Rail Health:"]
    for code, data in summary.items():
        status_marker = "🟢" if data["status"] == "healthy" else "🔴" if data["status"] == "down" else "🟡"
        lines.append(f"{status_marker} {data['bank_name']} ({code}): {data['status'].upper()} | Latency: {data['latency_ms']}ms | Error Rate: {data['error_rate_pct']}% | Traffic Weight: {data['traffic_weight_pct']}%")
    
    return "\n".join(lines)

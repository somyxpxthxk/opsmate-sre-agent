"""
Agent Tools: Log Retrieval
Provides the agent access to simulated service logs.
Uses pure Python so this works on Windows (no grep/tail).
"""

import os

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "logs")


def _read_lines(log_file: str) -> list[str]:
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def read_service_logs(service_name: str, lines: int = 50, grep_pattern: str = None) -> str:
    """
    Read the recent logs for a specific microservice.
    Available services: upi-gateway, settlement-engine, auth-service, merchant-service.
    Optionally filter by grep_pattern.
    """
    log_file = os.path.join(LOG_DIR, f"{service_name}.log")

    if not os.path.exists(log_file):
        return f"Error: Log file not found for service '{service_name}'."

    try:
        all_lines = _read_lines(log_file)
        if grep_pattern:
            needle = grep_pattern.lower()
            all_lines = [line for line in all_lines if needle in line.lower()]

        recent = all_lines[-lines:]
        output = "".join(recent).strip()
        if not output:
            return f"No logs found matching criteria for {service_name}."

        return f"Logs for {service_name}:\n{output}"

    except Exception as e:
        return f"Error reading logs: {str(e)}"


def search_all_logs(pattern: str, lines_per_file: int = 20) -> str:
    """
    Search across all microservice logs simultaneously for a specific pattern (e.g., a transaction ID, 'ERROR').
    """
    if not os.path.exists(LOG_DIR):
        return "Log directory not found."

    results = []
    needle = pattern.lower()

    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".log"):
            continue

        service_name = filename.replace(".log", "")
        log_file = os.path.join(LOG_DIR, filename)

        try:
            matches = [line for line in _read_lines(log_file) if needle in line.lower()]
            output = "".join(matches[-lines_per_file:]).strip()
            if output:
                results.append(f"--- {service_name} ---")
                results.append(output)
                results.append("")
        except Exception:
            pass

    if not results:
        return f"No matches found for pattern '{pattern}' across any logs."

    return "\n".join(results)

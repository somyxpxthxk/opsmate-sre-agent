import os

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

def seed_logs():
    services = [
        "upi-gateway",
        "settlement-engine",
        "auth-service",
        "merchant-service"
    ]
    
    for svc in services:
        log_path = os.path.join(LOG_DIR, f"{svc}.log")
        if not os.path.exists(log_path):
            with open(log_path, "w") as f:
                f.write(f"INFO [{svc}] Service started successfully.\n")
                f.write(f"INFO [{svc}] Listening on port 800X.\n")
                f.write(f"INFO [{svc}] Connected to database.\n")
                f.write(f"INFO [{svc}] Health checks passing.\n")

if __name__ == "__main__":
    seed_logs()
    print("Logs seeded.")

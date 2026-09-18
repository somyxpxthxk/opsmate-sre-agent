import subprocess
import os

def check_local_service(process_name: str = "uvicorn") -> str:
    """
    Check if a local process (like uvicorn) is running.
    """
    try:
        cmd = ["ps", "aux"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.split("\n")
        
        matches = [line for line in lines if process_name in line and "grep" not in line]
        
        if not matches:
            return f"Service '{process_name}' is NOT running locally."
            
        output = [f"SERVICE '{process_name}' IS RUNNING:", "-" * 50]
        for m in matches:
            output.append(m)
        return "\n".join(output)
    except Exception as e:
        return f"ERROR: Failed to check process status: {e}"

def read_local_logs(log_file: str = "backend.log", tail: int = 150) -> str:
    """
    Fetch the last N log lines from a local log file.
    """
    # If the user is running the backend folder, the log file might be in backend/backend.log
    # or in the root. We check a few common locations.
    paths_to_check = [log_file, f"backend/{log_file}", f"../{log_file}", f"../backend/{log_file}"]
    
    found_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            found_path = p
            break
            
    if not found_path:
        return f"ERROR: Log file '{log_file}' does not exist. Please make sure to run your app and redirect logs to this file (e.g., python3 -m uvicorn main:app > backend.log 2>&1)."
        
    try:
        with open(found_path, "r") as f:
            lines = f.readlines()
        
        recent_lines = lines[-tail:]
        return f"=== Logs from {found_path} (last {len(recent_lines)} lines) ===\n" + "".join(recent_lines)
    except Exception as e:
        return f"ERROR: Failed to read log file {found_path}: {e}"

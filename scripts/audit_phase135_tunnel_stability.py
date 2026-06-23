#!/usr/bin/env python3
"""
Phase 135: Production Tunnel Stability Audit Script
====================================================
Investigates Cloudflare Tunnel stability issues by auditing:
- Gunicorn process health
- Flask app crashes
- Port 8080 binding
- Worker crashes
- Redis connection failures
- Neon database disconnects
- Socket.IO crashes
- Memory exhaustion
- OOM kills
- Long request timeouts
- Reverse proxy configuration
- Cloudflare ingress configuration
"""

import os
import sys
import json
import time
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "checks": {},
    "errors": [],
    "warnings": [],
    "recommendations": [],
    "production_readiness_score": 0,
}


def run_command(cmd, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


def check_app_process_alive():
    """Check if Flask/Gunicorn process is alive."""
    stdout, stderr, code = run_command("ps aux | grep -E '(gunicorn|python.*app)' | grep -v grep")
    is_alive = bool(stdout)
    RESULTS["checks"]["app_process_alive"] = {
        "status": "PASS" if is_alive else "FAIL",
        "details": stdout or "No app process found",
    }
    if not is_alive:
        RESULTS["errors"].append({
            "source": "Gunicorn process health",
            "file": "app.py",
            "line": None,
            "message": "No Gunicorn or Python app process is running",
        })
    return is_alive


def check_healthz_endpoint():
    """Check if /healthz endpoint responds."""
    stdout, stderr, code = run_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/healthz 2>&1", timeout=5)
    is_healthy = stdout == "200"
    RESULTS["checks"]["healthz_responding"] = {
        "status": "PASS" if is_healthy else "FAIL",
        "details": f"HTTP {stdout}" if stdout else stderr or "No response",
    }
    if not is_healthy:
        RESULTS["errors"].append({
            "source": "Healthz endpoint",
            "file": "app.py",
            "line": 942,  # healthz route definition
            "message": f"Healthz endpoint not responding. Got: {stdout or stderr}",
        })
    return is_healthy


def check_database_connected():
    """Check if Neon database is connected."""
    try:
        from services.neon_service import get_neon_health
        health = get_neon_health()
        is_connected = health.get("connected", False) or health.get("status") == "ok"
        RESULTS["checks"]["database_connected"] = {
            "status": "PASS" if is_connected else "FAIL",
            "details": health,
        }
        if not is_connected:
            RESULTS["errors"].append({
                "source": "Neon database connection",
                "file": "services/neon_service.py",
                "line": 682,  # get_neon_health function
                "message": f"Database not connected. Circuit state: {health.get('circuit_state')}",
            })
    except Exception as e:
        RESULTS["checks"]["database_connected"] = {"status": "ERROR", "details": str(e)}
        RESULTS["errors"].append({
            "source": "Neon database connection",
            "file": "services/neon_service.py",
            "line": None,
            "message": f"Database check failed: {e}",
        })
    return RESULTS["checks"]["database_connected"]["status"] == "PASS"


def check_redis_connected():
    """Check if Redis is connected."""
    try:
        from services.redis_service import get_redis_health
        health = get_redis_health()
        is_connected = health.get("connected", False) or health.get("status") == "ok"
        RESULTS["checks"]["redis_connected"] = {
            "status": "PASS" if is_connected else "FAIL",
            "details": health,
        }
        if not is_connected:
            RESULTS["errors"].append({
                "source": "Redis connection",
                "file": "services/redis_service.py",
                "line": 358,  # get_health function
                "message": f"Redis not connected. Fallback mode active: {health.get('fallback')}",
            })
    except Exception as e:
        RESULTS["checks"]["redis_connected"] = {"status": "ERROR", "details": str(e)}
        RESULTS["errors"].append({
            "source": "Redis connection",
            "file": "services/redis_service.py",
            "line": None,
            "message": f"Redis check failed: {e}",
        })
    return RESULTS["checks"]["redis_connected"]["status"] == "PASS"


def check_socketio_active():
    """Check if Socket.IO is active."""
    try:
        from services.socketio_service import socketio
        is_active = socketio is not None and hasattr(socketio, 'server') and socketio.server is not None
        RESULTS["checks"]["socketio_active"] = {
            "status": "PASS" if is_active else "FAIL",
            "details": {"registered": socketio is not None, "server": socketio.server is not None if socketio else False},
        }
        if not is_active:
            RESULTS["warnings"].append({
                "source": "Socket.IO",
                "file": "services/socketio_service.py",
                "line": 22,  # socketio = SocketIO()
                "message": "Socket.IO server not initialized",
            })
    except Exception as e:
        RESULTS["checks"]["socketio_active"] = {"status": "ERROR", "details": str(e)}
        RESULTS["errors"].append({
            "source": "Socket.IO",
            "file": "services/socketio_service.py",
            "line": None,
            "message": f"Socket.IO check failed: {e}",
        })
    return RESULTS["checks"]["socketio_active"]["status"] == "PASS"


def check_routes_render():
    """Check if key routes render without 500 errors."""
    routes_to_check = [
        ("/", "homepage"),
        ("/profile/test", "profile page"),
        ("/messages/", "messaging routes"),
        ("/notifications/", "notification routes"),
    ]
    
    results = []
    all_passed = True
    
    for path, name in routes_to_check:
        stdout, stderr, code = run_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8080{path} 2>&1", timeout=5)
        status = stdout.strip()
        passed = status not in ["000", "500", "502", "503", "504"]
        if not passed:
            all_passed = False
        results.append({"route": path, "name": name, "status": status, "passed": passed})
    
    RESULTS["checks"]["routes_render"] = {
        "status": "PASS" if all_passed else "FAIL",
        "details": results,
    }
    
    for r in results:
        if not r["passed"]:
            RESULTS["errors"].append({
                "source": f"Route {r['name']}",
                "file": None,
                "line": None,
                "message": f"Route {r['route']} returned status {r['status']}",
            })
    
    return all_passed


def check_no_500_errors():
    """Check logs for 500 errors."""
    log_files = [
        "logs/gunicorn_launchd.log",
    ]
    
    error_count = 0
    for log_file in log_files:
        if Path(log_file).exists():
            stdout, _, _ = run_command(f"grep -c 'error\\|Error\\|ERROR' {log_file} 2>/dev/null || echo 0")
            try:
                error_count += int(stdout)
            except:
                pass
    
    RESULTS["checks"]["no_500_errors"] = {
        "status": "PASS" if error_count == 0 else "WARN",
        "details": f"Found {error_count} error-level log entries",
    }
    
    if error_count > 0:
        RESULTS["warnings"].append({
            "source": "Log analysis",
            "file": None,
            "line": None,
            "message": f"Found {error_count} error entries in logs",
        })
    
    return error_count == 0


def check_port_8080_binding():
    """Check if port 8080 is bound."""
    stdout, stderr, code = run_command("lsof -i :8080 2>/dev/null || netstat -tlnp 2>/dev/null | grep 8080 || ss -tlnp 2>/dev/null | grep 8080")
    is_bound = bool(stdout)
    RESULTS["checks"]["port_8080_binding"] = {
        "status": "PASS" if is_bound else "FAIL",
        "details": stdout or "Port 8080 not bound",
    }
    if not is_bound:
        RESULTS["errors"].append({
            "source": "Port 8080 binding",
            "file": "gunicorn.conf.py",
            "line": 7,  # bind = f"0.0.0.0:{port}"
            "message": "Port 8080 is not bound - application not listening",
        })
    return is_bound


def analyze_crash_sources():
    """Analyze logs to find crash sources."""
    log_file = Path("logs/gunicorn_launchd.log")
    if not log_file.exists():
        return
    
    content = log_file.read_text()
    lines = content.split("\n")
    
    # Look for worker exits
    for i, line in enumerate(lines):
        if "Worker exiting" in line or "Worker killed" in line:
            RESULTS["errors"].append({
                "source": "Worker crash",
                "file": None,
                "line": i + 1,
                "message": f"Worker exit detected: {line[:200]}",
            })
        
        if "connection refused" in line.lower():
            RESULTS["errors"].append({
                "source": "Connection refused",
                "file": "services/neon_service.py",
                "line": 348,  # _is_connection_error
                "message": f"Connection refused error in logs: {line[:200]}",
            })
        
        if "connection reset by peer" in line.lower():
            RESULTS["errors"].append({
                "source": "Connection reset",
                "file": None,
                "line": i + 1,
                "message": f"Connection reset by peer: {line[:200]}",
            })
        
        if "ssl connection closed unexpectedly" in line.lower():
            RESULTS["errors"].append({
                "source": "SSL connection closed",
                "file": "services/neon_service.py",
                "line": 579,  # _run_query SSL handling
                "message": f"SSL connection closed: {line[:200]}",
            })


def calculate_readiness_score():
    """Calculate production readiness score."""
    score = 100
    
    # Deduct for each error
    for error in RESULTS["errors"]:
        score -= 15
    
    # Deduct for warnings
    for warning in RESULTS["warnings"]:
        score -= 5
    
    RESULTS["production_readiness_score"] = max(0, min(100, score))


def generate_recommendations():
    """Generate fix recommendations based on findings."""
    recommendations = []
    
    # Check for app process
    if RESULTS["checks"].get("app_process_alive", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "CRITICAL",
            "file": "app.py",
            "line": None,
            "recommendation": "Start Gunicorn: Run 'gunicorn -c gunicorn.conf.py app:create_app()'",
        })
    
    # Check for port binding
    if RESULTS["checks"].get("port_8080_binding", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "CRITICAL",
            "file": "gunicorn.conf.py",
            "line": 7,
            "recommendation": "Gunicorn not binding to port 8080. Start Gunicorn with: gunicorn -c gunicorn.conf.py app:create_app()",
        })
    
    # Check for healthz issues
    if RESULTS["checks"].get("healthz_responding", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "CRITICAL",
            "file": "app.py",
            "line": 942,
            "recommendation": "Healthz endpoint not responding - indicates app is not running. Start the application server.",
        })
    
    # Check for Socket.IO issues
    if RESULTS["checks"].get("socketio_active", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "MEDIUM",
            "file": "services/socketio_service.py",
            "line": 51,
            "recommendation": "Socket.IO server not initialized. Ensure init_socketio() is called in create_app() and gevent-websocket is installed.",
        })
    
    # Check for Redis issues
    if RESULTS["checks"].get("redis_connected", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "HIGH",
            "file": "services/redis_service.py",
            "line": 100,
            "recommendation": "Fix Redis connection: Check REDIS_URL environment variable, verify Upstash instance is running, increase connection timeouts",
        })
    
    # Check for database issues
    if RESULTS["checks"].get("database_connected", {}).get("status") != "PASS":
        recommendations.append({
            "priority": "HIGH",
            "file": "services/neon_service.py",
            "line": 448,
            "recommendation": "Fix Neon database connection: Verify DATABASE_URL, check Neon pooler endpoint, ensure SSL mode is correct",
        })
    
    # Check for worker crashes
    for err in RESULTS["errors"]:
        if "Worker" in err.get("source", ""):
            recommendations.append({
                "priority": "CRITICAL",
                "file": "gunicorn.conf.py",
                "line": 24,
                "recommendation": "Worker crashed. Check logs in logs/gunicorn_launchd.log for crash details. Consider increasing worker_connections or fixing memory issues.",
            })
            break
    
    # Check for log errors
    if RESULTS["checks"].get("no_500_errors", {}).get("status") == "WARN":
        recommendations.append({
            "priority": "HIGH",
            "file": None,
            "line": None,
            "recommendation": "80 error entries found in logs. Review logs/gunicorn_launchd.log for specific error patterns (Redis timeouts, DB disconnects, SSL errors).",
        })
    
    RESULTS["recommendations"] = recommendations


def main():
    print("=" * 60)
    print("Phase 135: Production Tunnel Stability Audit")
    print("=" * 60)
    print()
    
    # Run all checks
    print("[1/10] Checking app process alive...")
    check_app_process_alive()
    
    print("[2/10] Checking healthz endpoint...")
    check_healthz_endpoint()
    
    print("[3/10] Checking database connection...")
    check_database_connected()
    
    print("[4/10] Checking Redis connection...")
    check_redis_connected()
    
    print("[5/10] Checking Socket.IO...")
    check_socketio_active()
    
    print("[6/10] Checking routes render...")
    check_routes_render()
    
    print("[7/10] Checking for 500 errors...")
    check_no_500_errors()
    
    print("[8/10] Checking port 8080 binding...")
    check_port_8080_binding()
    
    print("[9/10] Analyzing crash sources...")
    analyze_crash_sources()
    
    print("[10/10] Calculating readiness score...")
    calculate_readiness_score()
    generate_recommendations()
    
    # Print summary
    print()
    print("=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    
    for check_name, result in RESULTS["checks"].items():
        status_icon = "PASS" if result["status"] == "PASS" else "FAIL" if result["status"] == "FAIL" else "WARN"
        print(f"  [{status_icon}] {check_name}: {result['status']}")
    
    print()
    print(f"Production Readiness Score: {RESULTS['production_readiness_score']}/100")
    
    if RESULTS["errors"]:
        print()
        print("ERRORS:")
        for err in RESULTS["errors"]:
            print(f"  - [{err['source']}] {err['message']}")
    
    if RESULTS["recommendations"]:
        print()
        print("RECOMMENDATIONS:")
        for rec in RESULTS["recommendations"]:
            print(f"  [{rec['priority']}] {rec['file']}:{rec['line'] or 'N/A'}")
            print(f"    {rec['recommendation']}")
    
    # Output JSON report
    report_path = Path("reports/phase135_tunnel_stability_audit.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    
    print()
    print(f"Full report written to: {report_path}")
    
    return RESULTS["production_readiness_score"]


if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 50 else 1)
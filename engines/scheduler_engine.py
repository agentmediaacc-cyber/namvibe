import os
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def init_scheduler(app):
    # Only start if enabled via environment variable
    enable_scheduler = os.getenv("CHAIN_ENABLE_SCHEDULER") == "1"
    
    # Avoid starting during tests unless explicitly forced
    is_testing = os.getenv("FLASK_ENV") == "testing" or "pytest" in os.sys.modules or "unittest" in os.sys.modules
    
    if enable_scheduler and not is_testing:
        if not scheduler.running:
            try:
                scheduler.start()
                print("✅ Chain scheduler started")
            except Exception as e:
                print(f"❌ Chain scheduler failed to start: {e}")
    else:
        if not scheduler.running:
            pass # Stay quiet if disabled or in test mode
            
    return scheduler

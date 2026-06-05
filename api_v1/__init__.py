from .auth_api import auth_api_bp
from .feed_api import feed_api_bp
from .reels_api import reels_api_bp
from .messages_api import messages_api_bp
from .notifications_api import notifications_api_bp
from .profile_api import profile_api_bp
from .live_api import live_api_bp
from .creator_api import creator_api_bp
from .system_api import system_api_bp

BLUEPRINTS = [
    auth_api_bp,
    feed_api_bp,
    reels_api_bp,
    messages_api_bp,
    notifications_api_bp,
    profile_api_bp,
    live_api_bp,
    creator_api_bp,
    system_api_bp
]

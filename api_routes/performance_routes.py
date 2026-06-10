"""Phase 67 — Performance monitoring dashboard and API routes."""

from flask import Blueprint, jsonify, render_template, session
from api_routes.profile_routes import login_required

try:
    from services.production_cache_service import get_cache_stats
    CACHE_AVAILABLE = True
except Exception:
    CACHE_AVAILABLE = False
    def get_cache_stats(): return {}

try:
    from services.phase67_workers import get_worker_stats
    WORKERS_AVAILABLE = True
except Exception:
    WORKERS_AVAILABLE = False
    def get_worker_stats(): return {}

try:
    from services.job_queue_service import get_queue_stats
    QUEUE_AVAILABLE = True
except Exception:
    QUEUE_AVAILABLE = False
    def get_queue_stats(): return {}

try:
    from services.neon_service import get_pool_status as get_db_status
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    def get_db_status(): return {}

try:
    from services.redis_hardening_service import get_redis_health
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False
    def get_redis_health(): return {}

try:
    from services.system_health_service import get_health_status
    SYSTEM_HEALTH_AVAILABLE = True
except Exception:
    SYSTEM_HEALTH_AVAILABLE = False

try:
    from services.phase67_rate_limits import get_rate_limit_config
    RATE_LIMIT_AVAILABLE = True
except Exception:
    RATE_LIMIT_AVAILABLE = False
    def get_rate_limit_config(): return {}

try:
    from services.rate_limit_service import user_or_ip_key
    pass
except Exception:
    pass

performance_bp = Blueprint('performance', __name__, url_prefix='/admin/performance')

@performance_bp.route('/')
@login_required
def index():
    return render_template('admin/performance_dashboard.html')

@performance_bp.route('/api/cache')
@login_required
def api_cache_stats():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    stats = get_cache_stats()
    return jsonify({'ok': True, **stats})

@performance_bp.route('/api/workers')
@login_required
def api_worker_stats():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    stats = get_worker_stats()
    qstats = get_queue_stats()
    return jsonify({'ok': True, 'workers': stats, 'queues': qstats})

@performance_bp.route('/api/database')
@login_required
def api_db_stats():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    status = get_db_status()
    return jsonify({'ok': True, **status})

@performance_bp.route('/api/redis')
@login_required
def api_redis_stats():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    health = get_redis_health()
    return jsonify({'ok': True, 'health': health})

@performance_bp.route('/api/rate-limits')
@login_required
def api_rate_limits():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    config = get_rate_limit_config()
    return jsonify({'ok': True, 'config': config})

@performance_bp.route('/api/all')
@login_required
def api_all():
    if session.get('profile_id') != 'admin' and not session.get('auth_user_id'):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    cache_stats = get_cache_stats()
    worker_stats = get_worker_stats()
    queue_stats = get_queue_stats()
    db_status = get_db_status()
    redis_health = get_redis_health()
    rate_limits = get_rate_limit_config()
    system = {}
    if SYSTEM_HEALTH_AVAILABLE:
        try:
            system = get_health_status()
        except Exception:
            system = {'error': 'system health unavailable'}
    return jsonify({
        'ok': True,
        'cache': cache_stats,
        'workers': worker_stats,
        'queues': queue_stats,
        'database': db_status,
        'redis': {'health': redis_health},
        'rate_limits': rate_limits,
        'system': system,
    })

from flask import Blueprint, render_template

from api_routes.profile_routes import login_required
from services.activity_service import get_favorites, get_history

activity_bp = Blueprint("activity", __name__)

@activity_bp.route("/favorites")
@activity_bp.route("/favorites/")
@login_required
def favorites():
    items, current = get_favorites()
    return render_template("favorites/index.html", items=items, current=current)

@activity_bp.route("/history")
@activity_bp.route("/history/")
@login_required
def history():
    items, current = get_history()
    return render_template("history/index.html", items=items, current=current)

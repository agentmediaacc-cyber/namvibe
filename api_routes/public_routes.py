from flask import Blueprint, render_template
from api_routes.discovery_routes import discovery_bp

public_bp = Blueprint("public", __name__)


@public_bp.route("/feedback/")
def feedback_page():
    """Beta feedback page for users to submit feedback."""
    return render_template("feedback.html")


__all__ = ["discovery_bp", "public_bp"]
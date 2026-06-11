from flask import Blueprint, jsonify, render_template, request

from services.search_service import search_chain
from services.rate_limit_service import limiter

search_bp = Blueprint("search", __name__)
search_api_bp = Blueprint("search_api", __name__, url_prefix="/api")


@search_bp.route("/search")
@limiter.limit("60/minute")
def search_page():
    query = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 20, type=int)
    data = search_chain(query, limit=limit)
    return render_template("search/index.html", **data)


@search_api_bp.route("/search")
@limiter.limit("60/minute")
def search_api():
    query = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 20, type=int)
    return jsonify(search_chain(query, limit=limit))

from quart import Blueprint, jsonify, redirect, render_template, request, url_for

chat_api_bp = Blueprint("chat_api", __name__, url_prefix="/api") # , template_folder="templates", static_folder="static"


# ---------- REST endpoint ----------
@chat_api_bp.get("/hello")
async def hello_api():
    """
    Simple JSON endpoint:
    GET /api/hello  ->  {"message": "Hello from Quart!"}
    """
    return jsonify({"message": "Hello from Quart!"})

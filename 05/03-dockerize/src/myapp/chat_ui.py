from quart import Blueprint, jsonify, redirect, render_template, request, url_for

chat_ui_bp = Blueprint("chat_ui", __name__, template_folder="templates", static_folder="static") #, url_prefix="/api"


# ---------- HTML form ----------
@chat_ui_bp.get("/")
async def index_get():
    # Render the form page
    return await render_template("index.html")


@chat_ui_bp.post("/submit")
async def handle_submit():
    """
    Receives form submission from / (index.html).
    Grabs the field named 'name' and echoes it back.
    """
    form = await request.form
    name = form.get("name", "Anonymous")

    # For demo purposes we just show a confirmation page.
    return (
        f"<h1>Thanks, {name}!</h1>"
        "<p>Your form was successfully submitted.</p>"
        '<p><a href="/">Go back</a></p>'
    )

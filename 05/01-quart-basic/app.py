from quart import Quart, jsonify, redirect, render_template, request, url_for

app = Quart(__name__)


# ---------- REST endpoint ----------
@app.get("/api/hello")
async def hello_api():
    """
    Simple JSON endpoint:
    GET /api/hello  ->  {"message": "Hello from Quart!"}
    """
    return jsonify({"message": "Hello from Quart!"})


# ---------- HTML form ----------
@app.get("/")
async def index_get():
    # Render the form page
    return await render_template("index.html")


@app.post("/submit")
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


if __name__ == "__main__":
    # Run with: python app.py   (good for quick dev)
    # For production use `hypercorn app:app`
    app.run(debug=True, port=8000)   # Quart’s built-in dev server
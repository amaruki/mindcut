from flask import Flask, send_from_directory

from web.routes import bp

# Point static_folder to Vite's build directory and set static_url_path to root
app = Flask(__name__, static_folder="frontend/dist", static_url_path="/")

# Register all API endpoints
app.register_blueprint(bp)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    if path.startswith("api/"):
        return {"ok": False, "error": "API endpoint not found"}, 404
    # Let React Router handle the frontend routes
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

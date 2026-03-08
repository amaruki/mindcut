from flask import Flask

from web.routes import bp

app = Flask(__name__, static_folder="static", template_folder="templates")

# Register all API endpoints and pages
app.register_blueprint(bp)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

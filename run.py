"""Start the RemitTrend PH web app: python run.py"""

from app import create_app

PORT = 5050

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=True)

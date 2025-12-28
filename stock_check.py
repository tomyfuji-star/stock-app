from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def index():
    return """
    <h1>株価アプリ 起動成功</h1>
    <p>Renderで正常に動いています</p>
    """

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )

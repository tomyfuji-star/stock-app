from flask import Flask
import pandas as pd

app = Flask(__name__)

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1_jtP54CEzFlFn0lcqKB5qIwbYWbm7PU1EkpJnmW1Km8/export?format=csv&gid=249831611"

@app.route("/")
def index():
    df = pd.read_csv(SHEET_CSV_URL)

    html = "<h1>株価管理シート</h1>"
    html += "<table border='1' cellpadding='5'>"

    # ヘッダー
    html += "<tr>"
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr>"

    # データ
    for _, row in df.iterrows():
        html += "<tr>"
        for val in row:
            html += f"<td>{val}</td>"
        html += "</tr>"

    html += "</table>"
    return html

if __name__ == "__main__":
    print("株価アプリ 起動成功")
    app.run(host="0.0.0.0", port=5000)

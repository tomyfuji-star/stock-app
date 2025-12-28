from flask import Flask
import pandas as pd

app = Flask(__name__)

# Googleスプレッドシート（CSV公開URL）
CSV_URL = "https://docs.google.com/spreadsheets/d/1_jtP54CEzFlFn0lcqKB5qIwbYWbm7PU1EkpJnmW1Km8/export?format=csv&gid=249831611"

@app.route("/")
def index():
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        return f"データ取得エラー: {e}"

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>株価一覧</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            table {{ border-collapse: collapse; }}
            th, td {{ border: 1px solid #999; padding: 6px 10px; }}
            th {{ background: #f0f0f0; }}
        </style>
    </head>
    <body>
        <h2>保有株一覧（Googleスプレッドシート連動）</h2>
        {df.to_html(index=False)}
    </bo

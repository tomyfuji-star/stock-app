import pandas as pd
from flask import Flask, render_template_string

# ===== 設定 =====
SPREADSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/edit?gid=1052470389#gid=1052470389"

app = Flask(__name__)

# ===== 数値変換ユーティリティ =====
def to_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0

def to_int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except:
        return 0

# ===== HTML =====
HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>保有株一覧</title>
<style>
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 6px; text-align: right; }
th { background: #f5f5f5; }
td.left { text-align: left; }
</style>
</head>
<body>
<h2>📈 保有株一覧</h2>
<table>
<tr>
<th>証券コード</th>
<th>銘柄</th>
<th>取得時</th>
<th>枚数</th>
</tr>
{% for r in rows %}
<tr>
<td>{{ r.code }}</td>
<td class="left">{{ r.name }}</td>
<td>{{ "{:,.0f}".format(r.buy) }}</td>
<td>{{ r.qty }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)

    # 列名の正規化（空白対策）
    df.columns = df.columns.str.strip()

    rows = []

    for _, row in df.iterrows():
        rows.append({
            "code": row.get("証券コード", ""),
            "name": row.get("銘柄", ""),
            "buy": to_float(row.get("取得時", 0)),
            "qty": to_int(row.get("枚数", 0)),
        })

    return render_template_string(HTML, rows=rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

from flask import Flask, render_template_string, request
import pandas as pd
import re
import os
from datetime import date

app = Flask(__name__)

# スプレッドシートのURL（前回と同じ）
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

@app.route("/")
def index():
    try:
        # スプレッドシートを読み込む（Googleが計算した結果がここに入ってくる）
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN":
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            
            # --- スプレッドシートに追加した列から直接読み取る ---
            price = to_float(row.get("現在値"))
            change = to_float(row.get("前日比"))
            change_pct = to_float(row.get("騰落率")) * 100 # %表記に直す
            dividend = to_float(row.get("配当")) # 手動入力列がある場合
            # -----------------------------------------------

            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)
            
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code,
                "name": name,
                "price": price,
                "qty": qty,
                "change": change,
                "change_pct": round(change_pct, 2),
                "profit": profit,
                "yield_at_cost": round(yield_at_cost, 2),
                "current_yield": round(current_yield, 2)
            })

    except Exception as e:
        return f"エラーが発生しました: {e}"

    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>資産管理</title>
<style>
body { font-family: sans-serif; margin: 10px; background: #f4f7f6; }
.container { max-width: 900px; margin: auto; }
.summary { display: flex; gap: 10px; margin-bottom: 15px; }
.card { flex: 1; background: #fff; padding: 10px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
.card p { font-size: 1.2em; font-weight: bold; margin: 5px 0 0; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 0.85em; }
th, td { padding: 10px; border: 1px solid #eee; text-align: center; }
th { background: #333; color: #fff; cursor: pointer; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
.num { text-align: right; font-family: monospace; }
.refresh-btn { display: inline-block; background: #007bff; color: #fff; text-decoration: none; padding: 5px 15px; border-radius: 4px; margin-bottom: 10px; }
</style>
</head>
<body>
<div class="container">
    <h2>保有株管理</h2>
    <a href="/" class="refresh-btn">画面更新</a>
    
    <div class="summary">
        <div class="card">
            <h3>合計損益</h3>
            <p class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</p>
        </div>
        <div class="card">
            <h3>年間配当予定</h3>
            <p style="color: #0056b3;">¥{{ "{:,}".format(total_dividend_income) }}</p>
        </div>
    </div>

    <table id="stockTable">
        <thead>
            <tr>
                <th onclick="sortTable(0)">銘柄</th>
                <th onclick="sortTable(1)">現在値 / 株数</th>
                <th onclick="sortTable(2)">評価損益</th>
                <th onclick="sortTable(3)">取得利回り</th>
                <th onclick="sortTable(4)">現在利回り</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td style="text-align:left;"><strong>{{ r.name }}</strong><br><small>{{ r.code }}</small></td>
                <td class="num" data-value="{{ r.price }}">
                    {{ "{:,}".format(r.price|int) }}<br>
                    <small>{{ r.qty }}株</small>
                    <div class="{{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}" style="font-size:0.85em;">
                        {{ '+' if r.change > 0 else '' }}{{ "{:,}".format(r.change|int) }} ({{ r.change_pct }}%)
                    </div>
                </td>
                <td class="num" data-value="{{ r.profit }}">
                    <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:,}".format(r.profit) }}</span>
                </td>
                <td class="num" data-value="{{ r.yield_at_cost }}">{{ r.yield_at_cost }}%</td>
                <td class="num" data-value="{{ r.current_yield }}" style="background:#f0faff;">{{ r.current_yield }}%</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
function sortTable(n) {
  var table = document.getElementById("stockTable");
  var rows = Array.from(table.rows).slice(1);
  var dir = table.getAttribute("data-dir") === "asc" ? "desc" : "asc";
  table.setAttribute("data-dir", dir);
  rows.sort((a, b) => {
    var valA = a.cells[n].getAttribute("data-value") || a.cells[n].innerText;
    var valB = b.cells[n].getAttribute("data-value") || b.cells[n].innerText;
    return dir === "asc" ? (parseFloat(valA) - parseFloat(valB)) : (parseFloat(valB) - parseFloat(valA));
  });
  rows.forEach(row => table.tBodies[0].appendChild(row));
}
</script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

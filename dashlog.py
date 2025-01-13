from dash import Dash, dash_table, html, dcc, Input, Output
import sqlite3
import pandas as pd

# ฟังก์ชันสำหรับดึงข้อมูลจาก SQLite
def fetch_logs():
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, message, timestamp FROM logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    # แปลงข้อมูลเป็น DataFrame
    return pd.DataFrame(rows, columns=["ID", "Symbol", "Message", "Timestamp"])

# สร้าง Dash App
app = Dash(__name__)
app.title = "Trading Bot Logs (Realtime)"

app.layout = html.Div([
    html.H1("Trading Bot Logs (Realtime)"),
    dash_table.DataTable(
        id="logs-table",
        columns=[
            {"name": col, "id": col} for col in ["ID", "Symbol", "Message", "Timestamp"]
        ],
        data=[],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "5px"},
        style_header={"backgroundColor": "lightgrey", "fontWeight": "bold"}
    ),
    dcc.Interval(
        id="interval-component",
        interval=5000,  # อัปเดตทุก 5000ms = 5 วินาที
        n_intervals=0
    )
])

# Callback สำหรับอัปเดตข้อมูล
@app.callback(
    Output("logs-table", "data"),
    [Input("interval-component", "n_intervals")]
)
def update_table(n):
    logs_df = fetch_logs()
    return logs_df.to_dict("records")

if __name__ == "__main__":
    app.run_server(debug=True)

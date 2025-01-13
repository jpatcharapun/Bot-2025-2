from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import threading
import time

# บอทที่เราเขียน
from short import scalping_bot , get_market_ticker

app = Dash(__name__)

# สถานะของบอท
bot_running = False

def start_bot():
    global bot_running
    bot_running = True
    scalping_bot()

app.layout = html.Div([
    html.H1("Bitkub Scalping Bot Dashboard"),
    html.Div(id='bot-status', children="Bot not running"),
    html.Button("Start Bot", id='start-button'),
    html.Button("Stop Bot", id='stop-button'),
    html.Div(id='price-display', children="BTC Price: "),
    dcc.Interval(id='interval', interval=10000, n_intervals=0)  # Update every 10 seconds
])

@app.callback(
    Output('bot-status', 'children'),
    Input('start-button', 'n_clicks'),
    Input('stop-button', 'n_clicks')
)
def control_bot(start_clicks, stop_clicks):
    global bot_running
    ctx = app.callback_context
    if not ctx.triggered:
        return "Bot not running"
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'start-button' and not bot_running:
        threading.Thread(target=start_bot).start()
        return "Bot running"
    elif button_id == 'stop-button':
        bot_running = False
        return "Bot stopped"
    return "Bot not running"

@app.callback(
    Output('price-display', 'children'),
    Input('interval', 'n_intervals')
)
def update_price(n):
    ticker = get_market_ticker("BTC_THB")
    if ticker:
        return f"BTC Price: {ticker.get('last')} THB"
    return "Unable to fetch BTC price"

if __name__ == '__main__':
    app.run_server(debug=True)

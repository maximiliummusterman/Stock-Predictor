import yfinance as yf
import datetime

def get_price_change(ticker_symbol, start_date, end_date):
    # 1. Daten abrufen
    stock = yf.Ticker(ticker_symbol)
    df = stock.history(start=start_date, end=end_date)
    
    if df.empty:
        print("Keine Daten für diesen Zeitraum gefunden.")
        return

    # 2. Kurse am ersten und letzten Handelstag ermitteln
    start_price = df['Close'].iloc[0]
    end_price = df['Close'].iloc[-1]
    
    # Exakte Daten der Handelstage auslesen
    first_trading_day = df.index[0].strftime('%Y-%m-%d')
    last_trading_day = df.index[-1].strftime('%Y-%m-%d')

    # 3. Veränderung berechnen
    absolute_change = end_price - start_price
    percentage_change = (absolute_change / start_price) * 100

    # 4. Ergebnis ausgeben
    print(f"Aktie: {ticker_symbol}")
    print(f"Startdatum ({first_trading_day}): {start_price:.2f}")
    print(f"Enddatum ({last_trading_day}): {end_price:.2f}")
    print(f"Absolutes Wachstum: {absolute_change:+.2f}")
    print(f"Prozentuale Veränderung: {percentage_change:+.2f}%")

# Beispiel-Aufruf (z. B. Apple von 1. Jan bis 1. Jun 2024)
get_price_change("AAPL", "2024-01-01", "2024-06-01")

date_ranges = []
while datetime.date(2019, 1, 1) <= datetime.date(2019, 3, 31):
    date_ranges.append(datetime.date(2019, 1, 1))
    datetime.date(2019, 1, 1) + datetime.timedelta(days=1)

print(date_ranges)  # Ausgabe der generierten Datumsbereiche

def is_working_day(date_obj):
    # weekday(): 0 = Montag, 4 = Freitag, 5 = Samstag, 6 = Sonntag
    return date_obj.weekday() < 5

list_of_tickers = ["AAPL", "MSFT", "GOOGL"]  # Beispielhafte Liste von Tickersymbolen

for w in list_of_tickers:
    for i in range(len(date_ranges)):
        if is_working_day(date_ranges[i]) and is_working_day(date_ranges[i+1]):
            get_price_change(w, date_ranges[i], date_ranges[i+1])
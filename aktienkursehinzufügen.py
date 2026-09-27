from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

# 1. Liste aller 40 DAX-Ticker (Yahoo Finance Endung .DE)
dax_tickers = [
    "ADS.DE",
    "AIR.DE",
    "ALV.DE",
    "BAS.DE",
    "BAYN.DE",
    "BEI.DE",
    "BMW.DE",
    "BNR.DE",
    "CBK.DE",
    "CON.DE",
    "1COV.DE",
    "DTG.DE",
    "DB1.DE",
    "DBK.DE",
    "SY1.DE",
    "DPW.DE",
    "DTE.DE",
    "EON.DE",
    "FRE.DE",
    "HEI.DE",
    "HEN3.DE",
    "HLAG.DE",
    "IFX.DE",
    "MBG.DE",
    "MRK.DE",
    "MTX.DE",
    "MUV2.DE",
    "PAH3.DE",
    "QIA.DE",
    "RWE.DE",
    "SAP.DE",
    "SRT3.DE",
    "SIE.DE",
    "ENR.DE",
    "SHL.DE",
    "SPK.DE",
    "VOW3.DE",
    "VNA.DE",
    "ZAL.DE",
    "RHMG.DE",
]

# 2. Start- und Enddatum abfragen
print("Bitte gib den gewünschten Zeitraum ein (Format: YYYY-MM-DD)")
start_input = input("Startdatum (z.B. 2026-01-01): ").strip()
end_input = input("Enddatum (z.B. 2026-01-31): ").strip()

try:
    start_dt = datetime.strptime(start_input, "%Y-%m-%d")
    end_dt = datetime.strptime(end_input, "%Y-%m-%d")

    # Für den ersten Tag benötigen wir den Schlusskurs des Arbeitstages davor (ca. 7 Tage Puffer)
    fetch_start = (start_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    # yfinance benötigt als 'end' den Folgetag, um den gewünschten Endtag inkludieren zu können
    fetch_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    print(
        f"\nLade DAX-Daten von {start_input} bis {end_input} herunter..."
    )

    # 3. Kursdaten herunterladen
    data = yf.download(
        dax_tickers, start=fetch_start, end=fetch_end, progress=False
    )
    close_prices = data["Close"]

    # 4. Prozentuale und absolute Veränderungen berechnen
    change_abs = close_prices.diff()  # Differenz zum Vortag
    change_pct = close_prices.pct_change() * 100  # Prozentuale Änd. zum Vortag

    # 5. Nur die Tage im angeforderten Zeitraum herausfiltern (Puffer-Tage entfernen)
    requested_mask = (close_prices.index >= start_dt) & (
        close_prices.index <= end_dt
    )
    filtered_dates = close_prices.index[requested_mask]

    if len(filtered_dates) == 0:
        print(
            "Keine Handelstage im angegebenen Zeitraum gefunden (z.B. wegen Wochenenden oder Feiertagen)."
        )
    else:
        # 6. Für jeden Handelstag im Zeitraum eine CSV-Datei schreiben
        for current_date in filtered_dates:
            date_str = current_date.strftime("%Y-%m-%d")

            # Vorheriges Datum (Index) im DataFrame ermitteln, um den Vortageskurs zu holen
            idx = close_prices.index.get_loc(current_date)
            prev_date = close_prices.index[idx - 1]

            # Daten für den aktuellen Tag zusammenstellen
            df_day = pd.DataFrame(
                {
                    "Ticker": dax_tickers,
                    "Schlusskurs_Vortag": close_prices.loc[
                        prev_date, dax_tickers
                    ].values,
                    "Schlusskurs_Tag": close_prices.loc[
                        current_date, dax_tickers
                    ].values,
                    "Aenderung_Absolut": change_abs.loc[
                        current_date, dax_tickers
                    ].values,
                    "Aenderung_Prozent": change_pct.loc[
                        current_date, dax_tickers
                    ].values,
                }
            )

            # Werte runden
            df_day = df_day.round(2)

            # Dateiname nach dem Schema "DAX_Kurse_YYYY-MM-DD.csv"
            filename = f"DAX_Kurse_{date_str}.csv"

            # Als CSV speichern
            df_day.to_csv(filename, index=False, sep=";", encoding="utf-8-sig")
            print(f" -> Datei erstellt: {filename}")

        print(
            f"\nFertig! Es wurden {len(filtered_dates)} CSV-Dateien gespeichert."
        )

except ValueError as e:
    print(
        f"Ungültiges Datumsformat! Bitte nutze das Format YYYY-MM-DD (z.B. 2026-01-15). Fehler: {e}"
    )
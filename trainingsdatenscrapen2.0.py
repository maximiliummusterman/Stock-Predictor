from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urljoin
from urllib.request import urlopen
import csv
import datetime
import json
import ssl
import certifi
import requests
import tqdm
import yfinance as yf

# SSL-Kontext initialisieren
context = ssl.create_default_context(cafile=certifi.where())

# Globale Konfigurationen / Listen
keinegewichtungen = set()
unwichtigelinks = set()


def get_anzahlen(quelle):
    try:
        with open(quelle, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_performance(ticker_symbol, start_date, end_date):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        if df.empty or len(df) < 2:
            return None

        start_price = df['Close'].iloc[0]
        end_price = df['Close'].iloc[-1]
        
        performance = ((end_price / start_price) - 1) * 100
        return performance
    except Exception as e:
        print(f"Fehler bei YFinance ({ticker_symbol}): {e}")
        return None


def linkchecker(urlf):
    for i in unwichtigelinks:
        if i in urlf:
            return False
    return True


def is_working_day(date_obj):
    # weekday(): 0 = Montag, 4 = Freitag, 5 = Samstag, 6 = Sonntag
    return date_obj.weekday() < 5


def load_filter_lists():
    global keinegewichtungen, unwichtigelinks
    
    # keinegewichtungen.csv laden
    try:
        with open('keinegewichtungen.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=' ', quotechar='|')
            keinegewichtungen = {item for row in reader for item in row}
    except FileNotFoundError:
        keinegewichtungen = set()

    # unwichtigelinks.csv laden
    try:
        with open('unwichtigelinks.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=' ', quotechar='|')
            unwichtigelinks = {item for row in reader for item in row}
    except FileNotFoundError:
        unwichtigelinks = set()


def scrape_link(urlf):
    found_links = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(urlf, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for link in soup.find_all("a"):
                href = link.get("href", "")
                full_url = urljoin("https://www.welt.de", href)

                if "article" in full_url and "www.welt.de" in full_url:
                    if linkchecker(full_url) and not full_url.endswith(".pdf"):
                        found_links.append(full_url)
            
            # Duplikate entfernen
            found_links = list(set(found_links))
            print(f"[{urlf}] -> {len(found_links)} Links gefunden!")
            return found_links
        else:
            print(f"Fehler beim Aufruf von {urlf}: Status Code {response.status_code}")
            return []
    except Exception as e:
        print(f"Fehler beim Scrapen von {urlf}: {e}")
        return []


def links_aufrufen(url_to_scrape):
    rwörter = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = requests.get(url_to_scrape, headers=headers, timeout=10)
        if req.status_code == 200:
            soup = BeautifulSoup(req.text, "html.parser")
            for i in soup.get_text().split():
                clean_word = i.strip(",.-!?\"'()").lower()
                if len(clean_word) > 2 and clean_word not in keinegewichtungen:
                    rwörter.append(clean_word)

            with open("found_words.json", "a", encoding='utf-8') as f:
                f.write(json.dumps({url_to_scrape: rwörter}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Fehler beim Lesen von {url_to_scrape}: {e}")


def sortieren(datum_str):
    wörter = []
    
    try:
        with open('found_words.json', 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    for word_list in data.values():
                        wörter.extend(word_list)
    except FileNotFoundError:
        return

    # Counter nutzen für O(N) Performance statt O(N^2) mit list.count()
    anzahlen = Counter(wörter)
    
    # Nach Haufigkeit sortieren
    sorted_anzahlen = dict(sorted(anzahlen.items(), key=lambda item: item[1], reverse=True))

    # Erstelle den Ordner "Rohdaten" falls nicht vorhanden, oder speichere direkt
    import os
    os.makedirs("Rohdaten", exist_ok=True)
    
    with open(f'Rohdaten/anzahlen_{datum_str}.json', 'w', encoding='utf-8') as f:
        json.dump(sorted_anzahlen, f, ensure_ascii=False, indent=2)


# Main Execution Block
if __name__ == "__main__":
    # Filter-Listen vorab einmal laden
    load_filter_lists()

    # Indizes / Ticker laden
    wörter_ind = []
    try:
        with open("indexe.json", "r", encoding='utf-8') as f:
            data = json.load(f)
            wörter_ind = list(data.values())
    except FileNotFoundError:
        print("Datei 'indexe.json' nicht gefunden! Standard-Ticker werden genutzt.")
        wörter_ind = ["^GDAXI"] # Beispiel: DAX

    start_datum = datetime.date(2023, 1, 3)
    end_datum = datetime.date(2023, 1, 9)
    delta_ein_tag = datetime.timedelta(days=1)

    for w in tqdm.tqdm(wörter_ind, desc="Verarbeite Ticker/Indizes"):
        aktuelles_datum = start_datum

        while aktuelles_datum <= end_datum:
            naechster_tag = aktuelles_datum + delta_ein_tag

            # Nur verarbeiten, wenn aktueller und nächster Tag Arbeitstage sind (Börsenöffnung)
            if is_working_day(aktuelles_datum) and is_working_day(naechster_tag):
                
                datum_str = aktuelles_datum.strftime("%Y-%m-%d")
                
                # 1. Hauptseite scrapen (Format YYYY-mm-dd korrigiert)
                url_tag = f"https://www.welt.de/schlagzeilen/nachrichten-vom-{datum_str}.html"
                tages_links = scrape_link(url_tag)

                # 2. Zurücksetzen der temporären Textdatei
                open("found_words.json", "w", encoding='utf-8').close()

                # 3. Artikel scrapen
                for link in tqdm.tqdm(tages_links, desc=f"Scrape Artikel ({datum_str})", leave=False):
                    links_aufrufen(link)

                # 4. Worte auswerten & speichern
                sortieren(datum_str)

                # 5. Aktienperformance berechnen & anhängen
                pct_change = get_performance(w, datum_str, naechster_tag.strftime("%Y-%m-%d"))
                
                performance_data = {
                    "datum": datum_str,
                    "ticker": w,
                    "pct_change": pct_change
                }
                
                with open("aktienkursänderungen.json", "a", encoding='utf-8') as f:
                    f.write(json.dumps(performance_data, ensure_ascii=False) + "\n")

            # WICHTIG: Datum hochzählen!
            aktuelles_datum += delta_ein_tag
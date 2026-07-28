import yfinance as yf, tqdm, json
from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import certifi
import csv
import json
import tqdm
import requests
import multiprocessing
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

wörter_ind = []
context = ssl.create_default_context(cafile=certifi.where())
url = []
wörter = []
threads = []
keinegewichtungen = []
unwichtigelinks = []
links_des_tages = []
anzahlen = {}



def get_anzahlen(quelle):
    with open(quelle, 'r') as f:
        return json.load(f)

def get_performance(ticker_symbol, start_date, end_date):
    # Daten herunterladen
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(start=start_date, end=end_date)
    
    if df.empty:
        return "Keine Daten für diesen Zeitraum gefunden."

    # Ersten und letzten Schlusskurs ermitteln
    start_price = df['Close'].iloc[0]
    end_price = df['Close'].iloc[-1]
    
    # Prozentualen Anstieg berechnen
    performance = ((end_price / start_price) - 1) * 100
    
    return performance


def linkchecker(urlf):
    for i in unwichtigelinks:
        if i in urlf:
            return False
    return True

def tagesvalidation(j, m, d):
    if datetime.datetime(j, m, d).date() == "Saturday" or datetime.datetime(j, m, d).date() == "Sunday":
        return False
    return True

def url_aus_csv():
    url.clear()
    with open('links.csv', newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
        for row in spamreader:
            for i in row:
                url.append(i)
    print(url)

def get_keinegewichtungen():
    with open('keinegewichtungen.csv', newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
        for row in spamreader:
            for i in row:
                keinegewichtungen.append(i) 

def url_sortieren():
    with open('links.csv', newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
        flat_list = []
        for row in spamreader:
            for i in row:
                flat_list.append(i)
        saubere_liste = []
        for item in flat_list:
            if item not in saubere_liste:
                saubere_liste.append(item)
        print(f"Liste: {spamreader}")
        print(f"Flache Liste: {flat_list}")
        print(f"Saubere Liste: {saubere_liste}")
    with open('links.csv', 'w') as f:
        for item in tqdm.tqdm(saubere_liste, desc="Datei wird geschrieben"):
            f.write("%s\n" % item)

def get_unwichtigelinks():
    with open('unwichtigelinks.csv', newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
        for row in spamreader:
            for i in row:
                unwichtigelinks.append(i)



def scrape_link(urlf):
    links = []
    
    # 1. Nutze einen echten Browser-Header, sonst wirst du geblockt
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(urlf, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Diese Funktionen sollten besser AUSSERHALB der Schleife geladen werden (Performance)
            get_keinegewichtungen()
            get_unwichtigelinks()

            for link in soup.find_all("a"):
                href = link.get("href", "")
                
                # 2. Relative Links zu absoluten Links umwandeln
                # Macht aus "/sport/article..." -> "https://www.welt.de/sport/article..."
                full_url = urljoin("https://www.welt.de", href)

                # 3. Logik korrigieren: 
                # Wir wollen nur Links, die "article" enthalten und auf welt.de bleiben
                if "article" in full_url and "www.welt.de" in full_url:
                    if linkchecker(full_url) and not full_url.endswith(".pdf"):
                        if full_url not in url:
                            links.append(full_url)
            
            # Globalen Listen hinzufügen
            links_des_tages.extend(links) 
            
            print(f"{len(links)} Links gefunden!")
            
            # In CSV speichern
            with open('links.csv', 'a', newline='') as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
                if links:
                    spamwriter.writerow(links)
        else:
            print(f"Fehler: Status Code {response.status_code}")
    except Exception as e:
        print(f"Fehler beim Scrapen: {e}")

def links_aufrufen(url):
    rwörter = []

    if 1==1 or requests.get(url).status_code == 200:
    
        page = urlopen(url, context=context)
        html = page.read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for i in soup.get_text().split():
            if len(i) > 2 and i not in keinegewichtungen:

                #print("Found!" + " "  + j)
                rwörter.append(i)

        with open("found_words.json", "a") as f:
            f.write(json.dumps({url: rwörter}, ensure_ascii=False) + "\n")

def sortieren(datum : str):
    wörter = []
    anzahlen = get_anzahlen('anzahlen.json')
    

    with open('found_words.json', 'r') as f:
        for line in tqdm.tqdm(f, desc="Datei wird gelesen"):
            for i in json.loads(line).values():
                wörter.append(i)

    flat_list = [item for sublist in wörter for item in tqdm.tqdm(sublist, desc="Flache Liste wird erstellt")]
    flat_list = [item.lower() for item in flat_list]
    anzahlen = {i: flat_list.count(i) for i in tqdm.tqdm(set(flat_list), desc="Anzahlen werden berechnet")}

    anzahlen = dict(sorted(anzahlen.items(), key=lambda item: item[1]))

    with open(f'Rohdaten/anzahlen_{datum}.json', 'w') as f:
        json.dump(anzahlen, f)


with open("indexe.json", "r") as f:
    for i in json.loads(f.read()).values():
            wörter_ind.append(i)


for w in tqdm.tqdm(wörter_ind, desc="Verarbeitung läuft"):
    start_datum = datetime.date(2023, 1, 3)
    end_datum = datetime.date(2023, 1, 9)
    delta_ein_tag = datetime.timedelta(days=1)
    delta_eine_woche = datetime.timedelta(days=7)   

    aktuelles_datum = start_datum
    print("a")

    while aktuelles_datum <= end_datum:
        tag = aktuelles_datum.day
        monat = aktuelles_datum.month
        jahr = aktuelles_datum.year
        print("b")
        if tagesvalidation(jahr, monat, tag) and tagesvalidation(jahr, monat, tag + 1):
            
            scrape_link(f"https://www.welt.de/schlagzeilen/nachrichten-vom-{jahr}-{monat}-{tag}.html")
            print(links_des_tages)
            for i in links_des_tages:
                links_aufrufen(i)
            sortieren(str(aktuelles_datum))  
            print("aktuelles Datum: " + str(aktuelles_datum))  
            pct_change = get_performance(w, aktuelles_datum.strftime("%Y-%m-%d"), (aktuelles_datum + delta_ein_tag).strftime("%Y-%m-%d"))
            with open("aktienkursänderungen.json", "a") as f:
                f.write(json.dumps({str(aktuelles_datum): {w: pct_change}}, ensure_ascii=False))
            with open("found_words.json", "w") as f:
                f.write(json.dumps({}, ensure_ascii=False))
            with open("links.csv", "w") as f:
                f.write(json.dumps([], ensure_ascii=False))
            with open("anzahlen.json", "w") as f:
                f.write(json.dumps({}, ensure_ascii=False)) 
            #print(f"Die Performance von {w} zwischen {start_datum} und {end_datum} betrug: {pct_change:.2f}%")



            
#Beispiel: Apple (AAPL) im Jahr 2023
# symbol = "AAPL"
# start = "2023-01-04"
# end = "2023-01-09"

# scrape_link("https://www.welt.de/schlagzeilen/nachrichten-vom-2023-01-01.html")

# pct_change = get_performance(symbol, start, end)
# print("A" + str(pct_change))
# print(links_des_tages)
# for i in links_des_tages:
#     links_aufrufen(i)
# sortieren()
# print(f'Die Performance von {symbol} zwischen {start} und {end} betrug: {pct_change}%')

# Layout: {datum: [{wort1 : count, ...}} | {datum : {aktie 1: ptc_change, aktie 2: pct_change, ...}, datum : {aktie 1: ptc_change, aktie 2: pct_change, ...}}
# daten: 2023-01-01 - 2025-12-12
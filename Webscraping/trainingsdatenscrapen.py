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

wörter_ind = []
context = ssl.create_default_context(cafile=certifi.where())
url = []
wörter = []
threads = []
keinegewichtungen = []
unwichtigelinks = []
links_des_tages = []

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
    
    
    if requests.get(urlf).status_code == 200:
        page = urlopen(urlf, context=context)
        html = page.read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        get_keinegewichtungen()
        get_unwichtigelinks()

        for link in soup.find_all("a"):
            href = link.get("href", "")
            if href not in url and linkchecker(href):
                if not href.endswith(".pdf") and href.startswith(urlf):
                    links.append(href)
        links_des_tages.append(links)
        print(links)
        with open('links.csv', 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=' ',quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(links)

def links_aufrufen(url):
    rwörter = []

    if requests.get(url).status_code == 200:
    
        page = urlopen(url, context=context)
        html = page.read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for i in soup.get_text().split():
            if len(i) > 2 and i not in keinegewichtungen:

                #print("Found!" + " "  + j)
                rwörter.append(i)

        with open("found_words.json", "a") as f:
            f.write(json.dumps({url: rwörter}, ensure_ascii=False) + "\n")

def sortieren():
    anzahlen = {}
    wörter = []

    with open('found_words.json', 'r') as f:
        for line in tqdm.tqdm(f, desc="Datei wird gelesen"):
            for i in json.loads(line).values():
                wörter.append(i)

    flat_list = [item for sublist in wörter for item in tqdm.tqdm(sublist, desc="Flache Liste wird erstellt")]
    flat_list = [item.lower() for item in flat_list]
    anzahlen = {i: flat_list.count(i) for i in tqdm.tqdm(set(flat_list), desc="Anzahlen werden berechnet")}

    anzahlen = dict(sorted(anzahlen.items(), key=lambda item: item[1]))

    with open('anzahlen.json', 'w') as f:
        json.dump(anzahlen, f)


with open("indexe.json", "r") as f:
    for i in json.loads(f.read()).values():
            wörter_ind.append(i)


# for w in tqdm.tqdm(wörter_ind, desc="Verarbeitung läuft"):
#     for i in range(20):
#         for j in range(12):
#             for k in range(3):    
#                 symbol = w
#                 start = f"{i+2003}-{j+1}-{k*7+1}"
#                 end = f"{i+2003}-{j+1}-{k*7+2}"
#                 links_des_tages = scrape_link(f"https://www.welt.de/schlagzeilen/nachrichten-vom-{i+2003}-{j+1}-{k*7+1}.html")
#                 pct_change = get_performance(symbol, start, end)
#                 for i in links_des_tages:
#                     links_aufrufen(i)
#                 sortieren()    
#                 print(f"Die Performance von {symbol} zwischen {start} und {end} betrug: {pct_change:.2f}%")



            
#Beispiel: Apple (AAPL) im Jahr 2023
symbol = "AAPL"
start = "2023-01-04"
end = "2023-01-09"

scrape_link("https://www.welt.de/schlagzeilen/nachrichten-vom-2023-01-01.html")

pct_change = get_performance(symbol, start, end)
print("A" + str(pct_change))
print(links_des_tages)
for i in links_des_tages:
    links_aufrufen(i)
sortieren()
print(f'Die Performance von {symbol} zwischen {start} und {end} betrug: {pct_change}%')
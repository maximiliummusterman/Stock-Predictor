#https://realpython.com/python-web-scraping-practical-introduction/
#https://brightdata.de/blog/web-data-de/how-to-scrape-news-articles
#https://brightdata.com/blog/how-tos/beautiful-soup-web-scraping
#https://beautiful-soup-4.readthedocs.io/en/latest/#navigating-the-tree
#https://www.geeksforgeeks.org/python/multiprocessing-python-set-1/
#notion.site
#["([['a']])"] - wie bekomme ich die unnötigen klammern weg, so dass danach nur eine liste mit einem a drin steht? - url.append(u.values()[0]) - so könnte

#Problem: links.json muss stets geleert werden, damit die neuen Links hinzugefügt werden können, da sonst die alten Links mit den neuen vermischt werden. Lösung: links.json wird mit jedem neuen Link überschrieben, damit nur die neuen Links gespeichert werden.
#str(urlf) in link.get("href", "") and 

from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import certifi
import csv
import json
import tqdm
import requests
import multiprocessing

context = ssl.create_default_context(cafile=certifi.where())
url = []
wörter = []
threads = []
keinegewichtungen = []
unwichtigelinks = []


def linkchecker(urlf):
    for i in unwichtigelinks:
        if i in urlf:
            return False
    return True


def url_aus_csv():
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
        with open('links.csv', 'a', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=' ',quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(links)

scrape_link("https://www.handelsblatt.com")
#

def links_aufrufen(url):
    wörter = []

    if requests.get(url).status_code == 200:
    
        page = urlopen(url, context=context)
        html = page.read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for i in soup.get_text().split():
            if i not in wörter and len(i) > 2 and i not in keinegewichtungen:

                #print("Found!" + " "  + j)
                wörter.append(i)

        with open("found_words.json", "a") as f:
            f.write(json.dumps({url: wörter}, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    url_aus_csv()
    for i in tqdm.tqdm(range(1, len(url), 2), desc="Verarbeitung läuft"):

        p1 = multiprocessing.Process(target=links_aufrufen, args=(url[i],))
        p2 = multiprocessing.Process(target=links_aufrufen, args=(url[i-1],))
        p3 = multiprocessing.Process(target=scrape_link, args=(url[i],))
        p4 = multiprocessing.Process(target=scrape_link, args=(url[i-1],))
        p1.start()
        p2.start()
        p3.start()
        p4.start()
        p1.join()
        p2.join()
        p3.join()
        p4.join()

# from tqdm import tqdm

# liste = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
# ergebnis = []

# # Start bei Index 3 ("D"), Schrittweite 4
# for i in tqdm(range(3, len(liste), 4), desc="Extrahiere"):
#     ergebnis.append(liste[i])

# print(ergebnis)
# # Ausgabe: ['D', 'H'] -> für 16 statt 4
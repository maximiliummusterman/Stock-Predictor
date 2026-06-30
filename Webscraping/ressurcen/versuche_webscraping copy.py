#https://realpython.com/python-web-scraping-practical-introduction/
#https://brightdata.de/blog/web-data-de/how-to-scrape-news-articles
#https://brightdata.com/blog/how-tos/beautiful-soup-web-scraping
#https://beautiful-soup-4.readthedocs.io/en/latest/#navigating-the-tree
from bs4 import BeautifulSoup
from urllib.request import urlopen
import ssl
import certifi
import json

context = ssl.create_default_context(cafile=certifi.where())

url = "https://www.handelsblatt.com"
url2 = "http://books.toscrape.com"
url3 = "https://www.welt.de"
liste = ["GIRL", "Sharp", "objects", "sharp objects"]
wörter = []
page = urlopen(url, context=context)
page2 = urlopen(url2, context=context)
page3 = urlopen(url3, context=context)
html = page.read().decode("utf-8")
html2 = page2.read().decode("utf-8")
html3 = page3.read().decode("utf-8")

soup = BeautifulSoup(html, "html.parser")
soup2 = BeautifulSoup(html2, "html.parser")
soup3 = BeautifulSoup(html3, "html.parser")
#print(soup.get_text())

with open("keinegewichtungen.json", "r") as n_g_woerter:

    for j in soup3.get_text().split():
        if j in soup.get_text() and j not in wörter and len(j) > 2 and j not in n_g_woerter:

            #print("Found!" + " "  + j)
            wörter.append(j)
    print(wörter)

# Save the list of found words to a JSON file
with open("found_words.json", "w") as f:
    json.dump(wörter, f)

for link in soup.find_all("a"):
    if "handelsblatt.com" in link.get("href", ""):
        print(link.get("href"))

links = []
def scrape_links(url):
    page = urlopen(url, context=context)
    html = page.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "https://www.handelsblatt.com" in link.get("href", ""):
            links.append(href)
    with open("links.json", "w") as f:
        json.dump(links, f)
    return links

def links_aufrufen():
    with open("links.json", "r") as f:
        links = json.load(f)
    for link in links:
        page = urlopen(link, context=context)
        

print(scrape_links("https://www.handelsblatt.com"))
#print(soup3.get_text().split())
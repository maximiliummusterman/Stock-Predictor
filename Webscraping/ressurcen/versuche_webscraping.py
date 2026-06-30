#https://realpython.com/python-web-scraping-practical-introduction/
from urllib.request import urlopen

url = "http://olympus.realpython.org/profiles/aphrodite"
url2= "http://books.toscrape.com"
page = urlopen(url2)

html_bytes = page.read()
html = html_bytes.decode("utf-8")
start_index = html.find("<title>") + len("<title>")
end_index = html.find("</title>")
title = html[start_index:end_index]
start_index2 = html.find("<body>") + len("<body>")
end_index2 = html.find("</body>")
title2 = html[start_index2:end_index2]
liste = ["All", "Books", "Travel", "Mystery", "Historical Fiction", "Sequential Art", "Classics", "Philosophy", "Romance", "Womens Fiction", "Fiction", "Childrens", "Religion", "Nonfiction", "Music", "Default"]
for i in liste:
    if i in title:
        print("Found!" + " " + i)
print(title)




import json
import threading
import queue
import time

# 1. Die Warteschlange erstellen
data_queue = queue.Queue()
data_file = "daten.json"

def file_writer_worker():
    """Dieser Thread läuft im Hintergrund und schreibt als Einziger in die Datei."""
    while True:
        # Hole Daten aus der Queue (blockiert, bis etwas da ist)
        item = data_queue.get()
        
        if item is None: # Signal zum Beenden
            break
            
        # Hier findet der eigentliche Schreibvorgang statt
        try:
            # Bestehende Daten laden
            try:
                with open(data_file, "r") as f:
                    content = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                content = []

            content.append(item)

            # Zurückschreiben
            with open(data_file, "w") as f:
                json.dump(content, f, indent=4)
                
            print(f"Writer: {item} gespeichert.")
        finally:
            # Markiere die Aufgabe als erledigt
            data_queue.task_done()

# 2. Den Writer-Thread starten
writer_thread = threading.Thread(target=file_writer_worker, daemon=True)
writer_thread.start()

# 3. Beispiel für Arbeits-Threads (Worker), die Daten produzieren
def worker_task(worker_id):
    for i in range(3):
        data = {"worker": worker_id, "val": i, "timestamp": time.time()}
        data_queue.put(data) # Daten einfach in die Queue werfen
        time.sleep(0.5)

# Starte mehrere Worker-Threads
threads = []
for i in range(3):
    t = threading.Thread(target=worker_task, args=(i,))
    t.start()
    threads.append(t)

# Warten, bis alle Worker fertig sind
for t in threads:
    t.join()

# Warten, bis die Queue leer ist
data_queue.join()

print("Alle Daten wurden erfolgreich serialisiert.")
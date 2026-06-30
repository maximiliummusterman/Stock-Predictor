import json
import duden
import time, tqdm
from collections import deque
import multiprocessing

# TODO: - ausreizen wie viele wörter man durchlaufen kann, duden abbricht - gerade 86

anzahlen = {}
wörter = []

with open('found_words.json', 'r') as f:
    for line in tqdm.tqdm(f, desc="Datei wird gelesen"):
        for i in json.loads(line).values():
            wörter.append(i)

# def synonyme_ergänzen():
#     if duden.get(word) is not None:
#         synonyme = duden.get(word).synonyms
#         if synonyme:
#             for synonym in synonyme:
#                 try:
#                     data = anzahlen[word]
#                 except KeyError:
#                 # Handle the missing key logic here
#                     continue
#                 if synonym in anzahlen.keys():
#                     anzahlen[word] += anzahlen[synonym]
#                     del anzahlen[synonym]
#                     time.sleep(0.0)

flat_list = [item for sublist in wörter for item in tqdm.tqdm(sublist, desc="Flache Liste wird erstellt")]
flat_list = [item.lower() for item in flat_list]
anzahlen = {i: flat_list.count(i) for i in tqdm.tqdm(set(flat_list), desc="Anzahlen werden berechnet")}

anzahlen = dict(sorted(anzahlen.items(), key=lambda item: item[1]))
# letzte_elemente = deque(anzahlen.items(),)
# anzahlen = dict(letzte_elemente)
# print(anzahlen)
# print(len(anzahlen))
# anzahlen2 = anzahlen.copy()
# print(anzahlen2)

with open('anzahlen.json', 'w') as f:
    json.dump(anzahlen, f)
# for word in tqdm.tqdm(anzahlen2.keys(), desc="Verarbeitung läuft"):
#     synonyme_ergänzen()

print(anzahlen)
print(len(anzahlen))
print(max(anzahlen, key=anzahlen.get))
print(anzahlen["bmw"])

# def url_sortieren():
#     with open('links.csv', 'r') as f:
#         flat_list = [item for f in wörter for item in tqdm.tqdm(f, desc="Flache Liste wird erstellt")]
#         for i in tqdm.tqdm(flat_list, desc="Verarbeitung läuft"):
#             if i in flat_list:
#                 flat_list.remove(i)
#     with open('links.csv', 'w') as f:
#         for item in tqdm.tqdm(flat_list, desc="Datei wird geschrieben"):
#             f.write("%s\n" % item)

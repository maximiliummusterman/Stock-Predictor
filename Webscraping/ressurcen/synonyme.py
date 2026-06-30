import duden

# WICHTIG: Nutze "Loeffel" fuer die direkte Abfrage (URL-konform)
wort = duden.get('Gegenstand')  # Beispielwort, hier "Gegenstand"

if wort:
    # 'title' gibt meist "Löffel, der" zurueck
    print(f"Vollständiger Titel: {wort.title}") 
    
    # 'name' ist das reine Wort
    print(f"Wort: {wort.name}")            
    
    # Weitere korrekte Attribute laut Dokumentation:
    print(f"Artikel: {wort.article}")      
    print(f"Wortart: {wort.part_of_speech}")
    print(f"Häufigkeit: {wort.frequency}/5")
    
    # 'synonyms' ist eine Liste oder ein String (je nach Version)
    print(f"Synonyme: {wort.synonyms}")
else:
    print("Wort wurde nicht gefunden.")
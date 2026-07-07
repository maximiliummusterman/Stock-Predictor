from datetime import date, timedelta

start_datum = date(2026, 1, 1)
end_datum = date(2026, 12, 31)
delta_ein_tag = timedelta(days=1)
delta_eine_woche = timedelta(days=7)

aktuelles_datum = start_datum

while aktuelles_datum <= end_datum:
    datum_vor_woche = aktuelles_datum - delta_eine_woche
    print(f"Aktuell: {aktuelles_datum} | Vor einer Woche: {datum_vor_woche}")
    print(datum_vor_woche.strftime("%Y"))
    
    aktuelles_datum += delta_ein_tag

print 
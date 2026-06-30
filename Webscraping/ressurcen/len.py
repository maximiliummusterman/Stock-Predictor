import json

b = []
with open('anzahlen.json', 'r') as f:

    a = json.loads(f.read())
    for i in a:
        if a[i] != 1:
            b.append(i)

print(b)
print(len(b))
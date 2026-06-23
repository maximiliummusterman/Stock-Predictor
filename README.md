# Stock MAP Training

Einmal Pfade in `train_config.json` eintragen, danach immer:

```bash
python train.py
```

## Wichtige Dateien

- `train.py`: Training mit Config/Defaults
- `stock_map_model.py`: Modell
- `train_config.json`: hier deine Pfade und Hyperparameter eintragen

## Datenformat

`train.jsonl`, ein Beispiel pro Zeile:

```json
{"date":"2025-01-02", "words":{"revenue":4, "guidance":2}, "targets":{"AAPL":1, "MSFT":0}}
```

Targets:

- `1`: nächster Tag >= +0.2%
- `0`: neutral
- `-1`: nächster Tag <= -0.2%

## Config erzeugen

```bash
python train.py --write-config
```

## Einzelne Werte überschreiben

```bash
python train.py --epochs 50 --lr 0.00005
```

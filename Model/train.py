"""
train.py

Training fuer StockMovementMAP mit festen Standardpfaden.

Normaler Start:
    python train.py

Die Pfade stehen entweder oben in DEFAULTS oder in train_config.json.
CLI-Argumente ueberschreiben beides:
    python train.py --train-data data/train.jsonl --vocab data/vocab.json --symbols data/symbols.json

Erwartete Trainingszeile in JSONL:
    {"date":"2025-01-02", "words":{"revenue":4}, "targets":{"AAPL":1, "MSFT":0}}

Targets:
    -1 = fallend  <= -0.2%
     0 = neutral  zwischen -0.2% und +0.2%
    +1 = steigend >= +0.2%

Fehlende Targets werden als -999 codiert und in der Loss ignoriert.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset, random_split
from tqdm import tqdm

from Model.stock_map_model import (
    StockMAPConfig,
    StockMovementMAP,
    count_parameters,
    movement_loss,
    save_model,
)


MISSING_TARGET = -999


# =============================================================================
# 1. STANDARDWERTE: HIER EINMAL AENDERN, DANN NUR NOCH: python train.py
# =============================================================================

DEFAULTS: dict[str, Any] = {
    # Pfade
    "train_data": "example_train.jsonl",
    "vocab": "example_vocab.json",
    "symbols": "example_symbols.json",
    "out": "example_stock_map.pt",

    # Training
    "epochs": 20,
    "batch_size": 32,
    "lr": 1e-4,
    "weight_decay": 1e-2,
    "grad_clip_norm": 1.0,
    "val_fraction": 0.15,
    "seed": 42,
    "num_workers": 0,

    # Modellgroesse: etwa 25M Parameter, je nach vocab_size leicht anders
    "n_symbols": 40,
    "d_model": 1024,
    "input_rank": 64,
    "n_blocks": 4,
    "ffn_dim": 2944,
    "dropout": 0.10,
    "apply_signed_log1p": True,

    # Optional: neutral kleiner gewichten, falls sehr viele 0-Targets vorkommen.
    # None = keine Gewichtung, 0.5 = neutrale Klasse nur halb so stark.
    "neutral_weight": None,
}


@dataclass
class TrainSettings:
    train_data: str
    vocab: str
    symbols: str
    out: str

    epochs: int
    batch_size: int
    lr: float
    weight_decay: float
    grad_clip_norm: float
    val_fraction: float
    seed: int
    num_workers: int

    n_symbols: int
    d_model: int
    input_rank: int
    n_blocks: int
    ffn_dim: int
    dropout: float
    apply_signed_log1p: bool

    neutral_weight: float | None


def choose_device() -> torch.device:
    if torch.cuda.is_available():
        print("Nutze NVIDIA GPU:", torch.cuda.get_device_name(0))
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        print("Nutze Apple MPS")
        return torch.device("mps")
    print("Nutze CPU")
    return torch.device("cpu")


def load_config_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Config muss ein JSON-Objekt sein: {path}")
    return obj


def write_config_template(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Config-Vorlage geschrieben: {path}")


def merge_settings(config_path: str | Path, cli_args: argparse.Namespace) -> TrainSettings:
    values = dict(DEFAULTS)
    values.update(load_config_file(config_path))

    # CLI-Argumente ueberschreiben DEFAULTS und Config nur, wenn sie gesetzt wurden.
    for key, value in vars(cli_args).items():
        if key in {"config", "write_config"}:
            continue
        if value is not None:
            values[key] = value

    allowed = set(TrainSettings.__dataclass_fields__.keys())
    unknown = sorted(set(values.keys()) - allowed)
    if unknown:
        raise ValueError(f"Unbekannte Config-Keys: {unknown}")

    return TrainSettings(**values)


def load_json_or_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Datei ist leer: {path}")

    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"Zeile {line_no} ist kein JSON-Objekt: {path}")
            rows.append(obj)
        return rows

    obj = json.loads(text)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("examples"), list):
        return obj["examples"]
    raise ValueError("Trainingsdatei muss JSON-Liste, JSONL oder {'examples': [...]} sein.")


def load_vocab(path: str | Path) -> list[str]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(obj, list):
        vocab = [str(w) for w in obj]
    elif isinstance(obj, dict):
        # Variante 1: {"word": index} -> nach Index sortieren.
        if all(isinstance(v, int) for v in obj.values()):
            vocab = [w for w, _ in sorted(obj.items(), key=lambda kv: kv[1])]
        else:
            # Variante 2: {"word": scalar} -> Keys sind der feste Katalog.
            # Die Skalare muessen dann schon in words/word_counts eingerechnet sein,
            # oder du passt encode_words_to_vector() unten entsprechend an.
            vocab = list(obj.keys())
    else:
        raise ValueError("vocab.json muss Liste oder Dict sein.")

    if len(vocab) != len(set(vocab)):
        raise ValueError("vocab.json enthaelt doppelte Woerter.")
    if not vocab:
        raise ValueError("vocab.json ist leer.")
    return vocab


def load_symbols(path: str | Path) -> list[str]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError("symbols.json muss eine Liste sein.")
    symbols = [str(s) for s in obj]
    if len(symbols) != len(set(symbols)):
        raise ValueError("symbols.json enthaelt doppelte Symbole.")
    if not symbols:
        raise ValueError("symbols.json ist leer.")
    return symbols


def get_words_dict(example: dict[str, Any]) -> dict[str, float]:
    for key in ("words", "word_counts", "x", "features"):
        value = example.get(key)
        if isinstance(value, dict):
            return {str(k): float(v) for k, v in value.items()}
    raise ValueError("Beispiel braucht ein Dict unter 'words', 'word_counts', 'x' oder 'features'.")


def get_targets(example: dict[str, Any]) -> Any:
    for key in ("targets", "target", "y", "labels"):
        if key in example:
            return example[key]
    raise ValueError("Beispiel braucht Targets unter 'targets', 'target', 'y' oder 'labels'.")


def encode_words_to_vector(words: dict[str, float], word_to_idx: dict[str, int], vocab_size: int) -> torch.Tensor:
    x = torch.zeros(vocab_size, dtype=torch.float32)
    for word, value in words.items():
        idx = word_to_idx.get(word)
        if idx is not None:
            x[idx] = float(value)
    return x


def encode_targets_to_vector(targets: Any, symbols: list[str]) -> torch.Tensor:
    n_symbols = len(symbols)

    if isinstance(targets, list):
        if len(targets) != n_symbols:
            raise ValueError(f"Target-Liste hat Laenge {len(targets)}, erwartet {n_symbols}.")
        return torch.tensor([int(v) for v in targets], dtype=torch.long)

    if isinstance(targets, dict):
        y = torch.full((n_symbols,), MISSING_TARGET, dtype=torch.long)
        symbol_to_idx = {s: i for i, s in enumerate(symbols)}
        for symbol, value in targets.items():
            idx = symbol_to_idx.get(str(symbol))
            if idx is not None:
                y[idx] = int(value)
        return y

    raise ValueError("Targets muessen Dict {symbol: -1/0/1} oder Liste in Symbol-Reihenfolge sein.")


class StockJsonDataset(Dataset):
    def __init__(self, examples: list[dict[str, Any]], vocab: list[str], symbols: list[str]) -> None:
        self.examples = examples
        self.vocab = vocab
        self.symbols = symbols
        self.word_to_idx = {w: i for i, w in enumerate(vocab)}

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        example = self.examples[idx]
        words = get_words_dict(example)
        targets = get_targets(example)
        x = encode_words_to_vector(words, self.word_to_idx, len(self.vocab))
        y = encode_targets_to_vector(targets, self.symbols)
        return x, y


def accuracy_by_known_targets(logits: torch.Tensor, y_raw: torch.Tensor) -> float:
    pred = torch.argmax(logits, dim=-1) - 1
    mask = y_raw != MISSING_TARGET
    if mask.sum().item() == 0:
        return float("nan")
    return (pred[mask] == y_raw[mask]).float().mean().item()


def make_class_weights(device: torch.device, neutral_weight: float | None) -> torch.Tensor | None:
    if neutral_weight is None:
        return None
    # Reihenfolge in movement_loss: [-1, 0, +1] => Klassen [0, 1, 2]
    return torch.tensor([1.0, float(neutral_weight), 1.0], dtype=torch.float32, device=device)


def validate_settings(settings: TrainSettings) -> None:
    paths = {
        "train_data": settings.train_data,
        "vocab": settings.vocab,
        "symbols": settings.symbols,
    }
    missing = [f"{name}={path}" for name, path in paths.items() if not Path(path).exists()]
    if missing:
        msg = "\n".join(f"  - {item}" for item in missing)
        raise FileNotFoundError(
            "Diese Eingabedateien fehlen:\n"
            f"{msg}\n\n"
            "Loesung: Pfade oben in DEFAULTS aendern, train_config.json anpassen, "
            "oder einmalig per CLI ueberschreiben."
        )
    if not (0.0 < settings.val_fraction < 1.0):
        raise ValueError("val_fraction muss zwischen 0 und 1 liegen.")
    if settings.batch_size < 1:
        raise ValueError("batch_size muss >= 1 sein.")
    if settings.epochs < 1:
        raise ValueError("epochs muss >= 1 sein.")
    if settings.lr <= 0:
        raise ValueError("lr muss > 0 sein.")


def train(settings: TrainSettings) -> None:
    validate_settings(settings)

    random.seed(settings.seed)
    torch.manual_seed(settings.seed)

    device = choose_device()

    vocab = load_vocab(settings.vocab)
    symbols = load_symbols(settings.symbols)
    examples = load_json_or_jsonl(settings.train_data)

    if len(symbols) != settings.n_symbols:
        raise ValueError(f"symbols.json hat {len(symbols)} Symbole, n_symbols ist {settings.n_symbols}.")
    if len(examples) < 2:
        raise ValueError("Du brauchst mindestens 2 Beispiele fuer Training/Validierung.")

    dataset = StockJsonDataset(examples, vocab, symbols)

    val_size = max(1, int(len(dataset) * settings.val_fraction))
    val_size = min(val_size, len(dataset) - 1)
    train_size = len(dataset) - val_size

    train_ds, val_ds = random_split(
        dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(settings.seed),
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=settings.batch_size,
        shuffle=True,
        drop_last=False,
        num_workers=settings.num_workers,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=settings.batch_size,
        shuffle=False,
        drop_last=False,
        num_workers=settings.num_workers,
    )

    config = StockMAPConfig(
        vocab_size=len(vocab),
        n_symbols=len(symbols),
        d_model=settings.d_model,
        input_rank=settings.input_rank,
        n_blocks=settings.n_blocks,
        ffn_dim=settings.ffn_dim,
        dropout=settings.dropout,
        apply_signed_log1p=settings.apply_signed_log1p,
    )
    model = StockMovementMAP(config).to(device)

    print("\nKonfiguration:")
    print(json.dumps(asdict(settings), indent=2, ensure_ascii=False))
    print(f"\nBeispiele: {len(dataset):,} | Train: {train_size:,} | Val: {val_size:,}")
    print(f"Vokabular: {len(vocab):,} | Symbole: {len(symbols):,}")
    print(f"Parameter: {count_parameters(model):,}\n")

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=settings.lr,
        weight_decay=settings.weight_decay,
    )

    class_weights = make_class_weights(device, settings.neutral_weight)
    best_val_loss = float("inf")
    out_path = Path(settings.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, settings.epochs + 1):
        model.train()
        train_loss_sum = 0.0
        train_acc_sum = 0.0
        train_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{settings.epochs}")
        for x, y in pbar:
            x = x.to(device)
            y = y.to(device)

            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            loss = movement_loss(logits, y, class_weights=class_weights)
            loss.backward()

            if settings.grad_clip_norm > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), settings.grad_clip_norm)

            optimizer.step()

            acc = accuracy_by_known_targets(logits.detach(), y)
            train_loss_sum += float(loss.detach().cpu())
            train_acc_sum += acc
            train_batches += 1
            pbar.set_postfix(
                loss=f"{train_loss_sum / train_batches:.4f}",
                acc=f"{train_acc_sum / train_batches:.3f}",
            )

        model.eval()
        val_loss_sum = 0.0
        val_acc_sum = 0.0
        val_batches = 0

        with torch.no_grad():
            for x, y in val_loader:
                x = x.to(device)
                y = y.to(device)
                logits = model(x)
                loss = movement_loss(logits, y, class_weights=class_weights)
                acc = accuracy_by_known_targets(logits, y)
                val_loss_sum += float(loss.detach().cpu())
                val_acc_sum += acc
                val_batches += 1

        train_loss = train_loss_sum / max(1, train_batches)
        train_acc = train_acc_sum / max(1, train_batches)
        val_loss = val_loss_sum / max(1, val_batches)
        val_acc = val_acc_sum / max(1, val_batches)

        print(
            f"Epoch {epoch:03d} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.3f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.3f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            save_model(
                model,
                out_path,
                symbols=symbols,
                vocab=vocab,
                extra={
                    "best_val_loss": best_val_loss,
                    "epoch": epoch,
                    "settings": asdict(settings),
                    "label_meaning": {"-1": "<= -0.2%", "0": "neutral", "1": ">= +0.2%"},
                },
            )
            print(f"  gespeichert: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trainiert StockMovementMAP. Ohne Argumente nutzt es DEFAULTS/train_config.json."
    )

    parser.add_argument(
        "--config",
        default="train_config_example.json",
        help="Optionale JSON-Config. Wird geladen, falls vorhanden. Default: train_config.json",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="Schreibt eine train_config.json-Vorlage und beendet das Programm.",
    )

    # Pfade
    parser.add_argument("--train-data", dest="train_data", default=None)
    parser.add_argument("--vocab", default=None)
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--out", default=None)

    # Training
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--weight-decay", dest="weight_decay", type=float, default=None)
    parser.add_argument("--grad-clip-norm", dest="grad_clip_norm", type=float, default=None)
    parser.add_argument("--val-fraction", dest="val_fraction", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--num-workers", dest="num_workers", type=int, default=None)

    # Modell
    parser.add_argument("--n-symbols", dest="n_symbols", type=int, default=None)
    parser.add_argument("--d-model", dest="d_model", type=int, default=None)
    parser.add_argument("--input-rank", dest="input_rank", type=int, default=None)
    parser.add_argument("--n-blocks", dest="n_blocks", type=int, default=None)
    parser.add_argument("--ffn-dim", dest="ffn_dim", type=int, default=None)
    parser.add_argument("--dropout", type=float, default=None)
    parser.add_argument("--apply-signed-log1p", dest="apply_signed_log1p", action="store_true", default=None)
    parser.add_argument("--no-signed-log1p", dest="apply_signed_log1p", action="store_false")

    parser.add_argument("--neutral-weight", dest="neutral_weight", type=float, default=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_config:
        write_config_template(args.config)
        return

    settings = merge_settings(args.config, args)
    train(settings)


if __name__ == "__main__":
    main()

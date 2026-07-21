
"""
stock_map_model.py

Nur das Modell + Loss-Helfer für:
    Input:  fester Wörterkatalog als Skalarvektor [batch, vocab_size]
    Output: 40 Aktiensymbole × 3 Klassen
            Klasse 0 -> -1  fallend:  <= -0.2%
            Klasse 1 ->  0  neutral:  (-0.2%, +0.2%)
            Klasse 2 -> +1  steigend: >= +0.2%

Die Architektur ist absichtlich daten-/scraper-unabhängig.
Default-Konfiguration liegt bei ca. 25M Parametern, abhängig von vocab_size.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class StockMAPConfig:
    vocab_size: int
    n_symbols: int = 40
    n_classes: int = 3

    # Default: ca. 25M Parameter bei vocab_size um 5k-20k.
    d_model: int = 1024
    input_rank: int = 64
    n_blocks: int = 4
    ffn_dim: int = 2944

    dropout: float = 0.10
    apply_signed_log1p: bool = True


def signed_log1p(x: torch.Tensor) -> torch.Tensor:
    """
    Stabilisiert große positive/negative Wortskalarwerte:
        x -> sign(x) * log(1 + abs(x))

    Abschaltbar über config.apply_signed_log1p=False.
    """
    return torch.sign(x) * torch.log1p(torch.abs(x))


class ResidualFFNBlock(nn.Module):
    """
    PreNorm-Residual-MLP-Block:
        x -> x + FFN(LayerNorm(x))

    Für tabellarische / Bag-of-Words-artige Skalarfeatures meist sinnvoller
    als ein Transformer, weil keine Token-Sequenz mehr verarbeitet wird,
    sondern schon ein fester Wörterkatalogvektor.
    """

    def __init__(self, d_model: int, ffn_dim: int, dropout: float) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, ffn_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_dim, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.ffn(self.norm(x))


class StockMovementMAP(nn.Module):
    """
    Multi-Asset-Predictor:
        Wörterkatalog-Skalarvektor des Vortages
        -> Logits für alle Symbole des nächsten Tages.

    Forward:
        x:      FloatTensor [batch, vocab_size] oder [vocab_size]
        return: FloatTensor [batch, n_symbols, 3]
                letzte Dimension = Klassenlogits für [-1, 0, +1]
    """

    def __init__(self, config: StockMAPConfig) -> None:
        super().__init__()

        if config.n_classes != 3:
            raise ValueError("Dieses Modell erwartet genau 3 Klassen: -1, 0, +1.")
        if config.vocab_size <= 0:
            raise ValueError("vocab_size muss positiv sein.")
        if config.n_symbols <= 0:
            raise ValueError("n_symbols muss positiv sein.")

        self.config = config

        # Faktorisiertes Input-Mapping:
        # Spart Parameter gegenüber Linear(vocab_size -> d_model),
        # bleibt aber flexibel für große feste Wörterkataloge.
        self.input_projection = nn.Sequential(
            nn.Linear(config.vocab_size, config.input_rank, bias=False),
            nn.GELU(),
            nn.Linear(config.input_rank, config.d_model),
            nn.LayerNorm(config.d_model),
        )

        self.blocks = nn.Sequential(
            *[
                ResidualFFNBlock(
                    d_model=config.d_model,
                    ffn_dim=config.ffn_dim,
                    dropout=config.dropout,
                )
                for _ in range(config.n_blocks)
            ]
        )

        self.final_norm = nn.LayerNorm(config.d_model)

        # Gemeinsamer Artikelzustand -> alle Symbol-Klassenlogits.
        self.head = nn.Linear(config.d_model, config.n_symbols * config.n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        single_input = x.dim() == 1
        if single_input:
            x = x.unsqueeze(0)

        if x.dim() != 2:
            raise ValueError(f"x muss Form [batch, vocab_size] haben, bekommen: {tuple(x.shape)}")
        if x.shape[-1] != self.config.vocab_size:
            raise ValueError(
                f"Falsche vocab_size: erwartet {self.config.vocab_size}, bekommen {x.shape[-1]}"
            )

        x = x.float()
        if self.config.apply_signed_log1p:
            x = signed_log1p(x)

        h = self.input_projection(x)
        h = self.blocks(h)
        h = self.final_norm(h)

        logits = self.head(h)
        logits = logits.view(-1, self.config.n_symbols, self.config.n_classes)

        return logits.squeeze(0) if single_input else logits


def build_25m_model(
    vocab_size: int,
    n_symbols: int = 40,
    dropout: float = 0.10,
    input_rank: int = 64,
) -> StockMovementMAP:
    """
    Default-Fabrik für das gewünschte Setup.

    Parameterzahl ungefähr:
        vocab_size=5_000   -> 24.65M
        vocab_size=10_000  -> 24.97M
        vocab_size=20_000  -> 25.61M
        vocab_size=40_000  -> 26.89M
    """
    return StockMovementMAP(
        StockMAPConfig(
            vocab_size=vocab_size,
            n_symbols=n_symbols,
            d_model=1024,
            input_rank=input_rank,
            n_blocks=4,
            ffn_dim=2944,
            dropout=dropout,
            apply_signed_log1p=True,
        )
    )


def count_parameters(model: nn.Module, trainable_only: bool = True) -> int:
    params = model.parameters()
    if trainable_only:
        return sum(p.numel() for p in params if p.requires_grad)
    return sum(p.numel() for p in params)




def estimate_parameter_count(
    vocab_size: int,
    *,
    n_symbols: int = 40,
    n_classes: int = 3,
    d_model: int = 1024,
    input_rank: int = 64,
    n_blocks: int = 4,
    ffn_dim: int = 2944,
) -> int:
    """
    Parameterabschätzung ohne Modellinstanz.
    Entspricht der Default-Architektur in build_25m_model().
    """
    input_projection = (
        vocab_size * input_rank          # Linear(vocab -> rank), bias=False
        + input_rank * d_model + d_model # Linear(rank -> d_model)
        + 2 * d_model                    # LayerNorm
    )
    one_block = (
        2 * d_model                      # LayerNorm
        + d_model * ffn_dim + ffn_dim    # Linear(d_model -> ffn_dim)
        + ffn_dim * d_model + d_model    # Linear(ffn_dim -> d_model)
    )
    final_norm = 2 * d_model
    head = d_model * (n_symbols * n_classes) + (n_symbols * n_classes)
    return input_projection + n_blocks * one_block + final_norm + head


def encode_movement_targets(
    y: torch.Tensor,
    *,
    missing_value: int | float = -999,
    ignore_index: int = -100,
) -> torch.Tensor:
    """
    Wandelt Rohlabels in CrossEntropy-Klassenindizes um.

    Input y:
        Form [batch, n_symbols] oder [n_symbols]
        Werte:
            -1  -> Klasse 0
             0  -> Klasse 1
            +1  -> Klasse 2
        missing_value oder NaN -> ignore_index

    Output:
        LongTensor gleicher Form mit Werten {0,1,2,ignore_index}
    """
    y_float = y.float()
    out = torch.full(y.shape, ignore_index, dtype=torch.long, device=y.device)

    finite = torch.isfinite(y_float)
    missing = y_float == float(missing_value)
    valid_area = finite & (~missing)

    out[valid_area & (y_float == -1)] = 0
    out[valid_area & (y_float == 0)] = 1
    out[valid_area & (y_float == 1)] = 2

    invalid = valid_area & (y_float != -1) & (y_float != 0) & (y_float != 1)
    if invalid.any().item():
        bad_values = torch.unique(y_float[invalid]).detach().cpu().tolist()
        raise ValueError(f"Ungültige Target-Werte: {bad_values}. Erlaubt sind -1, 0, +1.")

    return out


def decode_movement_classes(class_ids: torch.Tensor) -> torch.Tensor:
    """
    Wandelt Klassenindizes zurück in Bewegungsskala:
        0 -> -1
        1 ->  0
        2 -> +1
    """
    mapping = torch.tensor([-1, 0, 1], dtype=torch.long, device=class_ids.device)
    return mapping[class_ids.long()]


def movement_loss(
    logits: torch.Tensor,
    y_raw: torch.Tensor,
    *,
    class_weights: Optional[torch.Tensor] = None,
    ignore_index: int = -100,
) -> torch.Tensor:
    """
    Multi-Symbol-CrossEntropy.

    logits:
        [batch, n_symbols, 3]

    y_raw:
        [batch, n_symbols] mit Rohlabels -1/0/+1.
        Für fehlende Labels NaN oder -999 verwenden.

    class_weights:
        Optional Tensor [3], z.B. um Neutral-Dominanz zu kompensieren.
        Reihenfolge: Klasse [-1, 0, +1] => [fallend, neutral, steigend].
    """
    if logits.dim() != 3 or logits.shape[-1] != 3:
        raise ValueError(f"logits muss Form [batch, n_symbols, 3] haben, bekommen: {tuple(logits.shape)}")

    targets = encode_movement_targets(y_raw, ignore_index=ignore_index).to(logits.device)

    if targets.shape != logits.shape[:2]:
        raise ValueError(
            f"Target-Form passt nicht: y={tuple(targets.shape)}, logits={tuple(logits.shape)}"
        )

    weights = class_weights.to(logits.device) if class_weights is not None else None

    return F.cross_entropy(
        logits.reshape(-1, 3),
        targets.reshape(-1),
        weight=weights,
        ignore_index=ignore_index,
    )


@torch.no_grad()
def predict_movements(
    model: StockMovementMAP,
    x: torch.Tensor,
    *,
    return_probabilities: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
    """
    Gibt pro Symbol die Bewegungsskala -1/0/+1 zurück.

    x:
        [batch, vocab_size] oder [vocab_size]

    return:
        pred: [batch, n_symbols] oder [n_symbols]
    """
    was_training = model.training
    model.eval()

    logits = model(x)
    probs = torch.softmax(logits, dim=-1)
    classes = torch.argmax(probs, dim=-1)
    pred = decode_movement_classes(classes)

    if was_training:
        model.train()

    if return_probabilities:
        return pred, probs
    return pred


def training_step(
    model: StockMovementMAP,
    optimizer: torch.optim.Optimizer,
    x: torch.Tensor,
    y_raw: torch.Tensor,
    *,
    class_weights: Optional[torch.Tensor] = None,
    grad_clip_norm: Optional[float] = 1.0,
) -> float:
    """
    Ein einzelner Trainingsschritt; kein Dataset/Scraper enthalten.

    x:
        [batch, vocab_size]

    y_raw:
        [batch, 40] mit -1/0/+1.
    """
    model.train()
    optimizer.zero_grad(set_to_none=True)

    logits = model(x)
    loss = movement_loss(logits, y_raw, class_weights=class_weights)
    loss.backward()

    if grad_clip_norm is not None:
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)

    optimizer.step()
    return float(loss.detach().cpu())


def save_model(
    model: StockMovementMAP,
    path: str | Path,
    *,
    symbols: Optional[list[str]] = None,
    vocab: Optional[list[str]] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """
    Speichert Modell + Konfiguration + optionale Symbol-/Vokabellisten.
    """
    payload = {
        "config": asdict(model.config),
        "state_dict": model.state_dict(),
        "symbols": symbols,
        "vocab": vocab,
        "extra": extra or {},
    }
    torch.save(payload, Path(path))


def load_model(
    path: str | Path,
    *,
    map_location: str | torch.device = "cpu",
) -> tuple[StockMovementMAP, dict[str, Any]]:
    """
    Lädt Modell und gibt zusätzlich Metadaten zurück.
    """
    payload = torch.load(Path(path), map_location=map_location)
    config = StockMAPConfig(**payload["config"])
    model = StockMovementMAP(config)
    model.load_state_dict(payload["state_dict"])

    metadata = {
        "symbols": payload.get("symbols"),
        "vocab": payload.get("vocab"),
        "extra": payload.get("extra", {}),
    }
    return model, metadata


if __name__ == "__main__":
    # Schneller Smoke-Test ohne echte Daten und ohne teuren Full-Model-Backward.
    print("Default-Parameterabschätzung:")
    for vocab_size in [5_000, 10_000, 20_000, 40_000]:
        print(f"  vocab_size={vocab_size:>6}: {estimate_parameter_count(vocab_size):,}")

    toy = StockMovementMAP(
        StockMAPConfig(
            vocab_size=32,
            n_symbols=4,
            d_model=16,
            input_rank=4,
            n_blocks=2,
            ffn_dim=32,
            dropout=0.0,
        )
    )

    x = torch.randn(3, 32)
    y = torch.tensor(
        [
            [-1, 0, 1, -999],
            [1, -1, 0, 1],
            [0, 0, -1, 1],
        ]
    )

    logits = toy(x)
    loss = movement_loss(logits, y)
    pred, probs = predict_movements(toy, x, return_probabilities=True)

    print("\nToy-Smoke-Test:")
    print("  logits:", tuple(logits.shape))
    print("  loss:", round(float(loss.detach()), 4))
    print("  pred:", tuple(pred.shape))
    print("  probs:", tuple(probs.shape))

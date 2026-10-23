"""ML-матчинг товаров каталога к типам работ (п. 3.1 ТЗ).

Схема:
    текст товара (name + marketing_description + characteristics)
        → эмбеддинг sentence-transformers (по умолчанию cointegrated/rubert-tiny2)
        → LogisticRegression (scikit-learn) → тип работ + вероятность (confidence)

Классы — коды из database.work_types плюс «other» (товар не относится ни к одной
работе: светильники, посуда, садовый инвентарь…). Без класса «other» модель
относила бы к какому-то типу работ каждый из 88 тыс. товаров каталога.

Обучение и запись предсказаний в БД — ml/pipeline.py.
Запуск обучения вручную:  python -m ml.matching train
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from database.work_types import ID_BY_CODE, OTHER_ID

logger = logging.getLogger(__name__)

ENCODER_NAME = os.getenv("ML_ENCODER", "cointegrated/rubert-tiny2")
ARTIFACT_DIR = Path(os.getenv("ML_ARTIFACT_DIR", "ml_artifacts"))
CONFIDENCE_THRESHOLD = float(os.getenv("ML_CONFIDENCE_THRESHOLD", "0.8"))
OTHER = "other"
ARTIFACT_FILE = "matcher.joblib"
ARTIFACT_VERSION = 1

MARKETING_KEY = "Маркетинговое описание товара"
MAX_TEXT_CHARS = 1200


# ------------------------------------------------------------------ текст товара


def product_text(name: str | None, marketing_description: str | None,
                 characteristics: Iterable[dict] | None) -> str:
    """Текст для эмбеддинга: название, маркетинговое описание, характеристики «имя: значение»."""
    parts = [(name or "").strip()]
    if marketing_description:
        parts.append(marketing_description.strip())
    chars = []
    for c in characteristics or []:
        n, v = c.get("name"), c.get("value")
        if not n or v in (None, "") or n == MARKETING_KEY:
            continue
        v = str(v).strip()
        if len(v) <= 80:
            chars.append(f"{n}: {v}")
    if chars:
        parts.append("; ".join(chars))
    return ". ".join(p for p in parts if p)[:MAX_TEXT_CHARS]


def text_of(product: Any) -> str:
    """Текст для объекта с полями модели Product."""
    return product_text(product.name, product.marketing_description, product.characteristics)


# ------------------------------------------------------------------ эмбеддинги


class Encoder(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceEncoder:
    """Обёртка над sentence-transformers с ленивой загрузкой модели.

    Модель скачивается с HuggingFace один раз (в Docker — при сборке образа,
    см. Dockerfile) и берётся из кеша HF_HOME. Для закрытого контура можно
    указать локальную папку с моделью в ML_ENCODER.
    """

    def __init__(self, model_name: str = ENCODER_NAME, device: str | None = None, batch_size: int = 64):
        self.name = model_name
        self.device = device or os.getenv("ML_DEVICE") or None   # None — sentence-transformers выберет сам (cuda/cpu)
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # тяжёлый импорт (torch) — только когда нужен
            t = time.monotonic()
            model = SentenceTransformer(self.name, device=self.device)
            model.max_seq_length = min(model.max_seq_length or 512, 256)
            self._model = model
            logger.info("Энкодер %s загружен за %.1f с", self.name, time.monotonic() - t)
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        with self._lock:
            model = self._load()
            vectors = model.encode(list(texts), batch_size=self.batch_size, normalize_embeddings=True,
                                   show_progress_bar=False, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)


# ------------------------------------------------------------------ обучение классификатора


@dataclass
class TrainResult:
    classifier: LogisticRegression
    classes: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)


def _make_classifier(seed: int) -> LogisticRegression:
    # class_weight="balanced": редкие типы работ (десятки товаров) не тонут в «other»
    return LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced", random_state=seed)


def evaluate(y_true: Sequence[str], proba: np.ndarray, classes: Sequence[str],
             threshold: float = CONFIDENCE_THRESHOLD) -> dict[str, Any]:
    """Метрики на отложенной выборке: F1 по типам работ и качество отсечения по порогу уверенности."""
    classes = list(classes)
    pred = [classes[i] for i in proba.argmax(axis=1)]
    conf = proba.max(axis=1)
    work = [c for c in classes if c != OTHER]
    p, r, f, s = precision_recall_fscore_support(y_true, pred, labels=work, zero_division=0)
    per_class = {c: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                     "f1": round(float(f[i]), 4), "support": int(s[i])} for i, c in enumerate(work)}
    y_true = list(y_true)
    # что попадёт в калькулятор: предсказан тип работ и уверенность ≥ порога
    accepted = [i for i, (pr, cf) in enumerate(zip(pred, conf)) if pr != OTHER and cf >= threshold]
    relevant = [i for i, yt in enumerate(y_true) if yt != OTHER]
    hit = sum(1 for i in accepted if pred[i] == y_true[i])
    return {
        "holdout_size": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "macro_f1": round(float(f1_score(y_true, pred, labels=work, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, pred, labels=work, average="weighted", zero_division=0)), 4),
        "threshold": threshold,
        "precision_at_threshold": round(hit / len(accepted), 4) if accepted else 0.0,
        "recall_at_threshold": round(hit / len(relevant), 4) if relevant else 0.0,
        "per_class": per_class,
    }


def train_classifier(X: np.ndarray, y: Sequence[str], *, seed: int = 42, test_size: float = 0.2,
                     threshold: float = CONFIDENCE_THRESHOLD) -> TrainResult:
    """Оценка на отложенных 20% (стратифицированно), затем дообучение на всех данных."""
    y_arr = np.asarray(y)
    labels, counts = np.unique(y_arr, return_counts=True)
    rare = set(labels[counts < 2])                 # такие классы не разделить — только в обучение
    idx = np.arange(len(y_arr))
    split_idx = np.array([i for i in idx if y_arr[i] not in rare])
    rare_idx = np.array([i for i in idx if y_arr[i] in rare], dtype=int)
    tr, te = train_test_split(split_idx, test_size=test_size, random_state=seed, stratify=y_arr[split_idx])
    tr = np.concatenate([tr, rare_idx])

    t = time.monotonic()
    holdout_clf = _make_classifier(seed).fit(X[tr], y_arr[tr])
    metrics = evaluate(list(y_arr[te]), holdout_clf.predict_proba(X[te]), list(holdout_clf.classes_), threshold)
    metrics["fit_seconds_holdout"] = round(time.monotonic() - t, 1)

    final = _make_classifier(seed).fit(X, y_arr)
    metrics["train_size"] = int(len(y_arr))
    metrics["class_counts"] = {str(k): int(v) for k, v in zip(labels, counts)}
    return TrainResult(final, [str(c) for c in final.classes_], metrics)


# ------------------------------------------------------------------ сервис инференса


class MLMatcher:
    """Предсказание типа работ для товара: predict(product) -> (work_type_id, confidence).

    work_type_id — id из database.work_types (0 — «нет подходящего типа работ»),
    confidence — вероятность предсказанного класса по классификатору.
    """

    def __init__(self, encoder: Encoder | None = None, artifact_dir: Path | str = ARTIFACT_DIR):
        self.encoder: Encoder = encoder or SentenceEncoder()
        self.artifact_dir = Path(artifact_dir)
        self.classifier: LogisticRegression | None = None
        self.classes: list[str] = []
        self.meta: dict[str, Any] = {}

    # --- состояние

    @property
    def ready(self) -> bool:
        return self.classifier is not None

    @property
    def artifact_path(self) -> Path:
        return self.artifact_dir / ARTIFACT_FILE

    def load(self) -> bool:
        """Загружает обученный классификатор, если он совместим с текущим энкодером."""
        path = self.artifact_path
        if not path.is_file():
            return False
        data = joblib.load(path)
        if data.get("version") != ARTIFACT_VERSION or data.get("encoder") != self.encoder.name:
            logger.warning("Артефакт %s обучен для другого энкодера/версии — нужно переобучение", path)
            return False
        self.classifier, self.classes, self.meta = data["classifier"], list(data["classes"]), data["meta"]
        return True

    def save(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.artifact_path.with_suffix(".tmp")
        joblib.dump({"version": ARTIFACT_VERSION, "encoder": self.encoder.name, "classifier": self.classifier,
                     "classes": self.classes, "meta": self.meta}, tmp)
        tmp.replace(self.artifact_path)

    # --- обучение

    def fit_embeddings(self, X: np.ndarray, labels: Sequence[str], extra_meta: dict | None = None) -> dict[str, Any]:
        result = train_classifier(X, labels)
        self.classifier, self.classes = result.classifier, result.classes
        self.meta = {"encoder": self.encoder.name, "trained_at": time.time(), "dim": int(X.shape[1]),
                     "metrics": result.metrics, **(extra_meta or {})}
        self.save()
        return self.meta

    # --- инференс

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return self.encoder.encode(texts)

    def predict_embeddings(self, X: np.ndarray) -> list[tuple[str | None, float]]:
        """[(код типа работ или None для «other», уверенность)] для матрицы эмбеддингов."""
        if self.classifier is None:
            raise RuntimeError("ML-модель ещё не обучена")
        proba = self.classifier.predict_proba(X)
        best = proba.argmax(axis=1)
        out = []
        for row, i in enumerate(best):
            code = self.classes[i]
            out.append((None if code == OTHER else code, float(proba[row, i])))
        return out

    def predict_texts(self, texts: Sequence[str]) -> list[tuple[str | None, float]]:
        return self.predict_embeddings(self.embed(texts))

    def predict_topk(self, texts: Sequence[str], k: int = 3) -> list[list[tuple[str | None, float]]]:
        """k самых вероятных классов для каждого текста (для админки и отладки)."""
        if self.classifier is None:
            raise RuntimeError("ML-модель ещё не обучена")
        proba = self.classifier.predict_proba(self.embed(texts))
        out = []
        for row in proba:
            top = np.argsort(row)[::-1][:k]
            out.append([(None if self.classes[i] == OTHER else self.classes[i], float(row[i])) for i in top])
        return out

    def predict(self, product: Any) -> tuple[int, float]:
        """Тип работ (id из справочника; 0 — не относится к работам) и уверенность модели."""
        code, conf = self.predict_texts([text_of(product)])[0]
        return (ID_BY_CODE.get(code, OTHER_ID) if code else OTHER_ID), conf

    def info(self) -> dict[str, Any]:
        return {"ready": self.ready, "encoder": self.encoder.name, "classes": len(self.classes),
                "threshold": CONFIDENCE_THRESHOLD, **{k: v for k, v in self.meta.items() if k != "metrics"}}


_matcher: MLMatcher | None = None
_matcher_lock = threading.Lock()


def get_matcher() -> MLMatcher:
    """Общий экземпляр для API: классификатор подгружается с диска, если уже обучен."""
    global _matcher
    with _matcher_lock:
        if _matcher is None:
            _matcher = MLMatcher()
            try:
                if _matcher.load():
                    logger.info("ML-матчер загружен: %s", _matcher.artifact_path)
            except Exception:  # noqa: BLE001 — повреждённый артефакт → переобучение
                logger.exception("Не удалось загрузить ML-артефакт")
        return _matcher


def main() -> None:
    """python -m ml.matching train [--sample-other N]"""
    import argparse
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Обучение ML-матчинга товаров к типам работ")
    parser.add_argument("command", choices=["train"])
    parser.add_argument("--sample-other", type=int, default=None, help="сколько товаров «other» брать в обучение")
    args = parser.parse_args()

    from ml.pipeline import run_training  # pipeline зависит от БД — импортируем только для CLI

    async def run() -> None:
        from database import engine
        result = await run_training(sample_other=args.sample_other)
        print({k: v for k, v in result.items() if k != "per_class"})
        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()

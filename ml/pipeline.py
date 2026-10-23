"""Обучение ML-матчинга на данных БД и запись предсказаний.

Шаги run_training():
  1. Тексты всех товаров → эмбеддинги (кеш на диске: пересчитываются только изменённые товары).
  2. Обучающая выборка: метки менеджера (приоритет) + слабая разметка правил
     (ml/weak_labels.py) + случайная выборка неразмеченных товаров как класс «other».
  3. LogisticRegression: оценка на отложенных 20%, затем обучение на всём.
  4. Предсказание для каждого товара → product.work_type / match_confidence / match_source="ml".
     Товары, подтверждённые менеджером, сохраняют его метку (confidence = 1.0).
  5. Где тип работ сменился, фасовка и влагостойкость пересчитываются (derive_fields) —
     формулы расхода при этом не меняются.
  6. Тип работ категорий, запись версии модели и статистики в ml_model.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from sqlalchemy import bindparam, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.catalog_parser import chars_dict, derive_fields
from database.db_engine import engine
from database.models import Category, MLModel, Product, WorkType
from database.work_types import WORK_TYPES, work_type_rows
from ml.matching import CONFIDENCE_THRESHOLD, OTHER, MLMatcher, get_matcher, product_text
from ml.weak_labels import weak_label

logger = logging.getLogger(__name__)

# Состояние обучения — его отдают /api/v1/health и /api/v1/ml/status
ML_STATUS: dict[str, Any] = {"state": "idle"}
_train_lock = asyncio.Lock()

ENCODE_CHUNK = 2048
WRITE_CHUNK = 5000
MAX_OTHER = 20000


# ------------------------------------------------------------------ кеш эмбеддингов


def _cache_path(matcher: MLMatcher):
    slug = re.sub(r"[^\w.-]+", "_", matcher.encoder.name)
    return matcher.artifact_dir / f"embeddings_{slug}.npz"


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


async def embed_all(matcher: MLMatcher, ids: list[int], texts: list[str]) -> np.ndarray:
    """Эмбеддинги в порядке ids. Неизменённые тексты берутся из кеша."""
    path = _cache_path(matcher)
    hashes = [_text_hash(t) for t in texts]
    cached: dict[int, tuple[str, int]] = {}
    old = None
    if path.is_file():
        data = np.load(path, allow_pickle=False)
        old = data["vectors"]
        cached = {int(i): (str(h), n) for n, (i, h) in enumerate(zip(data["ids"], data["hashes"]))}

    todo = [n for n, (pid, h) in enumerate(zip(ids, hashes)) if cached.get(pid, ("",))[0] != h]
    ML_STATUS.update(stage="embedding", total=len(todo), processed=0)
    new_vectors: dict[int, np.ndarray] = {}
    t = time.monotonic()
    for start in range(0, len(todo), ENCODE_CHUNK):
        part = todo[start:start + ENCODE_CHUNK]
        vecs = await asyncio.to_thread(matcher.embed, [texts[n] for n in part])
        for n, v in zip(part, vecs):
            new_vectors[n] = v
        ML_STATUS["processed"] = start + len(part)
    if todo:
        logger.info("Эмбеддинги: %d новых текстов за %.0f с, из кеша %d", len(todo), time.monotonic() - t,
                    len(ids) - len(todo))

    dim = next(iter(new_vectors.values())).shape[0] if new_vectors else (old.shape[1] if old is not None else 0)
    X = np.zeros((len(ids), dim), dtype=np.float32)
    for n, pid in enumerate(ids):
        if n in new_vectors:
            X[n] = new_vectors[n]
        else:
            X[n] = old[cached[pid][1]]  # type: ignore[index]
    if todo:
        matcher.artifact_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.stem + ".tmp.npz")
        np.savez(tmp, ids=np.asarray(ids, dtype=np.int64), hashes=np.asarray(hashes), vectors=X)
        tmp.replace(path)
    return X


# ------------------------------------------------------------------ обучающая выборка


def build_training_set(rows: list[dict], categories: dict[int, str], *, sample_other: int | None = None,
                       seed: int = 42) -> tuple[list[int], list[str], dict[str, int]]:
    """Индексы строк и метки для обучения. Возвращает также, откуда метки."""
    labeled_idx, labels, sources = [], [], Counter()
    unlabeled = []
    for n, r in enumerate(rows):
        wl = weak_label(categories.get(r["category_id"] or -1), r["name"])
        r["weak_label"] = wl   # с этой подсказкой импорт разбирал фасовку
        if r["label_source"] == "manager" and r["label_work_type"]:
            labeled_idx.append(n)
            labels.append(r["label_work_type"])
            sources["manager"] += 1
            continue
        if wl:
            labeled_idx.append(n)
            labels.append(wl)
            sources["rules"] += 1
        else:
            unlabeled.append(n)
    positives = sum(1 for lb in labels if lb != OTHER)
    k = min(len(unlabeled), sample_other if sample_other is not None else min(MAX_OTHER, 3 * positives))
    other = random.Random(seed).sample(unlabeled, k)
    sources["other_sampled"] = len(other)
    return labeled_idx + other, labels + [OTHER] * len(other), dict(sources)


# ------------------------------------------------------------------ основной сценарий


async def _load_rows() -> tuple[list[dict], dict[int, str]]:
    async with engine.connect() as conn:
        cats = dict((await conn.execute(select(Category.id, Category.name))).all())
        res = await conn.execute(select(
            Product.id, Product.name, Product.marketing_description, Product.characteristics, Product.category_id,
            Product.unit, Product.price, Product.label_work_type, Product.label_source, Product.match_source,
            Product.work_type,
        ).order_by(Product.id))
        rows = [dict(r._mapping) for r in res]
    return rows, cats


def _confidence_histogram(conf: list[float]) -> list[dict[str, Any]]:
    bins = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0001]
    counts = np.histogram(conf, bins=bins)[0] if conf else [0] * (len(bins) - 1)
    return [{"from": bins[i], "to": min(1.0, bins[i + 1]), "count": int(c)} for i, c in enumerate(counts)]


@dataclass
class TrainOutput:
    updates: list[dict]            # предсказания для записи в product
    rederive: list[dict]           # пересчитанные фасовка/влагостойкость
    final_types: list[str | None]
    preds: list[tuple[str | None, float]]
    metrics: dict[str, Any]
    label_sources: dict[str, int]
    prediction_stats: dict[str, Any]


async def train_and_predict(rows: list[dict], categories: dict[int, str], matcher: MLMatcher, *,
                            sample_other: int | None = None) -> TrainOutput:
    """Шаги 1–5 без записи в БД: эмбеддинги, обучение, предсказания, пересчёт фасовки."""
    started = time.monotonic()
    # 1. эмбеддинги всех товаров
    ids = [r["id"] for r in rows]
    texts = [product_text(r["name"], r["marketing_description"], r["characteristics"]) for r in rows]
    X = await embed_all(matcher, ids, texts)

    # 2–3. обучение
    ML_STATUS.update(stage="training")
    train_idx, train_labels, label_sources = build_training_set(rows, categories, sample_other=sample_other)
    meta = await asyncio.to_thread(matcher.fit_embeddings, X[train_idx], train_labels,
                                   {"label_sources": label_sources})
    metrics = meta["metrics"]
    logger.info("ML-матчинг обучен: macro F1 %.3f, precision@%.2f %.3f (holdout %d)",
                metrics["macro_f1"], CONFIDENCE_THRESHOLD, metrics["precision_at_threshold"],
                metrics["holdout_size"])

    # 4. предсказания для всех товаров
    ML_STATUS.update(stage="predicting")
    preds = await asyncio.to_thread(matcher.predict_embeddings, X)
    updates, rederive = [], []
    final_types: list[str | None] = []
    for r, (code, conf) in zip(rows, preds):
        if r["label_source"] == "manager":
            lt = r["label_work_type"]
            code, conf, source = (None if lt == OTHER else lt), 1.0, "manager"
            label, label_source = r["label_work_type"], "manager"
        else:
            source = "ml"
            label = r.get("weak_label")
            label_source = "rules" if label else None
        final_types.append(code)
        updates.append({"pid": r["id"], "wt": code, "conf": round(conf, 4), "src": source,
                        "lbl": label, "lsrc": label_source})
        # 5. фасовку при импорте разбирали с подсказкой метки правил — пересчёт, если тип другой
        #    (или прошлая версия модели уже меняла тип этого товара)
        if code != r["weak_label"] or r["work_type"] != r["weak_label"]:
            chars = chars_dict(r["characteristics"])
            fields = derive_fields(r["name"], r["unit"], chars, Decimal(r["price"] or 0), code)
            rederive.append({"pid": r["id"], **{f"d_{k}": v for k, v in fields.items()}})

    # статистика предсказаний
    conf_ml = [u["conf"] for u in updates if u["wt"] and u["src"] == "ml"]
    accepted = [u for u in updates if u["wt"] and (u["src"] == "manager" or u["conf"] >= CONFIDENCE_THRESHOLD)]
    weak = [(u, r["weak_label"]) for u, r in zip(updates, rows) if r["weak_label"] and u["src"] == "ml"]
    prediction_stats = {
        "products": len(rows),
        "predicted": sum(1 for u in updates if u["wt"]),
        "accepted": len(accepted),
        "accepted_by_type": dict(Counter(u["wt"] for u in accepted)),
        # уверенные предсказания там, где правила ничего не нашли — то, ради чего нужна модель
        "new_beyond_rules": sum(1 for u, r in zip(updates, rows)
                                if u["wt"] and u["src"] == "ml" and u["conf"] >= CONFIDENCE_THRESHOLD
                                and not r["weak_label"]),
        # совпадение с правилами на размеченных ими товарах (in-sample, оптимистичная оценка)
        "agreement_with_rules": round(sum(1 for u, wl in weak if u["wt"] == wl) / len(weak), 4) if weak else None,
        "manager_labels": label_sources.get("manager", 0),
        "rederived": len(rederive),
        "mean_confidence": round(float(np.mean(conf_ml)), 4) if conf_ml else 0.0,
        "confidence_histogram": _confidence_histogram(conf_ml),
        "seconds": round(time.monotonic() - started, 1),
    }
    return TrainOutput(updates, rederive, final_types, preds, metrics, label_sources, prediction_stats)


async def run_training(*, sample_other: int | None = None, matcher: MLMatcher | None = None) -> dict[str, Any]:
    """Обучает модель и проставляет предсказания всем товарам в БД. Возвращает метрики."""
    if _train_lock.locked():
        raise RuntimeError("Обучение уже идёт")
    async with _train_lock:
        ML_STATUS.clear()
        ML_STATUS.update(state="running", stage="loading", started_at=time.time())
        try:
            matcher = matcher or get_matcher()
            rows, categories = await _load_rows()
            if not rows:
                raise RuntimeError("В БД нет товаров — сначала импорт каталога")
            out = await train_and_predict(rows, categories, matcher, sample_other=sample_other)

            ML_STATUS.update(stage="saving")
            await _write_predictions(out.updates, out.rederive)
            await _update_categories(rows, out.final_types, out.preds)
            await _save_model_row(matcher, out.metrics, out.prediction_stats)
            result = {**out.metrics, **out.prediction_stats, "label_sources": out.label_sources}
            ML_STATUS.update(state="done", stage=None, result={k: v for k, v in result.items() if k != "per_class"})
            logger.info("ML-предсказания записаны: %s", {k: v for k, v in out.prediction_stats.items()
                                                       if k not in ("confidence_histogram", "accepted_by_type")})
            return result
        except Exception as exc:
            ML_STATUS.update(state="error", error=f"{exc.__class__.__name__}: {exc}")
            raise


async def _write_predictions(updates: list[dict], rederive: list[dict]) -> None:
    pred_stmt = (
        update(Product.__table__).where(Product.__table__.c.id == bindparam("pid"))
        .values(work_type=bindparam("wt"), match_confidence=bindparam("conf"), match_source=bindparam("src"),
                label_work_type=bindparam("lbl"), label_source=bindparam("lsrc"))
    )
    for start in range(0, len(updates), WRITE_CHUNK):
        async with engine.begin() as conn:
            await conn.execute(pred_stmt, updates[start:start + WRITE_CHUNK])
    if rederive:
        keys = [k[2:] for k in rederive[0] if k.startswith("d_")]
        der_stmt = (
            update(Product.__table__).where(Product.__table__.c.id == bindparam("pid"))
            .values(**{k: bindparam(f"d_{k}") for k in keys})
        )
        for start in range(0, len(rederive), WRITE_CHUNK):
            async with engine.begin() as conn:
                await conn.execute(der_stmt, rederive[start:start + WRITE_CHUNK])


async def _update_categories(rows: list[dict], final_types: list[str | None],
                             preds: list[tuple[str | None, float]]) -> None:
    """Тип работ категории — если больше половины её товаров уверенно отнесены к одному типу."""
    per_cat: dict[int, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for r, code, (_, conf) in zip(rows, final_types, preds):
        cid = r["category_id"]
        if cid is None:
            continue
        totals[cid] += 1
        if code and (conf >= CONFIDENCE_THRESHOLD or r["label_source"] == "manager"):
            per_cat[cid][code] += 1
    params = []
    for cid, total in totals.items():
        wt, n = per_cat[cid].most_common(1)[0] if per_cat[cid] else (None, 0)
        params.append({"cid": cid, "wt": wt if n * 2 > total else None})
    stmt = update(Category.__table__).where(Category.__table__.c.id == bindparam("cid")).values(work_type=bindparam("wt"))
    async with engine.begin() as conn:
        await conn.execute(stmt, params)


async def _save_model_row(matcher: MLMatcher, metrics: dict, prediction_stats: dict) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(MLModel).values(is_active=False))
        await conn.execute(pg_insert(MLModel).values(
            encoder=matcher.encoder.name, trained_at=time.time(), train_size=metrics.get("train_size", 0),
            threshold=CONFIDENCE_THRESHOLD, metrics=metrics, prediction_stats=prediction_stats, is_active=True,
        ))
        # справочник типов работ — на случай, если импорт был до появления таблицы
        stmt = pg_insert(WorkType)
        await conn.execute(stmt.on_conflict_do_nothing(index_elements=["id"]), work_type_rows())


_background: set[asyncio.Task] = set()


def start_training(after: "asyncio.Future | None" = None) -> bool:
    """Запускает обучение в фоне (после задачи after, если задана). False — если оно уже идёт."""
    if ML_STATUS.get("state") in ("running", "queued") or _train_lock.locked():
        return False

    async def job() -> None:
        try:
            if after is not None:
                await after
            await run_training()
        except Exception:  # noqa: BLE001
            logger.exception("Обучение ML-матчинга не удалось")

    ML_STATUS.update(state="queued")
    task = asyncio.create_task(job())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return True


async def needs_training() -> str | None:
    """Причина, по которой модель нужно (пере)обучить при старте, или None."""
    matcher = get_matcher()
    async with engine.connect() as conn:
        products = (await conn.execute(select(Product.id).limit(1))).first()
        if products is None:
            return None
        predicted = (await conn.execute(
            select(Product.id).where(Product.match_source.in_(["ml", "manager"])).limit(1))).first()
        active = (await conn.execute(select(MLModel.encoder).where(MLModel.is_active.is_(True)).limit(1))).first()
    if not matcher.ready:
        return "классификатор не обучен"
    if predicted is None:
        return "у товаров нет предсказаний модели"
    if active is None or active[0] != matcher.encoder.name:
        return "сменился энкодер"
    return None


__all__ = ["ML_STATUS", "WORK_TYPES", "build_training_set", "embed_all", "needs_training", "run_training",
           "start_training"]

"""Преобразование записей БД в формат каталожного API из ТЗ (без обращения к БД)."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

MARKETING_KEY = "Маркетинговое описание товара"
BOTTOM_PROPS = 6          # сколько характеристик показывать в propertiesBottom
FILTER_PROPS = 15         # сколько характеристик отдавать в properties (фильтры)
FILTER_VALUES = 30        # сколько значений у каждой


def _ref(obj: Any) -> dict | None:
    return {"id": obj.get("id"), "name": obj.get("name")} if isinstance(obj, dict) else None


def product_item(p: Any, category: Any | None = None, with_tree: bool = False) -> dict[str, Any]:
    """Товар в формате элемента items из GET /api/catalog/products."""
    chars = [c for c in (p.characteristics or []) if c.get("name") != MARKETING_KEY]
    item = {
        "id": p.id,
        "sku": p.sku,
        "cod_good": p.cod_good,
        "name": p.name,
        "marketing_description": p.marketing_description,
        "type": p.type or "simple",
        "url_key": p.url_key,
        "price": p.price,
        "result_price": p.result_price,
        "currency": p.currency,
        "quantity_in_package": p.quantity_in_package,
        "package_area": p.package_area,
        "price_per_m2": p.price_per_m2,
        "price_per_m2_unit": "₽/м2" if p.price_per_m2 is not None else None,
        "status": p.status,
        "brand": _ref(p.brand),
        "collection": _ref(p.collection),
        "country": _ref(p.country),
        "categories": {str(category.id): category.name} if category is not None else {},
        "categories_tree": None,
        "unit": p.unit,
        "propertiesBottom": [{"name": c.get("name"), "value": c.get("value")} for c in chars[:BOTTOM_PROPS]],
        "work_type": p.work_type,
        "moisture_resistant": p.moisture_resistant,
        "package_weight_kg": p.package_weight_kg,
        "package_volume_l": p.package_volume_l,
        "package_length_m": p.package_length_m,
        "match_confidence": p.match_confidence or 0,
        "match_source": p.match_source,
    }
    if with_tree:
        item["categories_tree"] = category_path(category) if category is not None else []
    return item


def product_card(p: Any, category: Any | None = None) -> dict[str, Any]:
    """Полная карточка — GET /api/catalog/products/{id}."""
    card = product_item(p, category, with_tree=True)
    card.update(
        description=p.description,
        weight=p.weight,
        characteristics=[{"code": c.get("code"), "name": c.get("name"), "value": c.get("value")}
                         for c in (p.characteristics or [])],
        pack_source=p.pack_source,
        consumption_rate=p.consumption_rate,
    )
    return card


def category_path(category: Any) -> list[dict[str, Any]]:
    """Путь от корня до категории: [{id, name, depth}]."""
    path = []
    node = category
    seen: set[int] = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        path.append({"id": node.id, "name": node.name, "depth": node.depth_level})
        node = getattr(node, "parent", None) if "parent" in getattr(node, "__dict__", {}) else None
    return list(reversed(path))


# ------------------------------------------------------------------ категории


def _cat_dict(c: Any) -> dict[str, Any]:
    return {
        "id": c.id, "parent_id": c.parent_id, "name": c.name, "url_key": c.url_key,
        "status": c.status, "depth_level": c.depth_level, "product_count": c.product_count or 0,
        "work_type": c.work_type,
    }


def children_index(categories: Iterable[Any]) -> tuple[dict[int, Any], dict[int | None, list[Any]]]:
    by_id = {c.id: c for c in categories}
    children: dict[int | None, list[Any]] = defaultdict(list)
    for c in by_id.values():
        parent = c.parent_id if c.parent_id in by_id else None
        children[parent].append(c)
    for lst in children.values():
        lst.sort(key=lambda x: x.name)
    return by_id, children


def totals_with_children(by_id: dict[int, Any], children: dict[int | None, list[Any]]) -> dict[int, int]:
    """product_count_all_children для каждой категории (итеративно, без рекурсии)."""
    total: dict[int, int] = {}
    order: list[int] = []
    stack = [c.id for c in children.get(None, [])]
    while stack:
        cid = stack.pop()
        order.append(cid)
        stack.extend(ch.id for ch in children.get(cid, []))
    for cid in reversed(order):
        total[cid] = (by_id[cid].product_count or 0) + sum(total.get(ch.id, 0) for ch in children.get(cid, []))
    return total


def descendants(category_id: int, children: dict[int | None, list[Any]]) -> list[int]:
    out, stack = [], [category_id]
    while stack:
        cid = stack.pop()
        out.append(cid)
        stack.extend(ch.id for ch in children.get(cid, []))
    return out


def build_tree(categories: Iterable[Any], root_id: int | None = None, depth: int = 20) -> list[dict[str, Any]]:
    """Дерево для GET /api/catalog/categories/tree: потомки root_id (или корни) на глубину depth."""
    by_id, children = children_index(categories)
    totals = totals_with_children(by_id, children)

    def node(c: Any, level: int) -> dict[str, Any]:
        d = _cat_dict(c)
        d["product_count_all_children"] = totals.get(c.id, d["product_count"])
        d["children"] = [node(ch, level + 1) for ch in children.get(c.id, [])] if level < depth else []
        return d

    return [node(c, 1) for c in children.get(root_id, [])]


def category_info(c: Any, totals: dict[int, int]) -> dict[str, Any]:
    d = _cat_dict(c)
    d.update(product_count_all_children=totals.get(c.id, d["product_count"]), description=c.description,
             is_hide="no" if c.status else "yes", dat_show_b=None, dat_show_e=None)
    return d


# ------------------------------------------------------------------ фильтры (properties)


def filter_properties(char_lists: Iterable[list[dict] | None]) -> list[dict[str, Any]]:
    """Характеристики выборки с вариантами значений и счётчиками — для фильтров."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for chars in char_lists:
        for c in chars or []:
            name, value = c.get("name"), c.get("value")
            if not name or name == MARKETING_KEY or value in (None, "") or len(str(value)) > 80:
                continue
            counts[name][str(value)] += 1
    ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))[:FILTER_PROPS]
    out = []
    for name, values in ranked:
        if len(values) < 2:
            continue
        out.append({
            "code": name,  # в выгрузке у характеристик нет кодов — ключом служит название
            "name": name,
            "type": "text",
            "values": [{"value": v, "label": v, "count": n, "is_available": True}
                       for v, n in values.most_common(FILTER_VALUES)],
        })
    return out

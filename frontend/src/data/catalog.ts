/** Справочники интерфейса. Товары, цены и нормы приходят с backend (см. api/client.ts). */

/** Уровень влажности: 0 — низкая, 1 — средняя, 2 — высокая. */
export type Humidity = 0 | 1 | 2;

/** Уровень ремонта: 0 — косметический, 1 — капитальный, 2 — дизайнерский. */
export type RepairLevel = 0 | 1 | 2;

/** Ценовой сегмент подбора; null — по уровню ремонта. */
export type Tier = "economy" | "balance" | "premium" | null;

export interface Room {
    id: number;
    /** Тип / название помещения */
    n: string;
    /** Площадь пола, м² */
    a: number;
    /** Высота потолка, м */
    ch: number;
    /** Площадь проёмов, м² */
    op: number;
    hum: Humidity;
    /** Ручной выбор товара: {код правила: id товара} */
    picks: Record<string, number>;
    /** Отключённые работы (коды правил) */
    disabled: string[];
}

export const HUM = ["низкая", "средняя", "высокая"] as const;

export const LVL = ["Косметический", "Капитальный", "Дизайнерский"] as const;
/** Значения repair_variant для API */
export const LVL_API = ["косметический", "капитальный", "дизайнерский"] as const;

export const TIERS: { key: Exclude<Tier, null>; label: string }[] = [
    { key: "economy", label: "Эконом" },
    { key: "balance", label: "Баланс" },
    { key: "premium", label: "Премиум" },
];
export const DEFAULT_TIER: Exclude<Tier, null>[] = ["economy", "balance", "premium"];

export const TIER_TEXT: Record<string, string> = {
    economy: "Режим «эконом»: сервис ставит первым самый доступный подходящий товар.",
    balance: "Режим «баланс»: средняя цена за м² среди подходящих товаров.",
    premium: "Режим «премиум»: товары верхнего ценового сегмента.",
};

export const ROOMT: Record<string, { h: Humidity; op: number }> = {
    "Санузел": { h: 2, op: 1.6 },
    "Кухня": { h: 1, op: 2.4 },
    "Детская": { h: 0, op: 2.4 },
    "Спальня": { h: 0, op: 2.4 },
    "Гостиная": { h: 0, op: 2.4 },
    "Коридор": { h: 0, op: 3.2 },
    "Балкон": { h: 1, op: 2.4 },
    "Кладовая": { h: 0, op: 1.6 },
};

export const ROOM_TYPES = Object.keys(ROOMT);

/** Типовые площади при разборе запроса без цифр. */
export const DEFAULT_AREA: Partial<Record<string, number>> = {
    "Санузел": 5, "Кухня": 10, "Коридор": 6, "Балкон": 4, "Кладовая": 3,
};

/** Типы работ, для которых на карточке товара доступен расчёт количества. */
export const CALC_WORK_TYPES = [
    "floor_tile", "floor_spc", "wall_tile", "wall_paint", "wallpaper", "wall_panels", "ceiling_tile",
    "underlay", "tile_adhesive", "grout", "floor_leveler", "wall_plaster", "wall_putty",
    "floor_waterproofing", "ceiling_molding", "waterproofing_tape",
];

/** Как задаются размеры в виджете карточки товара. */
export const SURFACE_OF: Record<string, "floor" | "wall" | "perimeter"> = {
    floor_tile: "floor", floor_spc: "floor", underlay: "floor", floor_leveler: "floor",
    floor_waterproofing: "floor", ceiling_tile: "floor", tile_adhesive: "floor", grout: "floor",
    wall_tile: "wall", wall_paint: "wall", wallpaper: "wall", wall_panels: "wall", wall_plaster: "wall",
    wall_putty: "wall", ceiling_molding: "perimeter", waterproofing_tape: "perimeter",
};

/** Порог уверенности ML-модели: ниже него товар не участвует в подборе и уходит на ручную проверку.
 *  Совпадает с ML_CONFIDENCE_THRESHOLD на backend (фактическое значение приходит в ответах API). */
export const CONFIDENCE_THRESHOLD = 0.8;

/** Примерный периметр и площадь стен — пока смета не пришла с сервера. */
export const per = (r: Room) => 4 * Math.sqrt(Math.max(r.a, 0.5));
export const wallA = (r: Room) => Math.max(0, per(r) * r.ch - r.op);

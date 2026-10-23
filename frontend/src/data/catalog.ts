/** Демо-данные каталога и справочники калькулятора (перенесено из макета RepairCalc v3). */

/** Уровень влажности: 0 — низкая, 1 — средняя, 2 — высокая. */
export type Humidity = 0 | 1 | 2;

/** Тип работ, к которому привязан товар. */
export type WorkKey = "floor" | "base" | "wall" | "ceil" | "hydro" | "elec" | "fix" | "aux";

/** Режим ранжирования товаров: 0 — дешевле, 1 — баланс, 2 — премиум. */
export type Tier = 0 | 1 | 2;

/** Уровень ремонта: 0 — косметический, 1 — капитальный, 2 — дизайнерский. */
export type RepairLevel = 0 | 1 | 2;

export interface Sku {
    id: number;
    /** Название */
    n: string;
    /** Тип работ */
    c: WorkKey;
    /** Единица продажи */
    u: string;
    /** Покрытие одной упаковки (м², м, шт.) */
    cover: number;
    /** Цена за упаковку, ₽ */
    p: number;
    /** Максимальная влажность, на которую рассчитан товар */
    wet: Humidity;
    /** Рейтинг просмотров 0..100 */
    views: number;
    /** Маржинальность 0..100 */
    margin: number;
    stock: number;
    /** Норма запаса на подрезку */
    waste: number;
}

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
    /** Отключённые работы */
    off: Partial<Record<string, boolean>>;
    /** Ручной выбор товара по типу работ */
    pick: Partial<Record<string, number>>;
}

export interface Work {
    k: WorkKey;
    t: string;
    q: (r: Room) => number;
    unit: string;
    /** Цена работ за единицу, ₽ */
    lab: number;
    /** Уровни ремонта, в которых работа выполняется */
    lv: RepairLevel[];
    when?: (r: Room) => boolean;
}

export const HUM = ["низкая", "средняя", "высокая"] as const;

/** Поправка расхода, обученная на реальных заказах. */
export const MLFIX = 0.015;

export const SKU: Sku[] = [
    { id: 4101, n: "Керамогранит 600×600, светлый бетон", c: "floor", u: "уп. 1,44 м²", cover: 1.44, p: 3154, wet: 2, views: 91, margin: 58, stock: 120, waste: .12 },
    { id: 4102, n: "Ламинат 33 класс, дуб натуральный", c: "floor", u: "уп. 2,40 м²", cover: 2.4, p: 2380, wet: 0, views: 96, margin: 70, stock: 240, waste: .07 },
    { id: 4103, n: "Кварцвиниловая плитка, замковая", c: "floor", u: "уп. 2,23 м²", cover: 2.23, p: 3890, wet: 2, views: 72, margin: 74, stock: 64, waste: .08 },
    { id: 4104, n: "Линолеум бытовой, 3 м", c: "floor", u: "рулон 9 м²", cover: 9, p: 4100, wet: 1, views: 60, margin: 40, stock: 18, waste: .1 },
    { id: 4201, n: "Гипсокартон влагостойкий 12,5 мм", c: "base", u: "лист 3,0 м²", cover: 3, p: 620, wet: 2, views: 76, margin: 54, stock: 310, waste: .08 },
    { id: 4202, n: "Гипсокартон стандартный 12,5 мм", c: "base", u: "лист 3,0 м²", cover: 3, p: 410, wet: 0, views: 88, margin: 49, stock: 420, waste: .08 },
    { id: 4203, n: "Штукатурка гипсовая, 30 кг", c: "base", u: "мешок 30 кг", cover: 3.3, p: 560, wet: 1, views: 81, margin: 52, stock: 150, waste: .1 },
    { id: 4301, n: "Плитка настенная 300×600, белая матовая", c: "wall", u: "уп. 1,62 м²", cover: 1.62, p: 1390, wet: 2, views: 86, margin: 56, stock: 200, waste: .1 },
    { id: 4302, n: "Обои виниловые моющиеся, 1,06 м", c: "wall", u: "рулон 5,3 м²", cover: 5.3, p: 1190, wet: 1, views: 83, margin: 63, stock: 95, waste: .15 },
    { id: 4303, n: "Краска для влажных помещений, 9 л", c: "wall", u: "банка 9 л", cover: 45, p: 3980, wet: 2, views: 69, margin: 66, stock: 40, waste: .08 },
    { id: 4304, n: "Краска интерьерная моющаяся, 9 л", c: "wall", u: "банка 9 л", cover: 45, p: 3280, wet: 1, views: 89, margin: 59, stock: 70, waste: .08 },
    { id: 4305, n: "Обои под покраску, флизелин", c: "wall", u: "рулон 5,3 м²", cover: 5.3, p: 890, wet: 0, views: 74, margin: 48, stock: 130, waste: .12 },
    { id: 4401, n: "Потолочная краска матовая, 7 л", c: "ceil", u: "банка 7 л", cover: 35, p: 2190, wet: 1, views: 78, margin: 55, stock: 88, waste: .06 },
    { id: 4402, n: "Реечный потолок влагостойкий", c: "ceil", u: "компл. 2 м²", cover: 2, p: 1650, wet: 2, views: 52, margin: 72, stock: 36, waste: .05 },
    { id: 4403, n: "Натяжной потолок, полотно", c: "ceil", u: "м²", cover: 1, p: 720, wet: 2, views: 84, margin: 61, stock: 999, waste: .05 },
    { id: 4501, n: "Гидроизоляция обмазочная, 20 кг", c: "hydro", u: "ведро 20 кг", cover: 13, p: 2450, wet: 2, views: 62, margin: 67, stock: 44, waste: .1 },
    { id: 4502, n: "Гидроизоляционная лента для швов", c: "hydro", u: "рулон 10 м", cover: 10, p: 690, wet: 2, views: 48, margin: 58, stock: 60, waste: .05 },
    { id: 4601, n: "Кабель ВВГнг-LS 3×2,5", c: "elec", u: "бухта 50 м", cover: 50, p: 3400, wet: 2, views: 80, margin: 46, stock: 52, waste: .08 },
    { id: 4602, n: "Кабель ВВГнг-LS 3×1,5", c: "elec", u: "бухта 50 м", cover: 50, p: 2300, wet: 2, views: 77, margin: 44, stock: 70, waste: .08 },
    { id: 4701, n: "Розетка влагозащищённая IP44", c: "fix", u: "шт.", cover: 1, p: 390, wet: 2, views: 71, margin: 60, stock: 180, waste: 0 },
    { id: 4702, n: "Розетка скрытой установки, белая", c: "fix", u: "шт.", cover: 1, p: 250, wet: 0, views: 87, margin: 52, stock: 300, waste: 0 },
    { id: 4801, n: "Клей плиточный усиленный, 25 кг", c: "aux", u: "мешок 25 кг", cover: 4, p: 690, wet: 2, views: 66, margin: 50, stock: 210, waste: .05 },
    { id: 4802, n: "Затирка влагостойкая, 2 кг", c: "aux", u: "упак. 2 кг", cover: 12, p: 480, wet: 2, views: 58, margin: 57, stock: 140, waste: .05 },
    { id: 4803, n: "Грунтовка глубокого проникновения, 10 л", c: "aux", u: "канистра 10 л", cover: 60, p: 1290, wet: 2, views: 79, margin: 53, stock: 120, waste: .05 },
];

export const CATN: Record<WorkKey, string> = {
    floor: "Пол",
    base: "Основание стен",
    wall: "Отделка стен",
    ceil: "Потолок",
    hydro: "Гидроизоляция",
    elec: "Электрика",
    fix: "Электроточки",
    aux: "Сопутствующее",
};

export const WORK_KEYS = Object.keys(CATN) as WorkKey[];

export const ROOMT: Record<string, { h: Humidity; base: number }> = {
    "Санузел": { h: 2, base: 1 },
    "Кухня": { h: 1, base: 1 },
    "Детская": { h: 0, base: 1 },
    "Спальня": { h: 0, base: 1 },
    "Гостиная": { h: 0, base: 1 },
    "Коридор": { h: 0, base: 1 },
    "Балкон": { h: 1, base: 1 },
    "Кладовая": { h: 0, base: 0 },
};

export const ROOM_TYPES = Object.keys(ROOMT);

/** Приблизительный периметр помещения. */
export const per = (r: Room) => 4 * Math.sqrt(Math.max(r.a, 1));
/** Площадь стен без проёмов. */
export const wallA = (r: Room) => Math.max(4, per(r) * r.ch - r.op);

export const WORKS: Work[] = [
    { k: "floor", t: "Пол: покрытие", q: r => r.a, unit: "м²", lab: 980, lv: [0, 1, 2] },
    { k: "hydro", t: "Гидроизоляция пола и примыканий", q: r => r.a + per(r) * .3, unit: "м²", lab: 620, lv: [1, 2], when: r => r.hum === 2 },
    { k: "base", t: "Выравнивание стен", q: wallA, unit: "м²", lab: 740, lv: [1, 2] },
    { k: "wall", t: "Отделка стен", q: wallA, unit: "м²", lab: 690, lv: [0, 1, 2] },
    { k: "ceil", t: "Потолок", q: r => r.a, unit: "м²", lab: 540, lv: [0, 1, 2] },
    { k: "elec", t: "Электрика: кабель", q: r => r.a * 4.2, unit: "м", lab: 160, lv: [1, 2] },
    { k: "fix", t: "Электроточки", q: r => Math.max(2, Math.ceil(r.a / 3)), unit: "шт.", lab: 950, lv: [1, 2] },
];

export const LVL = ["Косметический", "Капитальный", "Дизайнерский"] as const;
/** Коэффициент цены материалов по уровню ремонта. */
export const LK = [.72, 1, 1.55] as const;
/** Коэффициент цены работ по уровню ремонта. */
export const LLAB = [.8, 1, 1.45] as const;

export const TIER_TEXT = [
    "Режим «дешевле»: модель ставит первым самый бюджетный подходящий товар.",
    "Режим «баланс»: товары ранжированы по просмотрам и маржинальности.",
    "Режим «премиум»: первыми идут товары верхнего ценового сегмента.",
] as const;

/** Типовые параметры помещения при добавлении/разборе. */
export const DEFAULT_AREA: Partial<Record<string, number>> = {
    "Санузел": 5, "Кухня": 10, "Коридор": 6, "Балкон": 4, "Кладовая": 3,
};

export interface AdminItem {
    n: string;
    c: WorkKey;
    r: string[];
    /** Уверенность модели, % */
    v: number;
    ok: boolean;
}

export const ADMIN_SEED: AdminItem[] = (
    [
        ["Гипсокартон влагостойкий 12,5 мм", "base", ["Санузел", "Кухня"], 94],
        ["Ламинат 33 класс, дуб", "floor", ["Гостиная", "Спальня", "Детская"], 91],
        ["Плитка настенная 300×600", "wall", ["Санузел", "Кухня"], 93],
        ["Краска интерьерная моющаяся", "wall", ["Все помещения"], 87],
        ["Кварцвиниловая плитка", "floor", ["Кухня", "Коридор"], 85],
        ["Гидроизоляционная лента", "hydro", ["Санузел"], 79],
        ["Кабель ВВГнг-LS 3×2,5", "elec", ["Все помещения"], 63],
        ["Подложка под ламинат 3 мм", "floor", ["Гостиная"], 58],
        ["Профиль потолочный ПП 60×27", "ceil", ["Все помещения"], 71],
    ] as [string, WorkKey, string[], number][]
).map(([n, c, r, v]) => ({ n, c, r, v, ok: false }));

/** Порог уверенности, ниже которого карточка уходит на ручную проверку. */
export const CONFIDENCE_THRESHOLD = 85;

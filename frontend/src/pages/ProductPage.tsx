import { useEffect, useState } from "react";
import { CALC_WORK_TYPES, SURFACE_OF } from "@/data/catalog.ts";
import {
    calcProduct, getProduct, isAbort, listProducts,
    type CatalogProduct, type ProductCalc, type ProductCalcRequest, type ProductCard,
} from "@/api/client.ts";
import { useWorkTypes, workTypeName } from "@/api/useWorkTypes.ts";
import { packLabel } from "@/lib/estimate.ts";
import { d1, num, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

const lineStyle = { font: "600 14px Inter" };
const HIDE_CHARS = /Маркетинговое описание/;

type Loaded<T> = { key: string; data?: T; error?: string } | null;

function useLoad<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>, delay = 0): Loaded<T> {
    const [state, setState] = useState<Loaded<T>>(null);
    useEffect(() => {
        if (key === null) return;
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            load(ctrl.signal)
                .then(data => setState({ key, data }))
                .catch((e: unknown) => { if (!isAbort(e)) setState({ key, error: e instanceof Error ? e.message : String(e) }); });
        }, delay);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
        // eslint-disable-next-line react-hooks/exhaustive-deps -- запрос определяется ключом
    }, [key]);
    return state && state.key === key ? state : null;
}

export default function ProductPage() {
    const { update } = useProject();
    const toast = useToast();
    const types = useWorkTypes();
    const [workType, setWorkType] = useState("floor_tile");
    const [q, setQ] = useState("");
    const [pickedId, setPickedId] = useState<number | null>(null);
    const [m1, setM1] = useState("4");
    const [m2, setM2] = useState("3.2");
    const [m3, setM3] = useState("1.6");
    const [extra, setExtra] = useState("0");

    // 1. список товаров выбранного типа работ
    const listKey = JSON.stringify({ workType, q: q.trim() });
    const list = useLoad<CatalogProduct[]>(listKey, signal =>
        listProducts({ work_type: workType, q: q.trim() || undefined, per_page: 50, sort: "price_asc" }, signal).then(r => r.items), 250);
    const items = list?.data ?? [];
    const productId = pickedId !== null && items.some(p => p.id === pickedId) ? pickedId : items[0]?.id ?? null;

    // 2. полная карточка
    const card = useLoad<ProductCard>(productId === null ? null : String(productId), signal => getProduct(productId!, signal));
    const p = card?.data;

    // 3. расчёт количества на сервере
    const surface = SURFACE_OF[p?.work_type ?? workType] ?? "floor";
    const tileLike = ["floor_tile", "wall_tile", "floor_spc"].includes(p?.work_type ?? "");
    const extraWaste = tileLike ? num(extra) : 0;   // доп. запас на способ укладки — только для плитки и SPC
    const body: ProductCalcRequest = surface === "wall"
        ? { width: num(m1), height: num(m2), openings_area: num(m3), extra_waste_percent: extraWaste }
        : { length: num(m1), width: num(m2), extra_waste_percent: extraWaste };
    const sizesOk = num(m1) > 0 && num(m2) > 0;
    const calcKey = p && sizesOk ? JSON.stringify({ id: p.id, body }) : null;
    const calc = useLoad<ProductCalc>(calcKey, signal => calcProduct(p!.id, body, signal), 300);
    const c = calc?.data;

    const buy = () => {
        if (!c || !p) return;
        update(st => ({ ...st, cart: [...st.cart, { t: `${p.name} × ${c.packages_needed}`, sum: c.total_cost }] }));
        toast("Товар в корзине: " + rub(c.total_cost));
    };

    const chars = (p?.characteristics ?? []).filter(x => !HIDE_CHARS.test(x.name)).slice(0, 10);
    const labels = surface === "wall" ? ["Ширина стены, м", "Высота, м"]
        : surface === "perimeter" ? ["Длина комнаты, м", "Ширина комнаты, м"] : ["Длина помещения, м", "Ширина помещения, м"];

    return (
        <section>
            <div className="pdp">
                <div className="card">
                    <div className="gal" role="img" aria-label="Фотография товара"></div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                        <div>
                            <label className="lab" htmlFor="pt">Тип работ</label>
                            <select id="pt" value={workType} onChange={e => { setWorkType(e.target.value); setPickedId(null); }}>
                                {CALC_WORK_TYPES.map(k => <option key={k} value={k}>{workTypeName(types, k)}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="lab" htmlFor="pq">Поиск</label>
                            <input id="pq" type="search" placeholder="бренд, коллекция, размер" value={q} onChange={e => setQ(e.target.value)} />
                        </div>
                    </div>
                    <label className="lab" htmlFor="ps">Товар каталога {list?.data ? `(${items.length}${items.length === 50 ? "+" : ""})` : ""}</label>
                    <select id="ps" value={productId ?? ""} onChange={e => setPickedId(+e.target.value)} disabled={!items.length}>
                        {!items.length && <option value="">{list?.error ? "Каталог недоступен" : list ? "Ничего не найдено" : "Загружаем…"}</option>}
                        {items.map(x => <option key={x.id} value={x.id}>{x.name} — {rub(x.result_price)}</option>)}
                    </select>
                    {p && (
                        <>
                            <h2 style={{ marginTop: 14, fontSize: 20 }}>{p.name}</h2>
                            <p className="sub">
                                Код {p.cod_good}{p.sku ? ` · арт. ${p.sku}` : ""} · {packLabel(p)} · {rub(p.result_price)} за {p.unit ?? "шт."}
                            </p>
                            <dl className="specs">
                                <dt>Тип работ</dt><dd>{workTypeName(types, p.work_type)}</dd>
                                <dt>Фасовка</dt><dd>{packLabel(p)}{p.pack_source ? ` (${p.pack_source})` : ""}</dd>
                                <dt>Влагостойкость</dt><dd>{p.moisture_resistant === true ? "для влажных помещений" : p.moisture_resistant === false ? "нет" : "не указана"}</dd>
                                {p.consumption_rate && <><dt>Расход по карточке</dt><dd className="num">{String(p.consumption_rate).replace(".", ",")}</dd></>}
                                {chars.map((x, i) => <FragmentDt key={i + x.name} name={x.name} value={x.value} />)}
                            </dl>
                        </>
                    )}
                    {card?.error && <p className="sub" style={{ color: "var(--brand)", marginTop: 12 }}>{card.error}</p>}
                </div>
                <div>
                    <div className="card">
                        <h2>Сколько купить</h2>
                        <p className="sub">Виджет встраивается в карточку товара на сайте</p>
                        <label className="lab" htmlFor="m1">{labels[0]}</label>
                        <input id="m1" type="number" step={0.1} min={0.1} value={m1} onChange={e => setM1(e.target.value)} />
                        <label className="lab" htmlFor="m2">{labels[1]}</label>
                        <input id="m2" type="number" step={0.1} min={0.1} value={m2} onChange={e => setM2(e.target.value)} />
                        {surface === "wall" && (
                            <div>
                                <label className="lab" htmlFor="m3">Вычесть проёмы, м²</label>
                                <input id="m3" type="number" step={0.1} min={0} value={m3} onChange={e => setM3(e.target.value)} />
                            </div>
                        )}
                        {tileLike && (
                            <>
                                <label className="lab" htmlFor="m4">Способ укладки</label>
                                <select id="m4" value={extra} onChange={e => setExtra(e.target.value)}>
                                    <option value="0">Прямая, запас по норме</option>
                                    <option value="5">По диагонали, +5%</option>
                                    <option value="10">Сложный рисунок, +10%</option>
                                </select>
                            </>
                        )}
                        <div className="out" style={{ opacity: calc ? 1 : 0.6 }}>
                            {c ? (
                                <>
                                    <div className="outline"><span>{c.coverage_unit === "п.м." ? "Периметр" : "Площадь поверхности"}</span><b className="num" style={lineStyle}>{d1(c.area)} {c.coverage_unit}</b></div>
                                    <div className="outline"><span>Запас на подрезку и отходы</span><b className="num" style={lineStyle}>{d1(c.waste_percent)}%</b></div>
                                    <div className="outline"><span>С запасом</span><b className="num" style={lineStyle}>{d1(c.need_with_waste)} {c.coverage_unit}</b></div>
                                    <div className="outline"><span>Одна упаковка покрывает</span><b className="num" style={lineStyle}>{d1(c.coverage_per_package)} {c.coverage_unit}</b></div>
                                    <div className="outline" style={{ borderTop: "1px solid #C9E0D4", marginTop: 6, paddingTop: 8 }}>
                                        <span>Купить</span><b className="num">{c.packages_needed} × {c.pack}</b>
                                    </div>
                                    <div className="outline"><span>Стоимость</span><b className="num">{rub(c.total_cost)}</b></div>
                                </>
                            ) : (
                                <p className="sub">{calc?.error ?? (sizesOk ? "Считаем…" : "Укажите размеры")}</p>
                            )}
                        </div>
                        <button className="btn" style={{ width: "100%", marginTop: 12 }} onClick={buy} disabled={!c}>Добавить в корзину</button>
                    </div>
                    <div className="card">
                        <h2>Ответ сервиса</h2>
                        <pre>
                            <b>POST</b> /api/v1/product/{p?.id ?? "{id}"}/calc{"\n"}{JSON.stringify(body, null, 2)}{"\n\n"}
                            {JSON.stringify(c ?? (calc?.error ? { detail: calc.error } : {}), null, 2)}
                        </pre>
                    </div>
                </div>
            </div>
        </section>
    );
}

function FragmentDt({ name, value }: { name: string; value: unknown }) {
    return <><dt>{name}</dt><dd>{String(value ?? "")}</dd></>;
}

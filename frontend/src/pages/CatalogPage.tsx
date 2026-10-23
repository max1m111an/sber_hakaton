import { useEffect, useState } from "react";
import { CONFIDENCE_THRESHOLD, ROOMT, ROOM_TYPES } from "@/data/catalog.ts";
import { isAbort, listProducts, type CatalogProduct, type ProductList, type ProductListParams } from "@/api/client.ts";
import { useWorkTypes, workTypeName } from "@/api/useWorkTypes.ts";
import { packLabel } from "@/lib/estimate.ts";
import { rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

interface Filters {
    q: string;
    workType: string;
    room: string;
    wet: boolean;
    sort: NonNullable<ProductListParams["sort"]>;
    page: number;
}

const EMPTY: Filters = { q: "", workType: "", room: "", wet: false, sort: "id", page: 1 };
const PER_PAGE = 20;

export default function CatalogPage() {
    const { state, update, estimate } = useProject();
    const toast = useToast();
    const types = useWorkTypes();
    const [f, setF] = useState<Filters>(EMPTY);
    const [res, setRes] = useState<{ key: string; data?: ProductList; error?: string } | null>(null);
    const set = (p: Partial<Filters>) => setF(prev => ({ ...prev, page: 1, ...p }));

    // для влажного помещения показываем только влагостойкие товары
    const wetRoom = f.room ? ROOMT[f.room].h >= 2 : false;
    const params: ProductListParams = {
        q: f.q.trim() || undefined,
        work_type: f.workType || undefined,
        moisture_resistant: f.wet || wetRoom ? true : undefined,
        sort: f.sort,
        page: f.page,
        per_page: PER_PAGE,
    };
    const key = JSON.stringify(params);

    useEffect(() => {
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            listProducts(JSON.parse(key) as ProductListParams, ctrl.signal)
                .then(data => setRes({ key, data }))
                .catch((e: unknown) => { if (!isAbort(e)) setRes({ key, error: e instanceof Error ? e.message : String(e) }); });
        }, 250);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
    }, [key]);

    const data = res?.data;
    const loading = res?.key !== key;
    const room = state.rooms[state.sel];
    const roomLines = estimate.data?.rooms.length === state.rooms.length ? estimate.data.rooms[state.sel]?.items ?? [] : [];
    const lineFor = (p: CatalogProduct) => roomLines.find(l => p.work_type && l.recommended_materials.includes(p.work_type));

    const use = (p: CatalogProduct) => {
        const line = lineFor(p);
        if (!line) {
            toast(`В смете помещения «${room.n}» нет работы для этого товара`);
            return;
        }
        update(s => ({
            ...s,
            rooms: s.rooms.map((r, i) => i === s.sel
                ? { ...r, picks: { ...r.picks, [line.rule_code]: p.id }, disabled: r.disabled.filter(c => c !== line.rule_code) }
                : r),
        }));
        toast(`«${line.title}» в помещении «${room.n}»: ${p.name}`);
    };

    return (
        <section>
            <div className="card">
                <h2>Каталог с подбором под помещение</h2>
                <p className="sub">
                    Товары maxidom.ru из выгрузки. Тип работ определяет ML-модель по названию, описанию и характеристикам;
                    в смету идут товары с уверенностью от {Math.round(CONFIDENCE_THRESHOLD * 100)}%. «В смету» подставляет товар в помещение «{room.n}».
                </p>
                <div className="filters" style={{ marginTop: 14 }}>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cq">Поиск по каталогу</label>
                        <input id="cq" type="search" placeholder="керамогранит, затирка, обои…" value={f.q} onChange={e => set({ q: e.target.value })} />
                    </div>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cc">Тип работ</label>
                        <select id="cc" value={f.workType} onChange={e => set({ workType: e.target.value })}>
                            <option value="">Все товары</option>
                            {types.filter(t => t.predicted > 0).map(t => <option key={t.code} value={t.code}>{t.name} ({t.predicted})</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cr">Помещение</label>
                        <select id="cr" value={f.room} onChange={e => set({ room: e.target.value })}>
                            <option value="">Любое помещение</option>
                            {ROOM_TYPES.map(k => <option key={k} value={k}>{k}</option>)}
                        </select>
                    </div>
                    <button className="btn g" onClick={() => setF(EMPTY)}>Сбросить</button>
                </div>
                <div className="chips">
                    <button aria-pressed={f.wet} onClick={() => set({ wet: !f.wet })}>Только влагостойкие</button>
                    {([["id", "По умолчанию"], ["price_asc", "Сначала дешевле"], ["price_desc", "Сначала дороже"]] as const).map(([k, l]) => (
                        <button key={k} aria-pressed={f.sort === k} onClick={() => set({ sort: k })}>{l}</button>
                    ))}
                </div>
            </div>
            <div className="card">
                {res?.error && !loading ? (
                    <p className="sub" style={{ color: "var(--brand)" }}>Каталог недоступен: {res.error}</p>
                ) : (
                    <table className="t-cat" style={{ opacity: loading ? 0.6 : 1 }}>
                        <thead>
                            <tr>
                                <th style={{ width: "40%" }}>Товар</th><th>Тип работ</th><th className="r">Цена</th>
                                <th className="r">Фасовка</th><th>Уверенность модели</th><th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {data?.items.length ? data.items.map(p => {
                                const v = Math.round((p.match_confidence || 0) * 100);
                                const canUse = Boolean(lineFor(p));
                                return (
                                    <tr key={p.id}>
                                        <td>
                                            <div className="prod">
                                                <span className="thumb"></span>
                                                <div>
                                                    <b style={{ fontWeight: 600 }}>{p.name}</b>
                                                    <small>Код {p.cod_good}{p.brand?.name ? ` · ${p.brand.name}` : ""} · {Object.values(p.categories)[0] ?? ""}</small>
                                                </div>
                                            </div>
                                        </td>
                                        <td>{p.work_type ? workTypeName(types, p.work_type) : <span className="sub">не размечен</span>}
                                            {p.moisture_resistant && <> <span className="tag wet">влага</span></>}</td>
                                        <td className="r num">{rub(p.result_price)}</td>
                                        <td className="r num">{packLabel(p)}</td>
                                        <td>
                                            {p.work_type ? (
                                                <div className="score">
                                                    <div className="bar"><i className={v < CONFIDENCE_THRESHOLD * 100 ? "m" : ""} style={{ width: v + "%" }}></i></div>
                                                    <span className="num">{v}%</span>
                                                </div>
                                            ) : "—"}
                                        </td>
                                        <td className="r">
                                            <button className="btn g sm" disabled={!canUse} onClick={() => use(p)}
                                                title={canUse ? "" : `В смете «${room.n}» нет работы для этого товара`}>В смету</button>
                                        </td>
                                    </tr>
                                );
                            }) : (
                                <tr><td colSpan={6} className="sub" style={{ padding: "18px 0" }}>
                                    {loading ? "Загружаем…" : "Ничего не нашлось. Снимите часть фильтров."}
                                </td></tr>
                            )}
                        </tbody>
                    </table>
                )}
                {data && (
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
                        <p className="sub" style={{ flex: 1 }}>
                            {data.meta.total.toLocaleString("ru-RU")} товаров · страница {data.meta.current_page} из {data.meta.last_page}
                        </p>
                        <button className="btn g sm" disabled={f.page <= 1} onClick={() => setF(p => ({ ...p, page: p.page - 1 }))}>Назад</button>
                        <button className="btn g sm" disabled={f.page >= data.meta.last_page} onClick={() => setF(p => ({ ...p, page: p.page + 1 }))}>Вперёд</button>
                    </div>
                )}
            </div>
        </section>
    );
}

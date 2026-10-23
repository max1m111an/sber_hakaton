import { useState } from "react";
import { CATN, ROOMT, ROOM_TYPES, SKU, WORK_KEYS, type Sku } from "@/data/catalog.ts";
import { relevance } from "@/lib/estimate.ts";
import { rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

interface Filters {
    q: string;
    c: string;
    r: string;
    wet: boolean;
    stock: boolean;
}

const EMPTY: Filters = { q: "", c: "", r: "", wet: false, stock: false };

export default function CatalogPage() {
    const { state, update } = useProject();
    const toast = useToast();
    const [f, setF] = useState<Filters>(EMPTY);
    const set = (p: Partial<Filters>) => setF(prev => ({ ...prev, ...p }));

    let list = SKU.filter(s => (!f.c || s.c === f.c) && (!f.wet || s.wet === 2) && (!f.stock || s.stock >= 50));
    if (f.q) {
        const q = f.q.toLowerCase();
        list = list.filter(s => (s.n + " " + CATN[s.c]).toLowerCase().includes(q));
    }
    if (f.r) {
        const h = ROOMT[f.r].h;
        list = list.filter(s => s.wet >= h);
    }
    const rows = list.map(s => ({ s, v: relevance(s, f.q, f.r) })).sort((a, b) => b.v - a.v);

    const use = (s: Sku) => {
        const r = state.rooms[state.sel];
        if (s.c === "aux") { toast("Сопутствующее добавляется автоматически"); return; }
        if (s.wet < r.hum) { toast(`${s.n} не подходит для помещения «${r.n}»`); return; }
        update(st => ({
            ...st,
            rooms: st.rooms.map((x, i) => i === st.sel
                ? { ...x, pick: { ...x.pick, [s.c]: s.id }, off: { ...x.off, [s.c]: false } }
                : x),
        }));
        toast(`В смету помещения «${r.n}»: ${s.n}`);
    };

    return (
        <section>
            <div className="card">
                <h2>Каталог с подбором под помещение</h2>
                <p className="sub">Модель сопоставляет товары с типами работ и помещениями, поэтому фильтр понимает «для санузла» без ручной разметки.</p>
                <div className="filters" style={{ marginTop: 14 }}>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cq">Поиск по каталогу</label>
                        <input id="cq" type="search" placeholder="плитка, гипсокартон, кабель…" value={f.q} onChange={e => set({ q: e.target.value })} />
                    </div>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cc">Тип работ</label>
                        <select id="cc" value={f.c} onChange={e => set({ c: e.target.value })}>
                            <option value="">Все работы</option>
                            {WORK_KEYS.map(k => <option key={k} value={k}>{CATN[k]}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="lab" style={{ marginTop: 0 }} htmlFor="cr">Помещение</label>
                        <select id="cr" value={f.r} onChange={e => set({ r: e.target.value })}>
                            <option value="">Любое помещение</option>
                            {ROOM_TYPES.map(k => <option key={k} value={k}>{k}</option>)}
                        </select>
                    </div>
                    <button className="btn g" onClick={() => setF(EMPTY)}>Сбросить</button>
                </div>
                <div className="chips">
                    <button aria-pressed={f.wet} onClick={() => set({ wet: !f.wet })}>Только влагостойкие</button>
                    <button aria-pressed={f.stock} onClick={() => set({ stock: !f.stock })}>В наличии от 50</button>
                </div>
            </div>
            <div className="card">
                <table className="t-cat">
                    <thead>
                        <tr>
                            <th style={{ width: "40%" }}>Товар</th><th>Тип работ</th><th className="r">Цена</th>
                            <th className="r">Остаток</th><th>Соответствие</th><th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length ? rows.map(({ s, v }) => (
                            <tr key={s.id}>
                                <td>
                                    <div className="prod">
                                        <span className="thumb"></span>
                                        <div><b style={{ fontWeight: 600 }}>{s.n}</b><small>Артикул {s.id} · {s.u}</small></div>
                                    </div>
                                </td>
                                <td>{CATN[s.c]}{s.wet === 2 && <> <span className="tag wet">влага</span></>}</td>
                                <td className="r num">{rub(s.p)}</td>
                                <td className="r num">{s.stock >= 50 ? s.stock : <span className="tag w">{s.stock}</span>}</td>
                                <td>
                                    <div className="score">
                                        <div className="bar"><i className={v < 60 ? "m" : ""} style={{ width: v + "%" }}></i></div>
                                        <span className="num">{v}%</span>
                                    </div>
                                </td>
                                <td className="r"><button className="btn g sm" onClick={() => use(s)}>В смету</button></td>
                            </tr>
                        )) : (
                            <tr><td colSpan={6} className="sub" style={{ padding: "18px 0" }}>Ничего не нашлось. Снимите часть фильтров.</td></tr>
                        )}
                    </tbody>
                </table>
                <p className="sub" style={{ marginTop: 12 }}>
                    {rows.length} товаров · соответствие считает модель по названию, атрибутам и условиям помещения
                </p>
            </div>
        </section>
    );
}

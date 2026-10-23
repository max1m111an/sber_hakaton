import { useEffect, useState } from "react";
import { MLFIX, SKU } from "@/data/catalog.ts";
import { calcProduct, type ProductCalcResponse } from "@/api/client.ts";
import { d1, num, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

const PDP = SKU.filter(s => ["floor", "wall", "ceil"].includes(s.c));

interface Remote {
    key: string;
    data?: ProductCalcResponse;
    error?: string;
}

const lineStyle = { font: "600 14px Inter" };

export default function ProductPage() {
    const { update } = useProject();
    const toast = useToast();
    const [idx, setIdx] = useState(0);
    const [m1, setM1] = useState("4");
    const [m2, setM2] = useState("3.2");
    const [m3, setM3] = useState("1.6");
    const [m4, setM4] = useState("0");
    const [remote, setRemote] = useState<Remote | null>(null);

    const s = PDP[idx];
    const surf = s.c === "floor" ? "пол" : s.c === "ceil" ? "потолок" : "стена";
    const floor = s.c !== "wall";
    const a = Math.max(0, num(m1) * num(m2) - (floor ? 0 : num(m3)));
    const w = s.waste + MLFIX + num(m4);
    const need = a * (1 + w);
    const packs = Math.max(1, Math.ceil(need / s.cover - 1e-9));
    const sum = packs * s.p;
    const short = packs > s.stock;
    const area = +a.toFixed(2);
    const key = `${s.id}:${area}`;

    // Запрос к backend: POST /api/v1/product/{id}/calc (с задержкой, чтобы не спамить при вводе)
    useEffect(() => {
        if (area <= 0) return;
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            calcProduct(s.id, area, ctrl.signal)
                .then(data => setRemote({ key, data }))
                .catch((e: unknown) => {
                    if (!ctrl.signal.aborted) setRemote({ key, error: e instanceof Error ? e.message : String(e) });
                });
        }, 300);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
    }, [s.id, area, key]);

    const r = remote?.key === key ? remote : null;
    const local = {
        product_id: s.id, surface: surf, area_m2: area, waste_pct: +(w * 100).toFixed(1), packs,
        pack_coverage_m2: s.cover, unit_price: s.p, total: sum, in_stock: s.stock >= packs,
    };

    const buy = () => {
        update(st => ({ ...st, cart: [...st.cart, { t: s.n, sum }] }));
        toast("Товар в корзине: " + rub(sum));
    };

    return (
        <section>
            <div className="pdp">
                <div className="card">
                    <div className="gal" role="img" aria-label="Фотография товара"></div>
                    <label className="lab" htmlFor="ps">Товар каталога</label>
                    <select id="ps" value={idx} onChange={e => setIdx(+e.target.value)}>
                        {PDP.map((p, i) => <option key={p.id} value={i}>{p.n}</option>)}
                    </select>
                    <h2 style={{ marginTop: 14, fontSize: 20 }}>{s.n}</h2>
                    <p className="sub">Артикул {s.id} · {s.u} · {rub(s.p)} · в наличии {s.stock}</p>
                    <dl className="specs">
                        <dt>Поверхность</dt><dd>{surf}</dd>
                        <dt>Покрытие упаковки</dt>
                        <dd className="num">{s.cover.toFixed(2).replace(".", ",")} {s.c === "ceil" && s.cover > 20 ? "м² в два слоя" : "м²"}</dd>
                        <dt>Влагостойкость</dt><dd>{["нет", "для сухих и умеренных", "для влажных помещений"][s.wet]}</dd>
                        <dt>Норма запаса</dt><dd className="num">{Math.round(s.waste * 100)}% + 1,5% поправка</dd>
                        <dt>Рейтинг просмотров</dt><dd className="num">{s.views} из 100</dd>
                    </dl>
                </div>
                <div>
                    <div className="card">
                        <h2>Сколько купить</h2>
                        <p className="sub">Виджет встраивается в карточку товара на сайте</p>
                        <label className="lab" htmlFor="m1">{floor ? "Длина помещения, м" : "Ширина стены, м"}</label>
                        <input id="m1" type="number" step={0.1} min={0.1} value={m1} onChange={e => setM1(e.target.value)} />
                        <label className="lab" htmlFor="m2">{floor ? "Ширина помещения, м" : "Высота, м"}</label>
                        <input id="m2" type="number" step={0.1} min={0.1} value={m2} onChange={e => setM2(e.target.value)} />
                        {!floor && (
                            <div>
                                <label className="lab" htmlFor="m3">Вычесть проёмы, м²</label>
                                <input id="m3" type="number" step={0.1} min={0} value={m3} onChange={e => setM3(e.target.value)} />
                            </div>
                        )}
                        <label className="lab" htmlFor="m4">Способ укладки</label>
                        <select id="m4" value={m4} onChange={e => setM4(e.target.value)}>
                            <option value="0">Прямая, запас по норме</option>
                            <option value="0.05">По диагонали, +5%</option>
                            <option value="0.1">Сложный рисунок, +10%</option>
                        </select>
                        <div className="out">
                            <div className="outline"><span>Площадь поверхности</span><b className="num" style={lineStyle}>{d1(a)} м²</b></div>
                            <div className="outline"><span>Запас на подрезку и отходы</span><b className="num" style={lineStyle}>{Math.round(w * 100)}%</b></div>
                            <div className="outline"><span>С запасом</span><b className="num" style={lineStyle}>{d1(need)} м²</b></div>
                            <div className="outline" style={{ borderTop: "1px solid #C9E0D4", marginTop: 6, paddingTop: 8 }}>
                                <span>Купить</span><b className="num">{packs} {s.u.split(" ")[0]}</b>
                            </div>
                            <div className="outline"><span>Стоимость</span><b className="num">{rub(sum)}</b></div>
                            {short && <p className="sub" style={{ marginTop: 8, color: "var(--brand)" }}>На складе {s.stock}, часть позиций под заказ</p>}
                        </div>
                        <button className="btn" style={{ width: "100%", marginTop: 12 }} onClick={buy}>Добавить в корзину</button>
                    </div>
                    <div className="card">
                        <h2>Ответ сервиса</h2>
                        <p className="sub">
                            {r?.data ? "Ответ backend (FastAPI)"
                                : r?.error ? `Backend: ${r.error} — показан локальный расчёт виджета`
                                    : "Ожидаем ответ backend… ниже локальный расчёт виджета"}
                        </p>
                        <pre>
                            <b>POST</b> /api/v1/product/{s.id}/calc{"\n"}{JSON.stringify({ area }, null, 2)}{"\n\n"}
                            {JSON.stringify(r?.data ?? local, null, 2)}
                        </pre>
                    </div>
                </div>
            </div>
        </section>
    );
}

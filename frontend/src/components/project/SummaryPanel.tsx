import { DEFAULT_TIER, LVL, TIERS } from "@/data/catalog.ts";
import { deliveryCost } from "@/lib/estimate.ts";
import { num, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

export default function SummaryPanel() {
    const { state, update, estimate } = useProject();
    const toast = useToast();
    const data = estimate.data;
    const m = data?.materials_cost ?? 0;
    const w = data?.labor_cost ?? 0;
    const d = deliveryCost(m);
    const all = m + w + d;
    const b = state.budget;
    const pct = b ? Math.min(100, all / b * 100) : 0;
    const cartSum = state.cart.reduce((a, c) => a + c.sum, 0);
    const tier = state.tier ?? DEFAULT_TIER[state.lvl];
    const sameShape = data?.rooms.length === state.rooms.length;

    const fit = () => {
        if (!b) { toast("Укажите бюджет"); return; }
        update(s => ({ ...s, tier: "economy", rooms: s.rooms.map(r => ({ ...r, picks: {} })) }));
        toast("Режим «эконом»: пересчитываем смету на самые доступные товары");
    };

    return (
        <>
            <div className="card">
                <h2>Смета проекта</h2>
                <p className="sub">{state.rooms.length} помещ. · {LVL[state.lvl].toLowerCase()} ремонт</p>
                <div className="seg" style={{ marginTop: 12 }} role="group" aria-label="Ценовой сегмент">
                    {TIERS.map(t => (
                        <button key={t.key} aria-pressed={tier === t.key}
                            onClick={() => update(s => ({ ...s, tier: t.key }))}>{t.label}</button>
                    ))}
                </div>
                <div style={{ marginTop: 12, opacity: estimate.loading ? 0.6 : 1 }}>
                    <div className="sumrow"><span>Материалы</span><b className="num">{data ? rub(m) : "—"}</b></div>
                    <div className="sumrow"><span>Работы (оценка)</span><b className="num">{data ? rub(w) : "—"}</b></div>
                    <div className="sumrow"><span>Доставка и подъём</span><b className="num">{data ? rub(d) : "—"}</b></div>
                    <div className="sumtot"><span>Итого</span><b className="num">{data ? rub(all) : "—"}</b></div>
                </div>
                <label className="lab" htmlFor="bud">Бюджет, ₽</label>
                <div className="bud">
                    <input id="bud" type="number" step={10000} value={b || ""}
                        onChange={e => update(s => ({ ...s, budget: num(e.target.value) }))} />
                    <button className="btn g" onClick={fit}>Подогнать</button>
                </div>
                <div className="meter"><i className={all > b ? "over" : ""} style={{ width: pct + "%" }}></i></div>
                <p className="sub" style={{ marginTop: 6 }}>
                    {!data ? "Смета ещё не посчитана"
                        : b ? (all <= b ? `Укладываемся, остаётся ${rub(b - all)}` : `Превышение на ${rub(all - b)} — нажмите «Подогнать»`)
                            : "Укажите бюджет, чтобы видеть остаток"}
                </p>
                <div className="byroom">
                    {sameShape && data!.rooms.map((r, i) => (
                        <div key={state.rooms[i].id}><span>{r.room_type}</span><b className="num">{rub(r.total_cost)}</b></div>
                    ))}
                </div>
            </div>
            <div className="card">
                <h2>Корзина</h2>
                <p className="sub">{state.cart.length ? `${state.cart.length} поз. на ${rub(cartSum)}` : "Пока пусто"}</p>
                <div className="byroom">
                    {state.cart.map((c, i) => <div key={i}><span>{c.t}</span><b className="num">{rub(c.sum)}</b></div>)}
                </div>
            </div>
        </>
    );
}

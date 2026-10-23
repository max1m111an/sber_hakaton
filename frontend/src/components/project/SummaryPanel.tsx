import { LVL } from "@/data/catalog.ts";
import { sumRoom, totals } from "@/lib/estimate.ts";
import { num, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

export default function SummaryPanel() {
    const { state, update } = useProject();
    const toast = useToast();
    const t = totals(state.rooms, state.lvl, state.tier);
    const b = state.budget;
    const pct = b ? Math.min(100, t.all / b * 100) : 0;
    const cartSum = state.cart.reduce((a, c) => a + c.sum, 0);

    const fit = () => {
        if (!b) { toast("Укажите бюджет"); return; }
        const before = t.all;
        const rooms = state.rooms.map(r => ({ ...r, pick: {} }));
        const after = totals(rooms, state.lvl, 0).all;
        update(s => ({ ...s, tier: 0, rooms }));
        toast(after <= b ? `Уложились: ${rub(after)} вместо ${rub(before)}` : `Минимум по каталогу — ${rub(after)}, бюджета не хватает`);
    };

    return (
        <>
            <div className="card">
                <h2>Смета проекта</h2>
                <p className="sub">{state.rooms.length} помещ. · {LVL[state.lvl].toLowerCase()} ремонт</p>
                <div style={{ marginTop: 12 }}>
                    <div className="sumrow"><span>Материалы</span><b className="num">{rub(t.m)}</b></div>
                    <div className="sumrow"><span>Работы</span><b className="num">{rub(t.w)}</b></div>
                    <div className="sumrow"><span>Доставка и подъём</span><b className="num">{rub(t.d)}</b></div>
                    <div className="sumtot"><span>Итого</span><b className="num">{rub(t.all)}</b></div>
                </div>
                <label className="lab" htmlFor="bud">Бюджет, ₽</label>
                <div className="bud">
                    <input id="bud" type="number" step={10000} value={b || ""}
                        onChange={e => update(s => ({ ...s, budget: num(e.target.value) }))} />
                    <button className="btn g" onClick={fit}>Подогнать</button>
                </div>
                <div className="meter"><i className={t.all > b ? "over" : ""} style={{ width: pct + "%" }}></i></div>
                <p className="sub" style={{ marginTop: 6 }}>
                    {b ? (t.all <= b ? `Укладываемся, остаётся ${rub(b - t.all)}` : `Превышение на ${rub(t.all - b)} — нажмите «Подогнать»`)
                        : "Укажите бюджет, чтобы видеть остаток"}
                </p>
                <div className="byroom">
                    {state.rooms.map(r => {
                        const s = sumRoom(r, state.lvl, state.tier);
                        return <div key={r.id}><span>{r.n}</span><b className="num">{rub(s.m + s.w)}</b></div>;
                    })}
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

import { useState } from "react";
import { CATN, CONFIDENCE_THRESHOLD, WORK_KEYS, type WorkKey } from "@/data/catalog.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

export default function AdminPage() {
    const { state, update } = useProject();
    const toast = useToast();
    const [q, setQ] = useState("");
    const [only, setOnly] = useState(false);

    const rows = state.admin
        .map((a, i) => ({ a, i }))
        .filter(({ a }) => a.n.toLowerCase().includes(q.toLowerCase()) && (!only || a.v < CONFIDENCE_THRESHOLD));

    const confirm = (i: number) => update(s => ({
        ...s,
        admin: s.admin.map((a, j) => (j === i ? { ...a, ok: true } : a)),
        log: [{ t: s.admin[i].n, v: s.admin[i].v }, ...s.log],
    }));

    const recategorize = (i: number, c: WorkKey) => update(s => ({
        ...s,
        admin: s.admin.map((a, j) => (j === i ? { ...a, c } : a)),
        log: [{ t: `${s.admin[i].n}: категория изменена на «${CATN[c]}»`, v: 0 }, ...s.log],
    }));

    const bulk = () => {
        const todo = state.admin.filter(a => a.v >= CONFIDENCE_THRESHOLD && !a.ok);
        update(s => ({
            ...s,
            admin: s.admin.map(a => (a.v >= CONFIDENCE_THRESHOLD ? { ...a, ok: true } : a)),
            log: [...todo.map(a => ({ t: a.n, v: a.v })).reverse(), ...s.log],
        }));
        toast(todo.length ? `Подтверждено товаров: ${todo.length}` : "Все товары с уверенностью от 85% уже подтверждены");
    };

    return (
        <section>
            <div className="card">
                <div className="rhead">
                    <div>
                        <h2>Разметка новых товаров</h2>
                        <p className="sub">Модель предлагает тип работ и помещения, менеджер подтверждает. Ниже порога уверенности карточка уходит на ручную проверку.</p>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <label className="sw">
                            <input type="checkbox" checked={only} onChange={e => setOnly(e.target.checked)} /><i></i>
                            <span style={{ fontSize: 13.5 }}>Только требующие проверки</span>
                        </label>
                        <button className="btn" onClick={bulk}>Подтвердить от {CONFIDENCE_THRESHOLD}%</button>
                    </div>
                </div>
                <label className="lab" htmlFor="aq">Поиск по названию</label>
                <input id="aq" type="search" style={{ maxWidth: 360 }} value={q} onChange={e => setQ(e.target.value)} />
            </div>
            <div className="card">
                <table>
                    <thead>
                        <tr><th style={{ width: "34%" }}>Товар</th><th>Тип работ</th><th>Помещения</th><th>Уверенность</th><th className="r">Действие</th></tr>
                    </thead>
                    <tbody>
                        {rows.length ? rows.map(({ a, i }) => {
                            const low = a.v < CONFIDENCE_THRESHOLD;
                            return (
                                <tr key={a.n}>
                                    <td><b style={{ fontWeight: 600 }}>{a.n}</b><small>Новый товар из выгрузки каталога</small></td>
                                    <td>
                                        <select aria-label="Тип работ" value={a.c} onChange={e => recategorize(i, e.target.value as WorkKey)}>
                                            {WORK_KEYS.map(k => <option key={k} value={k}>{CATN[k]}</option>)}
                                        </select>
                                    </td>
                                    <td>{a.r.map(x => <span key={x} className="tag" style={{ marginRight: 4 }}>{x}</span>)}</td>
                                    <td>
                                        <div className="score">
                                            <div className="bar"><i className={low ? "m" : ""} style={{ width: a.v + "%" }}></i></div>
                                            <span className="num">{a.v}%</span>
                                        </div>
                                    </td>
                                    <td className="r">
                                        {a.ok ? <span className="tag ok">подтверждено</span>
                                            : <button className={"btn sm" + (low ? "" : " g")} onClick={() => confirm(i)}>{low ? "Проверить" : "Подтвердить"}</button>}
                                    </td>
                                </tr>
                            );
                        }) : (
                            <tr><td colSpan={5} className="sub" style={{ padding: "18px 0" }}>Ничего не найдено</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
            <div className="card">
                <h2>Журнал решений</h2>
                <p className="sub">Подтверждения менеджера идут в обучающую выборку: следующая версия модели берёт их как разметку.</p>
                <div className="byroom" style={{ marginTop: 8 }}>
                    {state.log.length ? state.log.slice(0, 8).map((l, i) => (
                        <div key={i}><span>{l.t}</span><b className="num">{l.v ? l.v + "%" : "правка"}</b></div>
                    )) : <div className="sub">Пока пусто: подтвердите товар или поменяйте категорию</div>}
                </div>
            </div>
        </section>
    );
}

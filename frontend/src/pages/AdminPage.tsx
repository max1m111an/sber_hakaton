import { useEffect, useState } from "react";
import { CONFIDENCE_THRESHOLD } from "@/data/catalog.ts";
import { confirmMatches, isAbort, matchedProducts, updateMatch, type MatchedList, type MatchedProduct } from "@/api/client.ts";
import { useWorkTypes } from "@/api/useWorkTypes.ts";
import { rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

const PER_PAGE = 20;

export default function AdminPage() {
    const { state, update } = useProject();
    const toast = useToast();
    const types = useWorkTypes();
    const [q, setQ] = useState("");
    const [workType, setWorkType] = useState("");
    const [only, setOnly] = useState(false);
    const [page, setPage] = useState(1);
    const [version, setVersion] = useState(0);   // перезагрузка списка после изменений
    const [res, setRes] = useState<{ key: string; data?: MatchedList; error?: string } | null>(null);

    const params = {
        q: q.trim() || undefined,
        work_type: workType || undefined,
        // «требующие проверки» — уверенность ниже порога (разметка по названию товара)
        max_confidence: only ? CONFIDENCE_THRESHOLD - 0.01 : undefined,
        page,
        per_page: PER_PAGE,
    };
    const key = JSON.stringify(params);
    const fetchKey = key + "#" + version;

    useEffect(() => {
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            matchedProducts(JSON.parse(key), ctrl.signal)
                .then(data => setRes({ key: fetchKey, data }))
                .catch((e: unknown) => { if (!isAbort(e)) setRes({ key: fetchKey, error: e instanceof Error ? e.message : String(e) }); });
        }, 250);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
    }, [key, fetchKey]);

    const data = res?.data;
    const loading = res?.key !== fetchKey;
    const log = (t: string, v: number) => update(s => ({ ...s, log: [{ t, v }, ...s.log] }));
    const fail = (e: unknown) => toast("Не удалось сохранить: " + (e instanceof Error ? e.message : String(e)));

    const confirm = (p: MatchedProduct) => updateMatch(p.id)
        .then(() => { log(p.name, Math.round(p.confidence * 100)); setVersion(v => v + 1); })
        .catch(fail);

    const recategorize = (p: MatchedProduct, wt: string) => updateMatch(p.id, wt)
        .then(saved => {
            log(`${p.name}: тип работ изменён на «${saved.work_type_name ?? wt}»`, 0);
            setVersion(v => v + 1);
        })
        .catch(fail);

    // подтверждает все товары с уверенностью от порога под текущими фильтрами, не только видимую страницу
    const bulk = () => {
        confirmMatches({ min_confidence: CONFIDENCE_THRESHOLD, work_type: workType || undefined, q: q.trim() || undefined })
            .then(r => {
                if (r.confirmed) log(`Массовое подтверждение: ${r.confirmed.toLocaleString("ru-RU")} товаров`, 95);
                setVersion(v => v + 1);
                toast(r.confirmed ? `Подтверждено товаров: ${r.confirmed.toLocaleString("ru-RU")}`
                    : "Все товары с уверенностью от 85% уже подтверждены");
            })
            .catch(fail);
    };

    return (
        <section>
            <div className="card">
                <div className="rhead">
                    <div>
                        <h2>Разметка товаров каталога</h2>
                        <p className="sub">
                            Сервис предлагает тип работ и помещения, менеджер подтверждает. Разметка по названию товара
                            (уверенность ниже 85%) уходит на ручную проверку. Подтверждения сохраняются в базе.
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <label className="sw">
                            <input type="checkbox" checked={only} onChange={e => { setOnly(e.target.checked); setPage(1); }} /><i></i>
                            <span style={{ fontSize: 13.5 }}>Только требующие проверки</span>
                        </label>
                        <button className="btn" onClick={bulk}>Подтвердить от 85%</button>
                    </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "minmax(0,360px) minmax(0,260px)", gap: 10 }}>
                    <div>
                        <label className="lab" htmlFor="aq">Поиск по названию</label>
                        <input id="aq" type="search" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} />
                    </div>
                    <div>
                        <label className="lab" htmlFor="aw">Тип работ</label>
                        <select id="aw" value={workType} onChange={e => { setWorkType(e.target.value); setPage(1); }}>
                            <option value="">Все размеченные</option>
                            {types.filter(t => t.products > 0).map(t => <option key={t.code} value={t.code}>{t.name}</option>)}
                        </select>
                    </div>
                </div>
            </div>
            <div className="card">
                {res?.error && !loading ? <p className="sub" style={{ color: "var(--brand)" }}>Сервис недоступен: {res.error}</p> : (
                    <table style={{ opacity: loading ? 0.6 : 1 }}>
                        <thead>
                            <tr><th style={{ width: "34%" }}>Товар</th><th>Тип работ</th><th>Помещения</th><th>Уверенность</th><th className="r">Действие</th></tr>
                        </thead>
                        <tbody>
                            {data?.items.length ? data.items.map(p => {
                                const v = Math.round(p.confidence * 100);
                                const low = p.confidence < CONFIDENCE_THRESHOLD;
                                const done = p.source === "manager";
                                return (
                                    <tr key={p.id}>
                                        <td>
                                            <b style={{ fontWeight: 600 }}>{p.name}</b>
                                            <small>{rub(p.price)} · {p.source === "category" ? "по категории" : p.source === "name" ? "по названию" : done ? "менеджер" : ""}</small>
                                        </td>
                                        <td>
                                            <select aria-label="Тип работ" value={p.work_type ?? ""} onChange={e => recategorize(p, e.target.value)}>
                                                {!p.work_type && <option value="">—</option>}
                                                {types.map(t => <option key={t.code} value={t.code}>{t.name}</option>)}
                                            </select>
                                        </td>
                                        <td>{p.suitable_rooms.length ? p.suitable_rooms.map(x => <span key={x} className="tag" style={{ marginRight: 4 }}>{x}</span>) : <span className="sub">—</span>}</td>
                                        <td>
                                            <div className="score">
                                                <div className="bar"><i className={low ? "m" : ""} style={{ width: v + "%" }}></i></div>
                                                <span className="num">{v}%</span>
                                            </div>
                                        </td>
                                        <td className="r">
                                            {done ? <span className="tag ok">подтверждено</span>
                                                : <button className={"btn sm" + (low ? "" : " g")} onClick={() => confirm(p)}>{low ? "Проверить" : "Подтвердить"}</button>}
                                        </td>
                                    </tr>
                                );
                            }) : (
                                <tr><td colSpan={5} className="sub" style={{ padding: "18px 0" }}>{loading ? "Загружаем…" : "Ничего не найдено"}</td></tr>
                            )}
                        </tbody>
                    </table>
                )}
                {data && (
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
                        <p className="sub" style={{ flex: 1 }}>{data.total.toLocaleString("ru-RU")} товаров · страница {data.page} из {Math.max(1, Math.ceil(data.total / PER_PAGE))}</p>
                        <button className="btn g sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Назад</button>
                        <button className="btn g sm" disabled={page * PER_PAGE >= data.total} onClick={() => setPage(p => p + 1)}>Вперёд</button>
                    </div>
                )}
            </div>
            <div className="card">
                <h2>Журнал решений</h2>
                <p className="sub">Подтверждения менеджера — разметка для обучения следующей версии модели матчинга.</p>
                <div className="byroom" style={{ marginTop: 8 }}>
                    {state.log.length ? state.log.slice(0, 8).map((l, i) => (
                        <div key={i}><span>{l.t}</span><b className="num">{l.v ? l.v + "%" : "правка"}</b></div>
                    )) : <div className="sub">Пока пусто: подтвердите товар или поменяйте тип работ</div>}
                </div>
            </div>
        </section>
    );
}

import { useEffect, useRef, useState } from "react";
import { CONFIDENCE_THRESHOLD } from "@/data/catalog.ts";
import {
    confirmMatches, getHealth, isAbort, matchedProducts, trainModel, updateMatch,
    type MatchedList, type MatchedParams, type MatchedProduct, type MLStatus,
} from "@/api/client.ts";
import { useWorkTypes, workTypeName } from "@/api/useWorkTypes.ts";
import { rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

const PER_PAGE = 20;
type Mode = "all" | "uncertain" | "disagree";

const ML_STAGE: Record<string, string> = {
    embedding: "считаем эмбеддинги", training: "обучаем классификатор", predicting: "размечаем каталог",
    saving: "сохраняем предсказания", loading: "загружаем товары",
};

export default function AdminPage() {
    const { state, update } = useProject();
    const toast = useToast();
    const types = useWorkTypes();
    const [q, setQ] = useState("");
    const [workType, setWorkType] = useState("");
    const [mode, setMode] = useState<Mode>("uncertain");
    const [page, setPage] = useState(1);
    const [version, setVersion] = useState(0);   // перезагрузка списка после изменений
    const [res, setRes] = useState<{ key: string; data?: MatchedList; error?: string } | null>(null);
    const [ml, setMl] = useState<(MLStatus & { ready: boolean }) | null>(null);
    const wasBusy = useRef(false);

    const params: MatchedParams = {
        q: q.trim() || undefined,
        work_type: workType || undefined,
        // «неуверенные» — модель не дотянула до порога: такие товары не идут в подбор
        max_confidence: mode === "uncertain" ? CONFIDENCE_THRESHOLD - 0.0001 : undefined,
        disagree: mode === "disagree" || undefined,
        sort: mode === "all" ? "confidence_desc" : "confidence_asc",
        page,
        per_page: PER_PAGE,
    };
    const key = JSON.stringify(params);
    const fetchKey = key + "#" + version;

    useEffect(() => {
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            matchedProducts(JSON.parse(key) as MatchedParams, ctrl.signal)
                .then(data => setRes({ key: fetchKey, data }))
                .catch((e: unknown) => { if (!isAbort(e)) setRes({ key: fetchKey, error: e instanceof Error ? e.message : String(e) }); });
        }, 250);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
    }, [key, fetchKey]);

    // состояние обучения модели; пока идёт — опрашиваем
    useEffect(() => {
        const ctrl = new AbortController();
        let timer = 0;
        const poll = () => getHealth(ctrl.signal)
            .then(h => {
                setMl(h.ml ?? null);
                if (h.ml && ["running", "queued"].includes(h.ml.state)) {
                    wasBusy.current = true;
                    timer = window.setTimeout(poll, 3000);
                } else if (wasBusy.current) {
                    wasBusy.current = false;
                    setVersion(v => v + 1);   // обучение закончилось — обновляем предсказания в таблице
                }
            })
            .catch(() => { /* статус необязателен */ });
        poll();
        return () => { ctrl.abort(); window.clearTimeout(timer); };
    }, [version]);

    const data = res?.data;
    const loading = res?.key !== fetchKey;
    const threshold = data?.threshold ?? CONFIDENCE_THRESHOLD;
    const training = ml && ["running", "queued"].includes(ml.state);
    const log = (t: string, v: number) => update(s => ({ ...s, log: [{ t, v }, ...s.log] }));
    const fail = (e: unknown) => toast("Не удалось сохранить: " + (e instanceof Error ? e.message : String(e)));
    const setFilter = (fn: () => void) => { fn(); setPage(1); };

    const confirm = (p: MatchedProduct) => updateMatch(p.id)
        .then(() => { log(p.name, Math.round(p.confidence * 100)); setVersion(v => v + 1); })
        .catch(fail);

    const relabel = (p: MatchedProduct, wt: string) => updateMatch(p.id, wt)
        .then(saved => {
            log(`${p.name}: ${saved.work_type ? `тип работ «${saved.work_type_name}»` : "не относится к работам"}`, 0);
            setVersion(v => v + 1);
        })
        .catch(fail);

    const bulk = () => {
        confirmMatches({ min_confidence: threshold, work_type: workType || undefined, q: q.trim() || undefined })
            .then(r => {
                if (r.confirmed) log(`Массовое подтверждение: ${r.confirmed.toLocaleString("ru-RU")} товаров`, Math.round(threshold * 100));
                setVersion(v => v + 1);
                toast(r.confirmed ? `Подтверждено товаров: ${r.confirmed.toLocaleString("ru-RU")}`
                    : `Все уверенные предсказания (от ${Math.round(threshold * 100)}%) уже подтверждены`);
            })
            .catch(fail);
    };

    const retrain = () => trainModel()
        .then(() => { toast("Модель переобучается на текущей разметке"); setVersion(v => v + 1); })
        .catch(e => toast(e instanceof Error ? e.message : String(e)));

    return (
        <section>
            <div className="card">
                <div className="rhead">
                    <div>
                        <h2>Разметка каталога ML-моделью</h2>
                        <p className="sub">
                            Модель (эмбеддинги rubert-tiny2 + логистическая регрессия) относит товары к типам работ.
                            В подбор калькулятора попадают предсказания с уверенностью от {Math.round(threshold * 100)}%
                            и решения менеджера. Исправления и подтверждения — разметка для следующего обучения.
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <button className="btn g" onClick={retrain} disabled={Boolean(training)}>
                            {training ? "Модель обучается…" : "Переобучить модель"}
                        </button>
                        <button className="btn" onClick={bulk}>Подтвердить от {Math.round(threshold * 100)}%</button>
                    </div>
                </div>
                {ml && (
                    <p className="sub" style={{ marginTop: 8 }}>
                        <span className={"status-dot" + (ml.ready && !training ? " ok" : ml.state === "error" ? " bad" : "")}></span>
                        {training ? `Обучение: ${ML_STAGE[ml.stage ?? ""] ?? "в очереди"}${ml.total ? ` (${(ml.processed ?? 0).toLocaleString("ru-RU")} из ${ml.total.toLocaleString("ru-RU")})` : ""}`
                            : ml.state === "error" ? `Ошибка обучения: ${ml.error}` : ml.ready ? "Модель обучена и размечает каталог" : "Модель ещё не обучена"}
                    </p>
                )}
                <div className="chips">
                    {([["uncertain", `Неуверенные (< ${Math.round(threshold * 100)}%)`], ["disagree", "Расходятся с разметкой"], ["all", "Все предсказания"]] as [Mode, string][]).map(([m, l]) => (
                        <button key={m} aria-pressed={mode === m} onClick={() => setFilter(() => setMode(m))}>{l}</button>
                    ))}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "minmax(0,360px) minmax(0,260px)", gap: 10 }}>
                    <div>
                        <label className="lab" htmlFor="aq">Поиск по названию</label>
                        <input id="aq" type="search" value={q} onChange={e => setFilter(() => setQ(e.target.value))} />
                    </div>
                    <div>
                        <label className="lab" htmlFor="aw">Тип работ (предсказание)</label>
                        <select id="aw" value={workType} onChange={e => setFilter(() => setWorkType(e.target.value))}>
                            <option value="">Все типы</option>
                            {types.filter(t => t.predicted > 0).map(t => <option key={t.code} value={t.code}>{t.name} ({t.predicted})</option>)}
                        </select>
                    </div>
                </div>
            </div>
            <div className="card">
                {res?.error && !loading ? <p className="sub" style={{ color: "var(--brand)" }}>Сервис недоступен: {res.error}</p> : (
                    <table style={{ opacity: loading ? 0.6 : 1 }}>
                        <thead>
                            <tr><th style={{ width: "30%" }}>Товар</th><th>Тип работ</th><th>Метка обучения</th><th>Уверенность модели</th><th className="r">Действие</th></tr>
                        </thead>
                        <tbody>
                            {data?.items.length ? data.items.map(p => {
                                const v = Math.round(p.confidence * 100);
                                const manager = p.source === "manager";
                                return (
                                    <tr key={p.id}>
                                        <td>
                                            <b style={{ fontWeight: 600 }}>{p.name}</b>
                                            <small>{rub(p.price)}{p.suitable_rooms.length ? ` · ${p.suitable_rooms.join(", ")}` : ""}</small>
                                        </td>
                                        <td>
                                            <select aria-label="Тип работ" value={p.work_type ?? "other"} onChange={e => relabel(p, e.target.value)}>
                                                <option value="other">Не относится к работам</option>
                                                {types.map(t => <option key={t.code} value={t.code}>{t.name}</option>)}
                                            </select>
                                        </td>
                                        <td>
                                            {p.label_work_type ? (
                                                <>
                                                    <span className={"tag" + (p.agrees_with_label ? " ok" : " w")}>
                                                        {p.label_work_type === "other" ? "не работы" : workTypeName(types, p.label_work_type)}
                                                    </span>
                                                    <small>{p.label_source === "manager" ? "менеджер" : "правила (обучающая выборка)"}</small>
                                                </>
                                            ) : <span className="sub">нет метки</span>}
                                        </td>
                                        <td>
                                            {manager ? <span className="tag ok">менеджер</span> : (
                                                <div className="score">
                                                    <div className="bar"><i className={p.accepted ? "" : "m"} style={{ width: v + "%" }}></i></div>
                                                    <span className="num">{v}%</span>
                                                </div>
                                            )}
                                        </td>
                                        <td className="r">
                                            {manager ? <span className="tag ok">подтверждено</span>
                                                : <button className={"btn sm" + (p.accepted ? " g" : "")} onClick={() => confirm(p)}>{p.accepted ? "Подтвердить" : "Проверить"}</button>}
                                        </td>
                                    </tr>
                                );
                            }) : (
                                <tr><td colSpan={5} className="sub" style={{ padding: "18px 0" }}>
                                    {loading ? "Загружаем…" : training ? "Модель ещё размечает каталог" : "Ничего не найдено"}
                                </td></tr>
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
                <p className="sub">Решения менеджера сразу действуют в подборе и попадают в обучающую выборку при следующем переобучении.</p>
                <div className="byroom" style={{ marginTop: 8 }}>
                    {state.log.length ? state.log.slice(0, 8).map((l, i) => (
                        <div key={i}><span>{l.t}</span><b className="num">{l.v ? l.v + "%" : "правка"}</b></div>
                    )) : <div className="sub">Пока пусто: подтвердите предсказание или исправьте тип работ</div>}
                </div>
            </div>
        </section>
    );
}

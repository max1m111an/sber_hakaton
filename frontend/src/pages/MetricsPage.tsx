import { useEffect, useState } from "react";
import { getStats, isAbort, type Stats } from "@/api/client.ts";
import { useWorkTypes, workTypeName } from "@/api/useWorkTypes.ts";
import { useProject } from "@/store/projectContext.ts";

const LOW_BUCKETS = ["<0.6", "0.6–0.8"];
const pct = (a: number, b: number) => (b ? Math.round(a / b * 1000) / 10 : 0);
const fmt = (n: number) => n.toLocaleString("ru-RU");
const comma = (x: number, digits = 2) => x.toFixed(digits).replace(".", ",");
const P = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${comma(x * 100, 1)}%`);

export default function MetricsPage() {
    const { state } = useProject();
    const types = useWorkTypes();
    const [stats, setStats] = useState<{ data?: Stats; error?: string } | null>(null);

    useEffect(() => {
        const ctrl = new AbortController();
        getStats(ctrl.signal)
            .then(data => setStats({ data }))
            .catch((e: unknown) => { if (!isAbort(e)) setStats({ error: e instanceof Error ? e.message : String(e) }); });
        return () => ctrl.abort();
    }, []);

    const s = stats?.data;
    const ml = s?.ml;
    const h = ml?.holdout;
    const pr = ml?.predictions;
    const manager = s?.by_source.manager ?? 0;
    const perClass = Object.entries(ml?.per_class ?? {}).sort((a, b) => b[1].support - a[1].support);
    const buckets = ml?.live?.confidence_buckets ?? [];
    const maxBucket = Math.max(1, ...buckets.map(b => b.count));
    const trainedAt = ml?.trained_at ? new Date(ml.trained_at * 1000).toLocaleString("ru-RU") : null;

    const kpis: [string, string, string][] = s ? [
        [h ? comma(h.macro_f1) : "—", "macro F1 на отложенной выборке", h ? `${fmt(h.holdout_size)} товаров, цель MVP ≥ 0,80` : "модель ещё не обучена"],
        [h ? P(h.precision_at_threshold) : "—", `точность при уверенности ≥ ${comma(ml!.threshold)}`,
            h ? `полнота ${P(h.recall_at_threshold)}` : ""],
        [fmt(s.classified), "товаров в подборе калькулятора", `${fmt(s.predicted)} отнесено моделью, ${fmt(manager)} — менеджером`],
        [pr ? fmt(pr.new_beyond_rules) : "—", "уверенных находок сверх правил", "товары, которые правила по ключевым словам не нашли"],
    ] : [];

    return (
        <section>
            {stats?.error && <div className="card"><p className="sub" style={{ color: "var(--brand)" }}>Статистика недоступна: {stats.error}</p></div>}
            <div className="kpis">
                {kpis.length ? kpis.map(k => (
                    <div className="kpi" key={k[1]}><b className="num">{k[0]}</b><span>{k[1]}</span>{k[2] && <em>{k[2]}</em>}</div>
                )) : !stats?.error && <div className="kpi"><span>Загружаем статистику…</span></div>}
            </div>
            <div className="cols2" style={{ marginTop: 16 }}>
                <div className="card">
                    <h2>Качество матчинга по типам работ</h2>
                    <p className="sub">F1 на отложенных 20% размеченной выборки (стратифицированно), цель MVP — 0,80</p>
                    <div style={{ marginTop: 12 }}>
                        {perClass.length ? perClass.map(([code, m]) => (
                            <div className="mrow" key={code} title={`precision ${comma(m.precision)} · recall ${comma(m.recall)} · ${m.support} товаров`}>
                                <span>{workTypeName(types, code)}</span>
                                <div className="bar"><i className={m.f1 < 0.8 ? "m" : ""} style={{ width: m.f1 * 100 + "%" }}></i></div>
                                <b className="num">{comma(m.f1)}</b>
                            </div>
                        )) : <p className="sub">Метрики появятся после обучения модели.</p>}
                    </div>
                </div>
                <div className="card">
                    <h2>Уверенность модели по каталогу</h2>
                    <p className="sub">
                        Товары, отнесённые моделью к типам работ. В подбор идут товары с уверенностью от {ml ? comma(ml.threshold, 1) : "0,8"}.
                        {ml?.live?.mean_confidence !== null && ml?.live?.mean_confidence !== undefined && ` Средняя уверенность ${P(ml.live.mean_confidence)}.`}
                    </p>
                    <div style={{ marginTop: 12 }}>
                        {buckets.map(b => (
                            <div className="mrow" key={b.bucket}>
                                <span>{b.bucket.replace(/\./g, ",")}</span>
                                <div className="bar"><i className={LOW_BUCKETS.includes(b.bucket) ? "m" : ""} style={{ width: b.count / maxBucket * 100 + "%" }}></i></div>
                                <b className="num">{fmt(b.count)}</b>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
            <div className="card">
                <h2>Модель</h2>
                {ml ? (
                    <div className="cols2" style={{ marginTop: 10 }}>
                        <dl className="specs" style={{ marginTop: 0 }}>
                            <dt>Эмбеддинги</dt><dd>{ml.encoder}</dd>
                            <dt>Классификатор</dt><dd>LogisticRegression (scikit-learn)</dd>
                            <dt>Обучена</dt><dd>{trainedAt ?? (ml.status.state === "running" ? "идёт обучение…" : "ещё не обучалась")}</dd>
                            <dt>Обучающая выборка</dt><dd className="num">{ml.train_size ? fmt(ml.train_size) : "—"}</dd>
                            <dt>Accuracy (holdout)</dt><dd className="num">{h ? P(h.accuracy) : "—"}</dd>
                        </dl>
                        <dl className="specs" style={{ marginTop: 0 }}>
                            <dt>Метки правил</dt><dd className="num">{fmt(ml.label_sources?.rules ?? 0)}</dd>
                            <dt>Метки менеджера</dt><dd className="num">{fmt(ml.label_sources?.manager ?? 0)}{state.log.length ? ` (+${state.log.length} в этой сессии)` : ""}</dd>
                            <dt>Класс «не работы»</dt><dd className="num">{fmt(ml.label_sources?.other_sampled ?? 0)} случайных товаров</dd>
                            <dt>Совпадение с правилами</dt><dd className="num">{P(pr?.agreement_with_rules)}</dd>
                            <dt>С фасовкой (в подборе)</dt><dd className="num">{s ? `${comma(pct(s.with_package, s.classified), 1)}%` : "—"}</dd>
                        </dl>
                    </div>
                ) : <p className="sub">Загружаем…</p>}
                <p className="sub" style={{ marginTop: 12 }}>
                    Обучающая выборка собирается из слабой разметки правил по ключевым словам и решений менеджера в «Разметке каталога»;
                    правила в подборе товаров не участвуют. Решения менеджера вытесняют правила при следующем обучении.
                </p>
            </div>
        </section>
    );
}

import { useEffect, useState } from "react";
import { getStats, isAbort, type Stats } from "@/api/client.ts";
import { useWorkTypes } from "@/api/useWorkTypes.ts";
import { useProject } from "@/store/projectContext.ts";

const F1: [string, number][] = [
    ["Напольные покрытия", .89], ["Отделка стен", .86], ["Влагостойкие материалы", .84], ["Электрика", .78], ["Сопутствующее", .71],
];

const pct = (a: number, b: number) => (b ? Math.round(a / b * 1000) / 10 : 0);
const fmt = (n: number) => n.toLocaleString("ru-RU");
const comma = (s: string) => s.replace(".", ",");

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
    const manager = s?.by_source.manager ?? 0;
    const byCategory = s?.by_source.category ?? 0;
    const byName = s?.by_source.name ?? 0;
    const top = [...types].filter(t => t.products > 0).sort((a, b) => b.products - a.products).slice(0, 8);
    const maxTop = top[0]?.products ?? 1;

    const kpis: [string, string, string][] = s ? [
        [fmt(s.products), "товаров в каталоге", `${fmt(s.categories)} категорий из выгрузки`],
        [fmt(s.classified), "товаров привязано к типам работ", `${comma(String(pct(s.classified - manager, s.classified)))}% — автоматически`],
        [`${comma(String(pct(s.with_package, s.classified)))}%`, "размеченных товаров с распознанной фасовкой", "м², кг, л или длина упаковки"],
        [fmt(manager), "подтверждено менеджером", state.log.length ? `${state.log.length} решений в этой сессии` : "разметка для обучения модели"],
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
                    <h2>Разметка каталога по типам работ</h2>
                    <p className="sub">Сколько товаров сервис отнёс к каждому типу работ</p>
                    <div style={{ marginTop: 12 }}>
                        {top.map(t => (
                            <div className="mrow" key={t.code}>
                                <span>{t.name}</span>
                                <div className="bar"><i style={{ width: t.products / maxTop * 100 + "%" }}></i></div>
                                <b className="num">{fmt(t.products)}</b>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="card">
                    <h2>Источник разметки</h2>
                    <p className="sub">По категории — уверенность 95%, по названию товара — 75%, менеджер — 100%</p>
                    {s && (
                        <div style={{ marginTop: 12 }}>
                            {([["По категории", byCategory], ["По названию товара", byName], ["Менеджер", manager]] as [string, number][]).map(([n, v]) => (
                                <div className="mrow" key={n}>
                                    <span>{n}</span>
                                    <div className="bar"><i className={n === "По названию товара" ? "m" : ""} style={{ width: pct(v, s.classified) + "%" }}></i></div>
                                    <b className="num">{fmt(v)}</b>
                                </div>
                            ))}
                            <p className="sub" style={{ marginTop: 10 }}>
                                Нормативов расхода в базе: {s.rules}. Товары, размеченные по названию, стоит проверить в разделе «Разметка каталога».
                            </p>
                        </div>
                    )}
                </div>
            </div>
            <div className="card">
                <h2>Целевые метрики ML-матчинга</h2>
                <p className="sub">
                    Демо-значения из макета: размеченной выборки для расчёта F1 пока нет, её наполняют подтверждения менеджера. Цель MVP — F1 ≥ 0,80.
                </p>
                <div style={{ marginTop: 12 }}>
                    {F1.map(([n, v]) => (
                        <div className="mrow" key={n}>
                            <span>{n}</span>
                            <div className="bar"><i className={v < .8 ? "m" : ""} style={{ width: v * 100 + "%" }}></i></div>
                            <b className="num">{comma(v.toFixed(2))}</b>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

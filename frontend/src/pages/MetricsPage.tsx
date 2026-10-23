import { useProject } from "@/store/projectContext.ts";

const F1: [string, number][] = [
    ["Напольные покрытия", .89], ["Отделка стен", .86], ["Влагостойкие материалы", .84], ["Электрика", .78], ["Сопутствующее", .71],
];
const MAE: [string, number][] = [
    ["Плитка и керамогранит", .058], ["Обои", .049], ["Краска", .071], ["Ламинат", .035],
];

const comma = (s: string) => s.replace(".", ",");

export default function MetricsPage() {
    const { state } = useProject();
    const done = state.admin.filter(a => a.ok).length;
    const kpis: [string, string, string][] = [
        ["0,84", "F1 матчинга на топ-категориях", "цель 0,80 выполнена"],
        [`${done} из ${state.admin.length}`, "товаров размечено в этой сессии", ""],
        ["6,2%", "MAE расхода материалов", "было 11,4% на нормативах"],
        ["3 с", "сборка сметы по 3 помещениям", ""],
    ];

    return (
        <section>
            <div className="kpis">
                {kpis.map(k => (
                    <div className="kpi" key={k[1]}><b className="num">{k[0]}</b><span>{k[1]}</span>{k[2] && <em>{k[2]}</em>}</div>
                ))}
            </div>
            <div className="cols2" style={{ marginTop: 16 }}>
                <div className="card">
                    <h2>Качество матчинга по категориям</h2>
                    <p className="sub">F1 на размеченном сабсете, цель MVP — 0,80</p>
                    <div style={{ marginTop: 12 }}>
                        {F1.map(([n, v]) => (
                            <div className="mrow" key={n}>
                                <span>{n}</span>
                                <div className="bar"><i className={v < .8 ? "m" : ""} style={{ width: v * 100 + "%" }}></i></div>
                                <b className="num">{comma(v.toFixed(2))}</b>
                            </div>
                        ))}
                        <p className="sub" style={{ marginTop: 10 }}>Сопутствующие товары пока ниже порога: в описаниях мало признаков, связывающих их с типом работ.</p>
                    </div>
                </div>
                <div className="card">
                    <h2>Точность расчёта расхода</h2>
                    <p className="sub">MAE по количеству упаковок против эталонных смет</p>
                    <div style={{ marginTop: 12 }}>
                        {MAE.map(([n, v]) => (
                            <div className="mrow" key={n}>
                                <span>{n}</span>
                                <div className="bar"><i style={{ width: v * 700 + "%" }}></i></div>
                                <b className="num">{comma((v * 100).toFixed(1))}%</b>
                            </div>
                        ))}
                    </div>
                    <p className="sub" style={{ marginTop: 12 }}>Поправочные коэффициенты обучаются на реальных заказах: по плитке подрезка выше норматива, по краске — ниже.</p>
                </div>
            </div>
            <div className="card">
                <h2>Бизнес-эффект</h2>
                <div className="cols2" style={{ marginTop: 10 }}>
                    <div>
                        <div className="mrow"><span>Товаров привязано автоматически</span><div className="bar"><i style={{ width: "82%" }}></i></div><b className="num">82%</b></div>
                        <div className="mrow"><span>Ручная разметка до сервиса</span><div className="bar"><i className="m" style={{ width: "18%" }}></i></div><b className="num">18%</b></div>
                    </div>
                    <div>
                        <div className="mrow"><span>Сборка сметы, сек</span><div className="bar"><i style={{ width: "30%" }}></i></div><b className="num">3</b></div>
                        <div className="mrow"><span>Кликов до корзины</span><div className="bar"><i style={{ width: "45%" }}></i></div><b className="num">5</b></div>
                    </div>
                </div>
            </div>
        </section>
    );
}

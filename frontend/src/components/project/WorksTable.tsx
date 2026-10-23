import { HUM, LK, SKU, TIER_TEXT, type Room } from "@/data/catalog.ts";
import { MLFIX } from "@/data/catalog.ts";
import type { EstimateLine } from "@/lib/estimate.ts";
import { d1, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";

function WhyBox({ room, lines }: { room: Room; lines: EstimateLine[] }) {
    const { state } = useProject();
    const excl = [...new Set(
        SKU.filter(s => s.wet < room.hum && ["floor", "wall", "base", "fix"].includes(s.c))
            .map(s => s.n.split(",")[0].toLowerCase()),
    )].slice(0, 3);
    const items = lines.filter(l => l.on && !l.aux && l.best).slice(0, 3);

    return (
        <div className="why">
            <b>Почему эти материалы</b>
            {room.n}, влажность {HUM[room.hum]}. {TIER_TEXT[state.tier]}{" "}
            {excl.length > 0 && `Из подбора убраны материалы, не рассчитанные на такую влажность: ${excl.join(", ")}.`}
            <ul>
                {items.map(l => (
                    <li key={l.key}>
                        {l.title.toLowerCase()}: {l.s.n} — {l.s.wet === 2 ? "держит влажность, " : ""}рейтинг просмотров {l.s.views} из 100
                    </li>
                ))}
            </ul>
            Расход считается по нормативам из базы знаний, сверху добавлен запас на подрезку и поправка +1,5%, обученная на реальных заказах.
            <small>Пояснение собирает локальная модель: нормы расхода находятся поиском по базе знаний, затем модель формулирует ответ.</small>
        </div>
    );
}

export default function WorksTable({ room, lines }: { room: Room; lines: EstimateLine[] }) {
    const { state, updateRoom } = useProject();
    const k = LK[state.lvl];
    const works = lines.filter(l => !l.aux);
    const nOn = works.filter(l => l.on).length;

    return (
        <div className="card">
            <div className="rhead">
                <div>
                    <h2>Работы и материалы</h2>
                    <p className="sub">{nOn} из {works.length} работ включено · материалы подобраны под влажность «{HUM[room.hum]}»</p>
                </div>
            </div>
            <table className="t-works" style={{ marginTop: 12 }}>
                <thead>
                    <tr>
                        <th style={{ width: "52%" }}>Работа и материал</th>
                        <th className="r">Объём</th>
                        <th className="r">Материалы</th>
                        <th className="r">Работы</th>
                    </tr>
                </thead>
                <tbody>
                    {lines.map(l => (
                        <tr key={l.key} className={l.on ? "" : "off"}>
                            <td>
                                <div style={{ display: "flex", alignItems: "center" }}>
                                    {!l.aux && (
                                        <label className="sw" style={{ marginRight: 8 }}>
                                            <input type="checkbox" checked={l.on} aria-label={"Включить работу " + l.title}
                                                onChange={e => updateRoom(r => ({ ...r, off: { ...r.off, [l.key]: !e.target.checked } }))} />
                                            <i></i>
                                        </label>
                                    )}
                                    <b style={{ fontWeight: 600 }}>{l.title}</b>
                                </div>
                                {l.aux ? (
                                    <small>{l.s.u} · {rub(l.s.p * k)}</small>
                                ) : (
                                    <>
                                        <div className="pick">
                                            <select value={l.s.id} aria-label={"Материал: " + l.title}
                                                onChange={e => updateRoom(r => ({ ...r, pick: { ...r.pick, [l.key]: +e.target.value } }))}>
                                                {l.list.map(s => <option key={s.id} value={s.id}>{s.n} — {rub(s.p * k)}</option>)}
                                            </select>
                                            {l.best ? <span className="tag top">выбор модели</span> : <span className="tag">замена вручную</span>}
                                            {l.s.wet === 2 && room.hum > 0 && SKU.some(x => x.c === l.key && x.wet < 2) &&
                                                <span className="tag wet">влагостойкий</span>}
                                        </div>
                                        <small className="num">
                                            {l.s.u} · {l.packs} уп. · запас {Math.round((l.s.waste + (l.s.waste ? MLFIX : 0)) * 100)}% · остаток {l.s.stock}
                                        </small>
                                    </>
                                )}
                            </td>
                            <td className="r num">{l.aux ? "—" : `${d1(l.qty)} ${l.unit}`}</td>
                            <td className="r num">{l.on ? rub(l.mat) : "—"}</td>
                            <td className="r num">{l.lab ? rub(l.lab) : "—"}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <WhyBox room={room} lines={lines} />
        </div>
    );
}

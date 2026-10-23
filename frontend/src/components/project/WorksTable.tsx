import { TIER_TEXT, type Room } from "@/data/catalog.ts";
import type { EstimateLine, ProductBrief, RoomEstimate } from "@/api/client.ts";
import { d1, rub } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";

const NOTE_SKIP = /ориентировочн|result_price/;

function WhyBox({ result }: { result: RoomEstimate }) {
    const items = result.items.filter(l => l.enabled && l.product).slice(0, 4);
    const notes = result.notes.filter(n => !NOTE_SKIP.test(n));
    return (
        <div className="why">
            <b>Почему эти материалы</b>
            {result.room_type}, влажность {result.humidity_level}. {TIER_TEXT[result.tier] ?? ""}
            <ul>
                {items.map(l => <li key={l.rule_code}>{l.title.toLowerCase()}: {l.product!.name} — {l.explanation}</li>)}
            </ul>
            {notes.map(n => <p key={n} style={{ marginTop: 6 }}>{n}</p>)}
            <small>
                Расход считается по нормативам расхода (таблица normative_rule) или по данным карточки товара;
                цены — из выгрузки каталога maxidom.ru. Стоимость работ ориентировочная.
            </small>
        </div>
    );
}

const optionText = (p: ProductBrief, packs: number, cost: number) =>
    `${p.name} — ${packs} × ${rub(p.price)} = ${rub(cost)}`;

function MaterialCell({ line, onPick }: { line: EstimateLine; onPick: (id: number) => void }) {
    const p = line.product;
    if (!p) return <small style={{ color: "var(--brand)" }}>Нет подходящего товара в каталоге</small>;
    const options = [{ ...p, packages_needed: line.packages_needed, material_cost: line.material_cost }, ...line.alternatives];
    return (
        <>
            <div className="pick">
                <select value={p.product_id} aria-label={"Материал: " + line.title} onChange={e => onPick(+e.target.value)}>
                    {options.map(o => <option key={o.product_id} value={o.product_id}>{optionText(o, o.packages_needed, o.material_cost)}</option>)}
                </select>
                {line.manual ? <span className="tag">замена вручную</span> : <span className="tag top">выбор сервиса</span>}
                {p.moisture_resistant && <span className="tag wet">влагостойкий</span>}
            </div>
            <small className="num">
                {p.pack} · {line.packages_needed} уп. · запас {d1(line.waste_percent)}%
                {line.consumption_rate ? ` · расход ${String(line.consumption_rate).replace(".", ",")} (${line.consumption_source})` : ""}
            </small>
            {line.pick_rejected && <small style={{ color: "var(--brand)" }}>{line.pick_rejected}</small>}
        </>
    );
}

export default function WorksTable({ room, result, loading, error }: {
    room: Room; result: RoomEstimate | null; loading: boolean; error: string | null;
}) {
    const { state, updateRoom } = useProject();
    const lines = result?.items ?? [];
    const nOn = lines.filter(l => l.enabled).length;

    const toggle = (code: string, on: boolean) => updateRoom(r => ({
        ...r, disabled: on ? r.disabled.filter(c => c !== code) : [...r.disabled, code],
    }));
    const pickProduct = (code: string, id: number) => updateRoom(r => ({ ...r, picks: { ...r.picks, [code]: id } }));
    const resetPicks = () => updateRoom(r => ({ ...r, picks: {} }));

    return (
        <div className="card">
            <div className="rhead">
                <div>
                    <h2>Работы и материалы</h2>
                    <p className="sub">
                        {result ? `${nOn} из ${lines.length} работ включено · подбор под влажность «${result.humidity_level}»`
                            : error ? "" : "Считаем смету…"}
                        {loading && result ? " · пересчитываем…" : ""}
                    </p>
                </div>
                {Object.keys(room.picks).length > 0 &&
                    <button className="btn g sm" onClick={resetPicks}>Вернуть выбор сервиса</button>}
            </div>
            {error && (
                <div className="why" style={{ borderLeftColor: "var(--brand)", background: "var(--brandsoft)" }}>
                    <b>Смета не посчитана</b>{error}. Проверьте, что backend запущен и каталог загружен (статус — внизу меню).
                </div>
            )}
            {result && (
                <table className="t-works" style={{ marginTop: 12, opacity: loading ? 0.6 : 1 }}>
                    <thead>
                        <tr>
                            <th style={{ width: "56%" }}>Работа и материал</th>
                            <th className="r">Объём</th>
                            <th className="r">Материалы</th>
                            <th className="r">Работы</th>
                        </tr>
                    </thead>
                    <tbody>
                        {lines.map(l => (
                            <tr key={l.rule_code} className={l.enabled ? "" : "off"}>
                                <td>
                                    <div style={{ display: "flex", alignItems: "center" }}>
                                        <label className="sw" style={{ marginRight: 8 }}>
                                            <input type="checkbox" checked={l.enabled} aria-label={"Включить работу " + l.title}
                                                onChange={e => toggle(l.rule_code, e.target.checked)} />
                                            <i></i>
                                        </label>
                                        <b style={{ fontWeight: 600 }}>{l.title}</b>
                                    </div>
                                    <MaterialCell line={l} onPick={id => pickProduct(l.rule_code, id)} />
                                </td>
                                <td className="r num">{d1(l.surface)} {l.surface_unit}</td>
                                <td className="r num">{l.enabled && l.product ? rub(l.material_cost) : "—"}</td>
                                <td className="r num">{l.enabled && l.labor_cost ? rub(l.labor_cost) : "—"}</td>
                            </tr>
                        ))}
                        {!lines.length && (
                            <tr><td colSpan={4} className="sub" style={{ padding: "18px 0" }}>
                                Для помещения «{room.n}» при уровне ремонта нет нормативов.
                            </td></tr>
                        )}
                    </tbody>
                </table>
            )}
            {result && <WhyBox result={result} />}
            {state.tier && <p className="sub" style={{ marginTop: 8 }}>Ценовой сегмент задан вручную в смете проекта.</p>}
        </div>
    );
}

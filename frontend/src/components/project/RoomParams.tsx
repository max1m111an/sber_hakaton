import { HUM, LVL, per, wallA, type Humidity, type RepairLevel, type Room } from "@/data/catalog.ts";
import { d1, num } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";

export default function RoomParams({ room }: { room: Room }) {
    const { state, update, updateRoom } = useProject();

    const setNum = (k: "a" | "ch" | "op") => (v: string) =>
        updateRoom(r => ({ ...r, [k]: Math.max(0, num(v)) }));

    return (
        <div className="card">
            <div className="rhead">
                <div>
                    <h2>{room.n}</h2>
                    <p className="sub">Стены {d1(wallA(room))} м² · периметр {d1(per(room))} м · влажность {HUM[room.hum]}</p>
                </div>
                <div className="seg lvlseg">
                    {LVL.map((l, i) => (
                        <button key={l} aria-pressed={i === state.lvl}
                            onClick={() => update(s => ({ ...s, lvl: i as RepairLevel }))}>{l}</button>
                    ))}
                </div>
            </div>
            <div className="params">
                <div>
                    <label className="lab" style={{ marginTop: 0 }} htmlFor="pa">Площадь пола, м²</label>
                    <input id="pa" type="number" step={0.5} min={2} value={room.a} onChange={e => setNum("a")(e.target.value)} />
                    <div className="tape">
                        <input type="range" min={2} max={45} step={0.5} aria-label="Площадь пола"
                            value={Math.min(45, room.a)} onChange={e => setNum("a")(e.target.value)} />
                    </div>
                </div>
                <div>
                    <label className="lab" style={{ marginTop: 0 }} htmlFor="ph">Высота потолка, м</label>
                    <input id="ph" type="number" step={0.05} min={2} max={4} value={room.ch} onChange={e => setNum("ch")(e.target.value)} />
                </div>
                <div>
                    <label className="lab" style={{ marginTop: 0 }} htmlFor="po">Проёмы (окна, двери), м²</label>
                    <input id="po" type="number" step={0.1} min={0} value={room.op} onChange={e => setNum("op")(e.target.value)} />
                </div>
                <div>
                    <label className="lab" style={{ marginTop: 0 }} htmlFor="pw">Влажность</label>
                    <select id="pw" value={room.hum}
                        onChange={e => updateRoom(r => ({ ...r, hum: +e.target.value as Humidity, pick: {} }))}>
                        <option value={0}>Низкая</option>
                        <option value={1}>Средняя</option>
                        <option value={2}>Высокая</option>
                    </select>
                </div>
            </div>
        </div>
    );
}

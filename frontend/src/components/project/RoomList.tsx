import { useState } from "react";
import { HUM, ROOM_TYPES } from "@/data/catalog.ts";
import { makeRoom } from "@/lib/estimate.ts";
import { d1, num } from "@/lib/format.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";

export default function RoomList() {
    const { state, update } = useProject();
    const toast = useToast();
    const [type, setType] = useState(ROOM_TYPES[0]);
    const [area, setArea] = useState("12");

    const remove = (i: number) => update(s => ({ ...s, rooms: s.rooms.filter((_, j) => j !== i), sel: 0 }));

    const add = () => {
        const room = makeRoom(type, num(area, 12) || 12);
        update(s => ({ ...s, rooms: [...s.rooms, room], sel: s.rooms.length }));
        toast("Добавлено помещение: " + type.toLowerCase());
    };

    return (
        <div className="card">
            <h2>Помещения</h2>
            <p className="sub">Выберите комнату, чтобы настроить работы</p>
            <div className="roomlist" style={{ marginTop: 12 }}>
                {state.rooms.map((r, i) => (
                    <button
                        key={r.id}
                        className={"roomrow h" + r.hum}
                        aria-current={i === state.sel}
                        onClick={() => update(s => ({ ...s, sel: i }))}
                    >
                        <span className="hum"></span>
                        <div>
                            <b>{r.n}</b>
                            <small className="num">{d1(r.a)} м² · влажность {HUM[r.hum]}</small>
                        </div>
                        {state.rooms.length > 1 && (
                            <span
                                className="del"
                                role="button"
                                tabIndex={0}
                                aria-label={"Удалить " + r.n}
                                onClick={e => { e.stopPropagation(); remove(i); }}
                                onKeyDown={e => {
                                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); remove(i); }
                                }}
                            >×</span>
                        )}
                    </button>
                ))}
            </div>
            <div className="addrow">
                <select aria-label="Тип помещения" value={type} onChange={e => setType(e.target.value)}>
                    {ROOM_TYPES.map(k => <option key={k}>{k}</option>)}
                </select>
                <input type="number" min={2} max={80} aria-label="Площадь, м²" value={area} onChange={e => setArea(e.target.value)} />
            </div>
            <button className="btn g sm" style={{ width: "100%", marginTop: 6 }} onClick={add}>Добавить помещение</button>
        </div>
    );
}

import { useState } from "react";
import { LVL } from "@/data/catalog.ts";
import { parseQuery } from "@/lib/estimate.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";
import RoomList from "@/components/project/RoomList.tsx";
import RoomParams from "@/components/project/RoomParams.tsx";
import WorksTable from "@/components/project/WorksTable.tsx";
import SummaryPanel from "@/components/project/SummaryPanel.tsx";

const SAMPLE = "Квартира, капитальный ремонт: санузел 6 м² с высокой влажностью, кухня 11 м², детская 14 м²";

export default function MainPage() {
    const { state, update, estimate } = useProject();
    const toast = useToast();
    const [query, setQuery] = useState(SAMPLE);

    const room = state.rooms[state.sel] ?? state.rooms[0];
    // ответ сервиса относится к текущему набору помещений, если их число совпадает
    const result = estimate.data && estimate.data.rooms.length === state.rooms.length
        ? estimate.data.rooms[state.sel] ?? null : null;

    const parse = () => {
        const { lvl, rooms } = parseQuery(query);
        if (!rooms.length) { toast("Не нашли помещения. Пример: кухня 11 м², санузел 6 м²"); return; }
        update(s => ({ ...s, lvl, rooms, sel: 0 }));
        toast(`Разобрали: ${rooms.length} помещ., ремонт ${LVL[lvl].toLowerCase()}`);
    };

    return (
        <section>
            <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, alignItems: "end" }}>
                    <div>
                        <label className="lab" htmlFor="q" style={{ marginTop: 0 }}>Опишите ремонт своими словами — заполним параметры</label>
                        <input id="q" type="text" value={query} onChange={e => setQuery(e.target.value)}
                            onKeyDown={e => { if (e.key === "Enter") parse(); }} />
                    </div>
                    <button className="btn" onClick={parse}>Разобрать запрос</button>
                </div>
            </div>

            <div className="work">
                <div className="stick"><RoomList /></div>
                <div>
                    <RoomParams room={room} result={result} />
                    <WorksTable room={room} result={result} loading={estimate.loading} error={estimate.error} />
                </div>
                <div className="stick"><SummaryPanel /></div>
            </div>
        </section>
    );
}

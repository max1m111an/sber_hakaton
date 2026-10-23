import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { HUM, LVL_API, type Room } from "@/data/catalog.ts";
import { makeRoom } from "@/lib/estimate.ts";
import { calcGeneral, isAbort, type GeneralRequest } from "@/api/client.ts";
import { ProjectContext, type EstimateState, type ProjectState } from "./projectContext.ts";

const initialState = (): ProjectState => ({
    rooms: [
        makeRoom("Санузел", 6, { ch: 2.55, op: 1.8, hum: 2 }),
        makeRoom("Кухня", 11, { op: 3.2, hum: 1 }),
        makeRoom("Детская", 14, { op: 2.4, hum: 0 }),
    ],
    sel: 0,
    lvl: 1,
    tier: null,
    cart: [],
    budget: 400000,
    log: [],
});

/** Тело запроса к калькулятору — только то, что влияет на смету. */
function requestOf(s: ProjectState): GeneralRequest {
    return {
        object_type: "квартира",
        repair_variant: LVL_API[s.lvl],
        area: Math.max(1, s.rooms.reduce((a, r) => a + r.a, 0)),
        tier: s.tier,
        rooms: s.rooms.map((r: Room) => ({
            room_type: r.n,
            area: Math.max(0.5, r.a),
            ceiling_height: Math.min(6, Math.max(2, r.ch || 2.7)),
            openings_area: Math.max(0, r.op),
            humidity_level: HUM[r.hum],
            picks: r.picks,
            disabled: r.disabled,
        })),
    };
}

export default function ProjectProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<ProjectState>(initialState);
    const [estimate, setEstimate] = useState<EstimateState>({ data: null, loading: true, error: null });

    const update = useCallback((fn: (s: ProjectState) => ProjectState) => setState(fn), []);
    const updateRoom = useCallback((fn: (r: Room) => Room) => setState(s => ({
        ...s,
        rooms: s.rooms.map((r, i) => (i === s.sel ? fn(r) : r)),
    })), []);

    // Пересчёт сметы на сервере: с задержкой, чтобы не слать запрос на каждый символ
    const body = useMemo(() => JSON.stringify(requestOf(state)), [state]);
    useEffect(() => {
        const ctrl = new AbortController();
        const timer = window.setTimeout(() => {
            setEstimate(e => ({ ...e, loading: true }));
            calcGeneral(JSON.parse(body) as GeneralRequest, ctrl.signal)
                .then(data => setEstimate({ data, loading: false, error: null }))
                .catch((err: unknown) => {
                    if (isAbort(err)) return;
                    setEstimate(e => ({ ...e, loading: false, error: err instanceof Error ? err.message : String(err) }));
                });
        }, 350);
        return () => { window.clearTimeout(timer); ctrl.abort(); };
    }, [body]);

    const value = useMemo(() => ({ state, update, updateRoom, estimate }), [state, update, updateRoom, estimate]);
    return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

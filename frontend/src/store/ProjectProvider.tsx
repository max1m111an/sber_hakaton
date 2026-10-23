import { useCallback, useMemo, useState, type ReactNode } from "react";
import { ADMIN_SEED, type Room } from "@/data/catalog.ts";
import { makeRoom } from "@/lib/estimate.ts";
import { ProjectContext, type ProjectState } from "./projectContext.ts";

const initialState = (): ProjectState => ({
    rooms: [
        makeRoom("Санузел", 6, { ch: 2.55, op: 1.8, hum: 2 }),
        makeRoom("Кухня", 11, { op: 3.2, hum: 1 }),
        makeRoom("Детская", 14, { op: 2.4, hum: 0 }),
    ],
    sel: 0,
    lvl: 1,
    tier: 1,
    cart: [],
    budget: 400000,
    admin: ADMIN_SEED.map(a => ({ ...a })),
    log: [],
});

export default function ProjectProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<ProjectState>(initialState);

    const update = useCallback((fn: (s: ProjectState) => ProjectState) => setState(fn), []);
    const updateRoom = useCallback((fn: (r: Room) => Room) => setState(s => ({
        ...s,
        rooms: s.rooms.map((r, i) => (i === s.sel ? fn(r) : r)),
    })), []);

    const value = useMemo(() => ({ state, update, updateRoom }), [state, update, updateRoom]);
    return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

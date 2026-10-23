import { createContext, useContext } from "react";
import type { RepairLevel, Room, Tier } from "@/data/catalog.ts";
import type { GeneralEstimate } from "@/api/client.ts";

export interface CartItem {
    t: string;
    sum: number;
}

export interface LogItem {
    t: string;
    /** Уверенность модели, %; 0 — ручная правка */
    v: number;
}

export interface ProjectState {
    rooms: Room[];
    /** Индекс выбранного помещения */
    sel: number;
    lvl: RepairLevel;
    tier: Tier;
    cart: CartItem[];
    budget: number;
    log: LogItem[];
}

export interface EstimateState {
    data: GeneralEstimate | null;
    loading: boolean;
    error: string | null;
}

export interface ProjectApi {
    state: ProjectState;
    /** Обновить состояние через чистую функцию */
    update: (fn: (s: ProjectState) => ProjectState) => void;
    /** Изменить выбранное помещение */
    updateRoom: (fn: (r: Room) => Room) => void;
    /** Смета с сервера (POST /api/v1/calc/general) */
    estimate: EstimateState;
}

export const ProjectContext = createContext<ProjectApi | null>(null);

export function useProject(): ProjectApi {
    const ctx = useContext(ProjectContext);
    if (!ctx) throw new Error("useProject must be used inside <ProjectProvider>");
    return ctx;
}

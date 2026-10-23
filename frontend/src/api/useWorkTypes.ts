import { useEffect, useState } from "react";
import { getWorkTypes, isAbort, type WorkType } from "@/api/client.ts";

let cache: WorkType[] | null = null;

/** Типы работ с числом товаров (GET /api/v1/work-types), загружаются один раз. */
export function useWorkTypes(): WorkType[] {
    const [types, setTypes] = useState<WorkType[]>(cache ?? []);
    useEffect(() => {
        if (cache) return;
        const ctrl = new AbortController();
        getWorkTypes(ctrl.signal)
            .then(t => { cache = t; setTypes(t); })
            .catch((e: unknown) => { if (!isAbort(e)) setTypes([]); });
        return () => ctrl.abort();
    }, []);
    return types;
}

export const workTypeName = (types: WorkType[], code: string | null) =>
    types.find(t => t.code === code)?.name ?? (code ? code : "—");

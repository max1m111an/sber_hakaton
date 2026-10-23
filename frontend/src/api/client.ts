/**
 * Клиент backend-сервиса RepairCalc (FastAPI).
 * В docker-compose запросы идут через nginx (/api/ → fastapi:8080),
 * в режиме `npm run dev` — через proxy из vite.config.ts.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

// ------------------------------------------------------------------ типы ответов

export interface ProductBrief {
    product_id: number;
    sku: string | null;
    name: string;
    url_key: string | null;
    price: number;
    currency: string;
    unit: string | null;
    pack: string;
    coverage_per_package: number;
    coverage_unit: string;
    moisture_resistant: boolean | null;
}

export interface Alternative extends ProductBrief {
    packages_needed: number;
    material_cost: number;
}

export interface EstimateLine {
    rule_code: string;
    title: string;
    work_type: string;
    work_type_name: string | null;
    recommended_materials: string[];
    enabled: boolean;
    manual: boolean;
    pick_rejected: string | null;
    surface: number;
    surface_unit: string;
    quantity_with_waste: number | null;
    waste_percent: number;
    consumption_rate: number | null;
    consumption_source: string | null;
    product: ProductBrief | null;
    packages_needed: number;
    material_cost: number;
    labor_cost: number;
    formula: string;
    explanation: string;
    alternatives: Alternative[];
}

export interface RoomEstimate {
    room_type: string;
    repair_type: string;
    area: number;
    humidity_level: string;
    tier: string;
    geometry: {
        floor_area: number;
        ceiling_height: number;
        perimeter: number;
        wall_area: number;
        openings_area: number;
        ceiling_area: number;
    };
    items: EstimateLine[];
    materials_cost: number;
    labor_cost: number;
    total_cost: number;
    currency: string;
    notes: string[];
}

export interface ShoppingItem {
    product_id: number;
    sku: string | null;
    name: string;
    pack: string;
    packages_needed: number;
    price_per_package: number;
    subtotal: number;
    rooms: string[];
}

export interface GeneralEstimate {
    object_type: string;
    repair_variant: string;
    area: number;
    tier: string;
    rooms: RoomEstimate[];
    items: ShoppingItem[];
    materials_cost: number;
    labor_cost: number;
    total_cost: number;
    currency: string;
    notes: string[];
}

export interface RoomRequest {
    room_type: string;
    area: number;
    ceiling_height?: number;
    openings_area?: number;
    humidity_level?: string;
    picks?: Record<string, number>;
    disabled?: string[];
}

export interface GeneralRequest {
    object_type: string;
    repair_variant: string;
    area: number;
    rooms: RoomRequest[];
    tier?: string | null;
}

export interface NamedRef {
    id: number | null;
    name: string | null;
}

export interface CatalogProduct {
    id: number;
    sku: string | null;
    cod_good: string;
    name: string;
    url_key: string | null;
    price: number;
    result_price: number;
    currency: string;
    unit: string | null;
    quantity_in_package: number | null;
    package_area: number | null;
    package_weight_kg: number | null;
    package_volume_l: number | null;
    package_length_m: number | null;
    price_per_m2: number | null;
    brand: NamedRef | null;
    country: NamedRef | null;
    categories: Record<string, string>;
    propertiesBottom: { name: string; value: unknown }[];
    work_type: string | null;
    moisture_resistant: boolean | null;
    match_confidence: number;
    match_source: string | null;
}

export interface ProductCard extends CatalogProduct {
    description: string | null;
    marketing_description: string | null;
    characteristics: { code: string | null; name: string; value: unknown }[];
    pack_source: string | null;
    consumption_rate: number | null;
}

export interface ProductList {
    items: CatalogProduct[];
    meta: { total: number; per_page: number; current_page: number; last_page: number };
}

export interface ProductListParams {
    q?: string;
    work_type?: string;
    moisture_resistant?: boolean;
    sort?: "id" | "price_asc" | "price_desc" | "name";
    page?: number;
    per_page?: number;
    category_id?: number;
}

export interface ProductCalcRequest {
    area?: number;
    length?: number;
    width?: number;
    height?: number;
    openings_area?: number;
    extra_waste_percent?: number;
}

export interface ProductCalc {
    product_id: number;
    name: string;
    area: number;
    calc_basis: string;
    rule_code: string | null;
    waste_percent: number;
    need_with_waste: number;
    coverage_per_package: number;
    coverage_unit: string;
    pack: string;
    packages_needed: number;
    units_needed: number | null;
    consumption_rate: number | null;
    consumption_source: string | null;
    price_per_package: number;
    total_cost: number;
    currency: string;
    formula_hint: string;
}

export interface MatchedProduct {
    id: number;
    name: string;
    category_id: number | null;
    work_type: string | null;
    work_type_name: string | null;
    confidence: number;
    source: string | null;
    moisture_resistant: boolean | null;
    suitable_rooms: string[];
    price: number;
}

export interface MatchedList {
    items: MatchedProduct[];
    total: number;
    page: number;
    per_page: number;
}

export interface WorkType {
    code: string;
    name: string;
    products: number;
}

export interface Stats {
    products: number;
    categories: number;
    classified: number;
    with_package: number;
    by_source: Record<string, number>;
    rules: number;
    import_state: string | null;
}

export interface Health {
    status: string;
    db: string;
    products: number | null;
    import: { state: string; processed?: number; error?: string };
}

// ------------------------------------------------------------------ транспорт

export class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
        super(message);
        this.status = status;
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
        res = await fetch(API_BASE + path, {
            ...init,
            headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
        });
    } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") throw e;
        throw new ApiError(0, "Сервис недоступен");
    }
    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
            const body = await res.json() as { detail?: unknown };
            if (typeof body.detail === "string") detail = body.detail;
            else if (Array.isArray(body.detail)) detail = "Проверьте введённые значения";
        } catch { /* тело не JSON */ }
        throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<T>;
}

const query = (params: object) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    }
    const s = q.toString();
    return s ? "?" + s : "";
};

const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

export const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

// ------------------------------------------------------------------ эндпоинты

/** POST /api/v1/calc/general — смета по всем помещениям и сводный список покупок. */
export const calcGeneral = (body: GeneralRequest, signal?: AbortSignal) =>
    post<GeneralEstimate>("/api/v1/calc/general", body, signal);

/** GET /api/catalog/products — товары с фильтрами и пагинацией. */
export const listProducts = (params: ProductListParams, signal?: AbortSignal) =>
    request<ProductList>("/api/catalog/products" + query(params), { signal });

/** GET /api/catalog/products/{id} — полная карточка. */
export const getProduct = (id: number, signal?: AbortSignal) =>
    request<{ data: ProductCard }>(`/api/catalog/products/${id}`, { signal }).then(r => r.data);

/** POST /api/v1/product/{id}/calc — сколько купить под размеры. */
export const calcProduct = (id: number, body: ProductCalcRequest, signal?: AbortSignal) =>
    post<ProductCalc>(`/api/v1/product/${id}/calc`, body, signal);

export const matchedProducts = (params: { q?: string; work_type?: string; max_confidence?: number; page?: number; per_page?: number }, signal?: AbortSignal) =>
    request<MatchedList>("/api/v1/match/products" + query(params), { signal });

export const updateMatch = (id: number, work_type?: string) =>
    request<MatchedProduct>(`/api/v1/match/products/${id}`, { method: "PATCH", body: JSON.stringify(work_type ? { work_type } : {}) });

/** Массовое подтверждение: по списку id или по фильтру (min_confidence, work_type, q). */
export const confirmMatches = (body: { ids?: number[]; min_confidence?: number; work_type?: string; q?: string }) =>
    post<{ confirmed: number }>("/api/v1/match/confirm", body);

export const getWorkTypes = (signal?: AbortSignal) => request<WorkType[]>("/api/v1/work-types", { signal });

export const getStats = (signal?: AbortSignal) => request<Stats>("/api/v1/stats", { signal });

export const getHealth = (signal?: AbortSignal) => request<Health>("/api/v1/health", { signal });

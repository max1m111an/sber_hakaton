/**
 * Клиент backend-сервиса (FastAPI).
 * В docker-compose запросы идут через nginx (/api/ → fastapi:8080),
 * в режиме `npm run dev` — через proxy из vite.config.ts.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export interface ProductCalcResponse {
    product_id: number;
    sku: string;
    area: number;
    package_area: number;
    quantity_in_package: number;
    packages_needed: number;
    units_needed: number;
    price_per_package: string;
    price_per_m2: string;
    total_cost: string;
    currency: string;
    formula_hint: string;
    detail: Record<string, unknown>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(API_BASE + path, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json() as Promise<T>;
}

/** Проверка доступности backend: схема OpenAPI отдаётся всегда, даже без БД. */
export async function pingApi(signal?: AbortSignal): Promise<boolean> {
    try {
        const res = await fetch(API_BASE + "/openapi.json", { signal });
        return res.ok;
    } catch {
        return false;
    }
}

/** POST /api/v1/product/{id}/calc — расчёт количества товара под площадь. */
export const calcProduct = (productId: number, area: number, signal?: AbortSignal) =>
    request<ProductCalcResponse>(`/api/v1/product/${productId}/calc`, {
        method: "POST",
        body: JSON.stringify({ area }),
        signal,
    });

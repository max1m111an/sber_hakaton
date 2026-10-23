import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { NAV, ROUTES } from "@/configs/RoutesConst.ts";
import { getHealth, isAbort, type Health } from "@/api/client.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";
import { deliveryCost, exportCsv } from "@/lib/estimate.ts";
import { rub } from "@/lib/format.ts";

type ApiStatus = { kind: "checking" } | { kind: "offline" } | { kind: "online"; health: Health };

function statusText(s: ApiStatus): string {
    if (s.kind === "checking") return "проверка…";
    if (s.kind === "offline") return "недоступен";
    const imp = s.health.import;
    if (imp.state === "running") return `импорт каталога: ${(imp.processed ?? 0).toLocaleString("ru-RU")}`;
    if (imp.state === "error") return "ошибка импорта";
    return `онлайн · ${(s.health.products ?? 0).toLocaleString("ru-RU")} товаров`;
}

export default function AppLayout() {
    const { pathname } = useLocation();
    const { update, estimate } = useProject();
    const toast = useToast();
    const [api, setApi] = useState<ApiStatus>({ kind: "checking" });

    const page = NAV.find(n => n.path === pathname) ?? NAV[0];
    const isProject = page.path === ROUTES.MAIN;
    const data = estimate.data;
    const delivery = deliveryCost(data?.materials_cost ?? 0);
    const total = data ? data.total_cost + delivery : 0;
    const importing = api.kind === "online" && api.health.import.state === "running";

    // Статус сервиса; пока идёт импорт каталога — опрашиваем чаще
    useEffect(() => {
        const ctrl = new AbortController();
        let timer = 0;
        const poll = () => {
            getHealth(ctrl.signal)
                .then(health => {
                    setApi({ kind: "online", health });
                    timer = window.setTimeout(poll, health.import.state === "running" ? 3000 : 30000);
                })
                .catch((e: unknown) => {
                    if (isAbort(e)) return;
                    setApi({ kind: "offline" });
                    timer = window.setTimeout(poll, 10000);
                });
        };
        poll();
        return () => { ctrl.abort(); window.clearTimeout(timer); };
    }, []);

    useEffect(() => {
        window.scrollTo({ top: 0, behavior: "instant" });
        document.title = `${page.title} — RepairCalc`;
    }, [page]);

    const toCart = () => {
        if (!data) return;
        const cart = data.items.map(i => ({ t: `${i.name} × ${i.packages_needed}`, sum: i.subtotal }));
        if (delivery) cart.push({ t: "Доставка и подъём", sum: delivery });
        update(s => ({ ...s, cart }));
        toast(`В корзине ${data.items.length} поз. на ${rub(data.materials_cost + delivery)}`);
    };

    const toCsv = () => {
        if (!data) return;
        exportCsv(data, delivery);
        toast("Файл сметы выгружен");
    };

    return (
        <div className="app">
            <aside className="rail">
                <div className="brand"><i></i><span>RepairCalc</span></div>
                <nav>
                    {NAV.map((n, i) => (
                        <NavLink key={n.path} to={n.path} end><b>{i + 1}</b>{n.label}</NavLink>
                    ))}
                </nav>
                <div className="railfoot">
                    Данные каталога: maxidom.ru<br />Модель: локальная, Ollama<br />
                    <span className={"status-dot" + (api.kind === "online" && !importing ? " ok" : api.kind === "offline" ? " bad" : "")}></span>
                    API: {statusText(api)}
                </div>
            </aside>

            <div>
                <div className="topbar">
                    <div><h1>{page.title}</h1><div className="crumb">{page.crumb}</div></div>
                    <div className="spacer"></div>
                    <div className="pricetag">
                        <b className="num">{data ? rub(total) : "—"}</b>
                        <span>{estimate.loading ? "пересчитываем…" : "материалы и работы"}</span>
                    </div>
                    {isProject && <button className="btn g sm" onClick={toCsv} disabled={!data}>Выгрузить CSV</button>}
                    {isProject && <button className="btn sm" onClick={toCart} disabled={!data}>В корзину</button>}
                </div>
                <main>
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

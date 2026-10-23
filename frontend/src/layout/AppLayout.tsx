import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { NAV, ROUTES } from "@/configs/RoutesConst.ts";
import { pingApi } from "@/api/client.ts";
import { useProject } from "@/store/projectContext.ts";
import { useToast } from "@/store/toastContext.ts";
import { exportCsv, sumRoom, totals } from "@/lib/estimate.ts";
import { rub } from "@/lib/format.ts";

type ApiStatus = "checking" | "online" | "offline";

export default function AppLayout() {
    const { pathname } = useLocation();
    const { state, update } = useProject();
    const toast = useToast();
    const [api, setApi] = useState<ApiStatus>("checking");

    const page = NAV.find(n => n.path === pathname) ?? NAV[0];
    const isProject = page.path === ROUTES.MAIN;
    const t = totals(state.rooms, state.lvl, state.tier);

    useEffect(() => {
        const ctrl = new AbortController();
        pingApi(ctrl.signal).then(ok => setApi(ok ? "online" : "offline"));
        return () => ctrl.abort();
    }, []);

    useEffect(() => {
        window.scrollTo({ top: 0, behavior: "instant" });
        document.title = `${page.title} — RepairCalc`;
    }, [page]);

    const toCart = () => {
        const cart = state.rooms.map(r => {
            const s = sumRoom(r, state.lvl, state.tier);
            return { t: r.n + " · материалы и работы", sum: s.m + s.w };
        });
        cart.push({ t: "Доставка и подъём", sum: t.d });
        update(s => ({ ...s, cart }));
        toast("Смета добавлена в корзину: " + rub(t.all));
    };

    const toCsv = () => {
        exportCsv(state.rooms, state.lvl, state.tier);
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
                    <span className={"status-dot" + (api === "online" ? " ok" : api === "offline" ? " bad" : "")}></span>
                    API: {api === "checking" ? "проверка…" : api === "online" ? "онлайн" : "недоступен"}
                </div>
            </aside>

            <div>
                <div className="topbar">
                    <div><h1>{page.title}</h1><div className="crumb">{page.crumb}</div></div>
                    <div className="spacer"></div>
                    <div className="pricetag"><b className="num">{rub(t.all)}</b><span>материалы и работы</span></div>
                    {isProject && <button className="btn g sm" onClick={toCsv}>Выгрузить CSV</button>}
                    {isProject && <button className="btn sm" onClick={toCart}>В корзину</button>}
                </div>
                <main>
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

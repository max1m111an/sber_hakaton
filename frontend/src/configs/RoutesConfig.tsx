import { createBrowserRouter } from "react-router-dom";
import { ROUTES } from "./RoutesConst.ts";
import AppLayout from "@/layout/AppLayout.tsx";
import MainPage from "@/pages/MainPage.tsx";
import CatalogPage from "@/pages/CatalogPage.tsx";
import ProductPage from "@/pages/ProductPage.tsx";
import AdminPage from "@/pages/AdminPage.tsx";
import MetricsPage from "@/pages/MetricsPage.tsx";
import ArchitecturePage from "@/pages/ArchitecturePage.tsx";


export const routesConfig = [
    {
        element: <AppLayout />,
        children: [
            { path: ROUTES.MAIN, element: <MainPage /> },
            { path: ROUTES.CATALOG, element: <CatalogPage /> },
            { path: ROUTES.PRODUCT, element: <ProductPage /> },
            { path: ROUTES.ADMIN, element: <AdminPage /> },
            { path: ROUTES.METRICS, element: <MetricsPage /> },
            { path: ROUTES.ARCHITECTURE, element: <ArchitecturePage /> },
            { path: "*", element: <MainPage /> },
        ],
    },
];

export const router = createBrowserRouter(routesConfig);

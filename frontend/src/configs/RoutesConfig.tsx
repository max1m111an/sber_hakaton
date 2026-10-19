import { createBrowserRouter } from "react-router-dom";
import { ROUTES } from "./RoutesConst.ts";
import MainPage from "@/pages/MainPage.tsx";
import EmptyLayout from "@/layout/EmptyLayout.tsx";


export const routesConfig = [
    {
        element: <EmptyLayout />,
        children: [
            {
                path: ROUTES.MAIN,
                element: <MainPage />,
            },
        ],
    },
];

export const router = createBrowserRouter(routesConfig);

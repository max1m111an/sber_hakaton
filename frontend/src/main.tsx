import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import {RouterProvider} from "react-router-dom";
import {router} from "@/configs/RoutesConfig.tsx";
import ProjectProvider from "@/store/ProjectProvider.tsx";
import ToastProvider from "@/store/ToastProvider.tsx";
import "@/styles/repaircalc.css";

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <ToastProvider>
            <ProjectProvider>
                <RouterProvider router={ router } />
            </ProjectProvider>
        </ToastProvider>
    </StrictMode>,
)

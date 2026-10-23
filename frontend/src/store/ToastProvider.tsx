import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ToastContext } from "./toastContext.ts";

export default function ToastProvider({ children }: { children: ReactNode }) {
    const [text, setText] = useState("");
    const [on, setOn] = useState(false);
    const timer = useRef<number | undefined>(undefined);

    const toast = useCallback((t: string) => {
        setText(t);
        setOn(true);
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setOn(false), 2600);
    }, []);

    useEffect(() => () => window.clearTimeout(timer.current), []);

    return (
        <ToastContext.Provider value={toast}>
            {children}
            <div className={"toast" + (on ? " on" : "")} role="status" aria-live="polite">{text}</div>
        </ToastContext.Provider>
    );
}

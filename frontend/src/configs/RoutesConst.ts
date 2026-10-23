export const ROUTES = {
    MAIN: "/",
    CATALOG: "/catalog",
    PRODUCT: "/product",
    ADMIN: "/admin",
    METRICS: "/metrics",
    ARCHITECTURE: "/architecture",
};

/** Пункты бокового меню: путь, подпись, заголовок и подзаголовок страницы. */
export const NAV = [
    { path: ROUTES.MAIN, label: "Смета ремонта", title: "Смета ремонта", crumb: "Объект, помещения, материалы и работы" },
    { path: ROUTES.CATALOG, label: "Каталог", title: "Каталог", crumb: "Товары maxidom.ru с подбором под помещение" },
    { path: ROUTES.PRODUCT, label: "Карточка товара", title: "Карточка товара", crumb: "Расчёт количества под размеры покупателя" },
    { path: ROUTES.ADMIN, label: "Разметка каталога", title: "Разметка каталога", crumb: "Проверка предложений модели" },
    { path: ROUTES.METRICS, label: "Метрики", title: "Метрики", crumb: "Качество моделей и эффект для бизнеса" },
    { path: ROUTES.ARCHITECTURE, label: "Архитектура", title: "Архитектура", crumb: "Микросервис, API и закрытый контур" },
];

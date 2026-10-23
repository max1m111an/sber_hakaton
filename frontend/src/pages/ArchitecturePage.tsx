/** Эндпоинты: реализованные в apps/backend и запланированные. */
const ENDPOINTS: { m: string; path: string; d: string; plan?: boolean }[] = [
    { m: "POST", path: "/api/v1/calc/general", d: "Общий калькулятор: тип объекта и вариант ремонта → смета и список покупок" },
    { m: "POST", path: "/api/v1/calc/room", d: "Калькулятор комнаты: влажность, назначение, уровень ремонта" },
    { m: "POST", path: "/api/v1/product/{id}/calc", d: "Расчёт количества под размеры на карточке" },
    { m: "POST", path: "/api/v1/match", d: "Тип работ и помещения для товара каталога" },
    { m: "GET", path: "/api/catalog/categories/tree", d: "Дерево категорий каталога" },
    { m: "GET", path: "/api/catalog/products", d: "Товары с фильтрами и пагинацией" },
    { m: "GET", path: "/api/catalog/products/{id}", d: "Полная карточка товара с характеристиками" },
    { m: "POST", path: "/api/v1/explain", d: "Пояснение выбора материалов, RAG + локальная модель", plan: true },
    { m: "POST", path: "/api/v1/parse", d: "Параметры ремонта из текстового запроса", plan: true },
];

const STACK = ["FastAPI", "Docker", "PostgreSQL", "Qdrant", "Redis", "sentence-transformers", "CatBoost", "React"];
const SERVER = ["Core i7-14700K", "RTX 3090, 24 ГБ", "32 ГБ ОЗУ", "NVMe 1 ТБ"];
const MVP_YES = ["Общий калькулятор", "Расчёт на карточке", "Матчинг каталога", "Специфика помещения", "Пояснения RAG", "Админка", "Разбор запроса"];
const MVP_NO = ["Распознавание планов", "Продакшн-нагрузка"];

export default function ArchitecturePage() {
    return (
        <section>
            <div className="card">
                <h2>Как устроен сервис</h2>
                <p className="sub">Stateless-микросервис в Docker, общается по REST/JSON. Каталог и остатки остаются на стороне сайта.</p>
                <div className="flow" style={{ marginTop: 14 }}>
                    <div><b>Клиент</b><p>Виджет калькулятора, карточка товара, админка привязки. Встраивается в Bitrix компонентом или AJAX-вызовом.</p></div>
                    <div><b>API</b><p>REST/JSON, авторизация по ключу, без состояния между запросами.</p></div>
                    <div><b>Сервис</b><p>Движок расхода, матчинг товаров, рекомендации под помещение, пояснения через RAG.</p></div>
                    <div><b>Данные</b><p>Выгрузка каталога, нормы расхода из базы знаний, векторное хранилище эмбеддингов.</p></div>
                </div>
            </div>
            <div className="cols2" style={{ marginTop: 16 }}>
                <div className="card">
                    <h2>Эндпоинты</h2>
                    <p className="sub">Серые — запланированы, ещё не реализованы в backend</p>
                    <div style={{ marginTop: 10 }}>
                        {ENDPOINTS.map(e => (
                            <div className="ep" key={e.path}>
                                <span className={e.plan ? "plan" : ""}>{e.m}</span>
                                <div><code>{e.path}</code><p>{e.d}</p></div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="card">
                    <h2>Стек и контур</h2>
                    <p className="sub">Система работает в закрытом контуре, языковая модель поднята локально через Ollama.</p>
                    <div className="pillrow">{STACK.map(s => <span className="pill" key={s}>{s}</span>)}</div>
                    <label className="lab">Сервер</label>
                    <div className="pillrow">{SERVER.map(s => <span className="pill" key={s}>{s}</span>)}</div>
                    <label className="lab">Объём MVP</label>
                    <div className="pillrow">
                        {MVP_YES.map(s => <span className="pill y" key={s}>{s}</span>)}
                        {MVP_NO.map(s => <span className="pill n" key={s}>{s}</span>)}
                    </div>
                </div>
            </div>
        </section>
    );
}

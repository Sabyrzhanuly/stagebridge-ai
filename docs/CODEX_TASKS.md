# Codex task — AI Query Advisor (пятая AI-функция)

> Прочитай сначала `AGENTS.md` в корне репозитория и соблюдай все guardrails.
> Работай в ветке `feature/ai-query-advisor`. Скоуп — ровно эта задача.

## Цель

Добавить **пятую AI-функцию** — **AI Query Advisor**: для медленного SQL-запроса (из мониторинга, `pg_stat_statements`) ИИ (GPT-5.6) возвращает диагноз и **конкретные рекомендации по оптимизации** — предлагаемые индексы (`CREATE INDEX ...`), варианты переписывания запроса и заметки. Строго **advisory**: ничего не выполняется, только показывается.

Почему так: категория хакатона — **Developer Tools**, а «посоветуй индекс по медленному запросу» — классическая боль разработчика/DBA. Фича изолирована и не трогает критичную логику.

## Границы (повтор ключевого из AGENTS.md)
- Никаких изменений схемы БД, миграций, docker-compose, бэкапов, structure-sync.
- Только новые/точечные правки. Отдельная ветка. i18n во все 3 локали. Проверки перед сдачей.

---

## Шаг 1 — Backend: сервисная функция

Файл: `backend/app/services/ai_service.py`. Добавь новую async-функцию **по образцу существующих** (`diagnostics_analysis`/`backup_risk`):

```python
async def query_advisor(api_key: str, model: str, payload: str) -> dict:
    system = (
        f"Ты — эксперт по производительности PostgreSQL. Отвечай на {_LANG}. "
        "Тебе дают медленный SQL-запрос и (опционально) статистику из pg_stat_statements "
        "и контекст схемы. Верни СТРОГО JSON с полями: "
        "severity ('ok'|'warning'|'critical'), summary (строка — в чём проблема), "
        "problems (массив строк), indexes (массив строк — готовые CREATE INDEX ... предложения), "
        "rewrite (массив строк — как переписать запрос), notes (массив строк — оговорки/риски). "
        "Опирайся только на данные. Индексы — только предложения, не выполняются автоматически."
    )
    return _safe_json(await _chat(api_key, model, system,
        f"Данные запроса (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1100))
```

Ничего в существующих функциях не меняй.

## Шаг 2 — Backend: эндпоинт

Файл: `backend/app/api/ai.py`. Добавь роут по образцу `/ai/diagnostics` (используй существующую модель `PayloadIn` — она уже есть, `{payload: str}`):

```python
@router.post("/query-advisor")
async def ai_query_advisor(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.query_advisor(key, model, body.payload)
```

## Шаг 3 — Backend: модель GPT-5.6

В `backend/app/api/ai.py` (`_config`) и `backend/app/services/ai_service.py` (`_chat`) подними дефолт модели с `gpt-4o-mini` на **`gpt-5.6`** (значение всё равно приходит из настроек/`.env`; ключ пользователь задаёт в UI). Если GPT-5.6 не принимает `response_format`/`temperature`/`max_tokens` в Chat Completions — адаптируй `_chat` аккуратно (например, отправлять `response_format` только для поддерживаемых моделей), **не ломая** 4 существующих вызова. Проверь одним живым вызовом.

## Шаг 4 — Frontend: кнопка в мониторинге

Файл: `frontend/src/views/MonitoringView.vue`. В панели «Медленные запросы» (`snapshot.slow_queries`, колонка `query`) добавь в каждую строку кнопку **«AI: оптимизировать»**, которая раскрывает под таблицей (или в строке-детали) панель `AiInsight` для выбранного запроса.

Используй существующий компонент `frontend/src/components/AiInsight.vue`:
```vue
<AiInsight
  :label="t('queryAdvisor.label')"
  endpoint="/ai/query-advisor"
  :payload="() => ({ payload: JSON.stringify({ query: selectedQuery, stats: selectedStats }) })"
  :sections="[
    { key: 'problems', title: t('queryAdvisor.secProblems') },
    { key: 'indexes',  title: t('queryAdvisor.secIndexes') },
    { key: 'rewrite',  title: t('queryAdvisor.secRewrite') },
    { key: 'notes',    title: t('queryAdvisor.secNotes') },
  ]"
  badge-field="severity"
/>
```
`selectedQuery`/`selectedStats` — из выбранной строки таблицы (заведи `ref`). При выключенном ИИ компонент сам показывает `ai.disabledShort` — ничего доп. не нужно. Стиль кнопки — как у существующих действий в таблице, не ломай раскладку/`responsive-layout="stack"`.

## Шаг 5 — i18n (все три локали)

Добавь namespace `queryAdvisor` в `frontend/src/i18n/locales/{ru,kk,en}.json` (строгий паритет ключей):

| ключ | ru | en |
|------|----|----|
| `queryAdvisor.label` | ИИ: оптимизировать запрос | AI: optimize query |
| `queryAdvisor.action` | Оптимизировать | Optimize |
| `queryAdvisor.secProblems` | Проблемы | Problems |
| `queryAdvisor.secIndexes` | Предлагаемые индексы | Suggested indexes |
| `queryAdvisor.secRewrite` | Как переписать | How to rewrite |
| `queryAdvisor.secNotes` | Оговорки | Caveats |

Казахский (`kk`) — переведи литературно (напр. `queryAdvisor.secProblems` → «Мәселелер», `secIndexes` → «Ұсынылатын индекстер», `secRewrite` → «Қалай қайта жазу», `secNotes` → «Ескертпелер», `label` → «ЖИ: сұранысты оңтайландыру», `action` → «Оңтайландыру»). `badge`-подписи (severity ok/warning/critical) уже есть в namespace `ai.*` — переиспользуются автоматически.

## Шаг 6 — Проверки (обязательно)

1. `cd frontend && npx vue-tsc -b` → 0 ошибок.
2. Паритет локалей ru/kk/en (одинаковое число ключей; все новые `t('queryAdvisor.*')` есть в трёх файлах).
3. `docker compose up -d --build backend frontend` → `docker compose ps` без падений.
4. http://localhost → войти → сервер `Demo PostgreSQL` → Мониторинг → «Медленные запросы» → кнопка **AI: оптимизировать** возвращает карточку с секциями. (Ключ OpenAI с доступом к GPT-5.6 должен быть задан в Настройки → ИИ.)
5. Остальные 4 AI-функции и весь UI работают как раньше; переключение языков РУС/ҚАЗ/ENG не ломается.

## Шаг 7 — README

Добавь в `README.md` короткий честный раздел **«How Codex & GPT-5.6 were used»**: что именно ты (Codex) сделал в этой сессии (эта фича), где применялся GPT-5.6. По факту, без преувеличений.

## Готово, когда
- Фича работает end-to-end, проверки Шага 6 зелёные, ветка `feature/ai-query-advisor` закоммичена, README дополнен. Не делай `git push` и не открывай PR без подтверждения владельца.

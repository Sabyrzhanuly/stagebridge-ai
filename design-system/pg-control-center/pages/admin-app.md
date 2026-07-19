# Page Override: Admin App (все views)

> Перекрывает MASTER.md для внутренних страниц PG Control Center (не login landing).

## Layout

- Shell: `AppLayout.vue` — sidebar + topbar + content + `TaskPanel`
- Sidebar: 240px / collapsed 64px (`--layout-sidebar-width`)
- Topbar: 56px (`--layout-topbar-height`)
- Content: padding `--space-lg`, scroll внутри main, не body

## Паттерн страницы

1. **Page header** — заголовок + краткий subtitle + primary action справа
2. **Filters bar** (опционально) — Select, InputText, Button «Обновить»
3. **Main block** — DataTable или card grid
4. **Empty state** — иконка + текст + CTA, не голая таблица

## PrimeVue mapping (тёмная тема)

| Token MASTER | Проект |
|--------------|--------|
| Primary `#0F172A` | `--dark-nav` / `--p-surface-950` |
| Surface | `--dark-surface` / `--p-surface-800` |
| CTA `#0369A1` | PrimeVue `Button severity="info"` или custom `--p-primary-500` |
| Text | `--p-text-color` |
| Border | `--dark-border` / `--p-surface-600` |

## DataTable

- `stripedRows`, `size="small"` для плотных данных
- Pagination server-side где API поддерживает
- Loading: `:loading="true"` + skeleton для первой загрузки
- Row actions: `Button icon text rounded`, не текст-ссылки без hover

## Dashboard / Monitoring

- KPI cards: 3–4 в ряд на desktop, 1–2 на mobile
- Charts: простые (PrimeVue нет chart — SVG/CSS или placeholder + число)
- Real-time: WebSocket `stores/tasks.ts`, badge «live»

## Login (`LoginView.vue`)

- Centered card, max-width 420px
- Logo + «PG Control Center»
- Без sidebar; light или dark — согласовано с `.app-dark`

# Page Override: Scenarios (Сценарии восстановления)

> Перекрывает MASTER.md и admin-app.md для `ScenariosView.vue`.

## Layout

1. **PageHeader** — title + subtitle + «Обновить» (outlined) + «Новый сценарий» (primary)
2. **KPI strip** — 3× `StatCard`: всего / активных / выполняется сейчас
3. **card-panel** — filters bar + grid карточек сценариев
4. **Empty state** — `EmptyState` + CTA (не пустой grid)

## Карточка сценария

| Блок | Правило |
|------|---------|
| Header | Название + `Tag` статуса; toolbar: ToggleSwitch + icon buttons text rounded |
| Route | 3 колонки: источник → действие (`Tag`) → цель; без rainbow-цветов серверов |
| Facts | `dl` 3 колонки: расписание / последний запуск / исключения |
| Исключения | Счётчик + expand list (max-height scroll), не chip-облако |
| Footer | `margin-top: auto` — Запустить (outlined) + История (text) |

Surfaces: `--dark-surface`, `--dark-border`, `--dark-bg`. Monospace: `--font-mono`, cron/exclude → `.code-chip`.

**Scoped Vue:** dark overrides только через `html.app-dark .class` в `frontend/src/styles/scenarios.css` — `:global(.app-dark) .class` в scoped Vue **ломается** (стили попадают на `<html>`).

## Модалки

- Create/edit: max-width 560px, секции uppercase muted labels
- History: `DataTable` + `app-data-table` + `responsive-layout="stack"` + `#empty` EmptyState

## Anti-patterns (эта страница)

- ❌ Inline hex (`#ef4444`, `#f59e0b`) — только `--color-danger`, `--color-warning`
- ❌ Layout-shifting hover (`transform: translateY`)
- ❌ Все excluded tables на карточке без collapse

## Checklist (ui-ux-pro-max)

- [ ] Font Awesome icons, не emoji
- [ ] Transitions 150–300ms (`--transition-ui`)
- [ ] Responsive 375 / 768 / 1024
- [ ] `prefers-reduced-motion` для pulse-анимаций
- [ ] После изменений: `docker compose up -d --build frontend`

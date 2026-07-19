from __future__ import annotations

from typing import Any

SUPPORTED_LOCALES = {"kk", "ru", "en"}
DEFAULT_LOCALE = "ru"
FALLBACK_LOCALE = "en"

LANGUAGE_NAMES = {"kk": "Kazakh", "ru": "Russian", "en": "English"}

CATEGORY_LABELS = {
    "en": {
        "table_removed": "Table removed", "table_added": "Table added", "column_removed": "Column removed", "column_added": "Column added",
        "nullable_to_not_null": "Nullable to NOT NULL", "nullability_change": "Nullability change", "incompatible_type_change": "Incompatible type change",
        "text_to_integer": "Text to integer", "type_change": "Type change", "varchar_length_reduction": "Text length reduction", "default_change": "Default value change",
        "enum_value_mismatch": "Enum value mismatch", "primary_key_added": "Primary key added", "primary_key_removed": "Primary key removed", "primary_key_changed": "Primary key changed",
        "new_foreign_key_orphans": "New foreign key with orphan rows", "foreign_key_removed": "Foreign key removed", "foreign_key_changed": "Foreign key changed",
        "new_unique_constraint_duplicates": "New unique constraint with duplicates", "unique_constraint_removed": "Unique constraint removed", "unique_constraint_changed": "Unique constraint changed",
        "check_constraint_added": "Check constraint added", "check_constraint_removed": "Check constraint removed", "check_constraint_changed": "Check constraint changed",
        "index_added": "Index added", "index_removed": "Index removed", "index_changed": "Index changed", "enum_added": "Enum added", "enum_removed": "Enum removed",
        "enum_changed": "Enum changed", "sequence_added": "Sequence added", "sequence_removed": "Sequence removed", "sequence_changed": "Sequence changed",
        "probable_column_rename": "Probable column rename",
        "routine_added": "Function/procedure added", "routine_removed": "Function/procedure removed", "routine_changed": "Function/procedure changed",
        "view_added": "View added", "view_removed": "View removed", "view_changed": "View changed",
        "trigger_added": "Trigger added", "trigger_removed": "Trigger removed", "trigger_changed": "Trigger changed",
    },
    "ru": {
        "table_removed": "Таблица удалена", "table_added": "Таблица добавлена", "column_removed": "Столбец удален", "column_added": "Столбец добавлен",
        "nullable_to_not_null": "NULL заменяется на NOT NULL", "nullability_change": "Изменение допустимости NULL", "incompatible_type_change": "Несовместимое изменение типа",
        "text_to_integer": "Текст преобразуется в целое число", "type_change": "Изменение типа", "varchar_length_reduction": "Уменьшение длины текста", "default_change": "Изменение значения по умолчанию",
        "enum_value_mismatch": "Несовпадение значений enum", "primary_key_added": "Добавлен первичный ключ", "primary_key_removed": "Удален первичный ключ", "primary_key_changed": "Изменен первичный ключ",
        "new_foreign_key_orphans": "Новый внешний ключ и потерянные ссылки", "foreign_key_removed": "Удален внешний ключ", "foreign_key_changed": "Изменен внешний ключ",
        "new_unique_constraint_duplicates": "Новое ограничение уникальности и дубликаты", "unique_constraint_removed": "Удалено ограничение уникальности", "unique_constraint_changed": "Изменено ограничение уникальности",
        "check_constraint_added": "Добавлено проверочное ограничение", "check_constraint_removed": "Удалено проверочное ограничение", "check_constraint_changed": "Изменено проверочное ограничение",
        "index_added": "Индекс добавлен", "index_removed": "Индекс удален", "index_changed": "Индекс изменен", "enum_added": "Enum добавлен", "enum_removed": "Enum удален",
        "enum_changed": "Enum изменен", "sequence_added": "Последовательность добавлена", "sequence_removed": "Последовательность удалена", "sequence_changed": "Последовательность изменена",
        "probable_column_rename": "Вероятное переименование столбца",
        "routine_added": "Функция/процедура добавлена", "routine_removed": "Функция/процедура удалена", "routine_changed": "Функция/процедура изменена",
        "view_added": "Представление добавлено", "view_removed": "Представление удалено", "view_changed": "Представление изменено",
        "trigger_added": "Триггер добавлен", "trigger_removed": "Триггер удалён", "trigger_changed": "Триггер изменён",
    },
    "kk": {
        "table_removed": "Кесте жойылған", "table_added": "Кесте қосылған", "column_removed": "Баған жойылған", "column_added": "Баған қосылған",
        "nullable_to_not_null": "NULL мәнінен NOT NULL мәніне ауысу", "nullability_change": "NULL рұқсатын өзгерту", "incompatible_type_change": "Үйлесімсіз түр өзгерісі",
        "text_to_integer": "Мәтінді бүтін санға түрлендіру", "type_change": "Түр өзгерісі", "varchar_length_reduction": "Мәтін ұзындығын қысқарту", "default_change": "Әдепкі мәнді өзгерту",
        "enum_value_mismatch": "Enum мәндерінің сәйкессіздігі", "primary_key_added": "Бастапқы кілт қосылған", "primary_key_removed": "Бастапқы кілт жойылған", "primary_key_changed": "Бастапқы кілт өзгерген",
        "new_foreign_key_orphans": "Жаңа сыртқы кілт және байланыссыз жолдар", "foreign_key_removed": "Сыртқы кілт жойылған", "foreign_key_changed": "Сыртқы кілт өзгерген",
        "new_unique_constraint_duplicates": "Жаңа бірегейлік шектеуі және телнұсқалар", "unique_constraint_removed": "Бірегейлік шектеуі жойылған", "unique_constraint_changed": "Бірегейлік шектеуі өзгерген",
        "check_constraint_added": "Тексеру шектеуі қосылған", "check_constraint_removed": "Тексеру шектеуі жойылған", "check_constraint_changed": "Тексеру шектеуі өзгерген",
        "index_added": "Индекс қосылған", "index_removed": "Индекс жойылған", "index_changed": "Индекс өзгерген", "enum_added": "Enum қосылған", "enum_removed": "Enum жойылған",
        "enum_changed": "Enum өзгерген", "sequence_added": "Тізбек қосылған", "sequence_removed": "Тізбек жойылған", "sequence_changed": "Тізбек өзгерген",
        "probable_column_rename": "Бағанның ықтимал қайта аталуы",
        "routine_added": "Функция/процедура қосылған", "routine_removed": "Функция/процедура жойылған", "routine_changed": "Функция/процедура өзгерген",
        "view_added": "Көрініс қосылған", "view_removed": "Көрініс жойылған", "view_changed": "Көрініс өзгерген",
        "trigger_added": "Триггер қосылған", "trigger_removed": "Триггер жойылған", "trigger_changed": "Триггер өзгерген",
    },
}

CONFLICT_EXPLANATIONS = {
    "en": {
        "nullable_to_not_null": "Production NULL values cannot satisfy the development NOT NULL constraint.",
        "incompatible_type_change": "Some production values cannot be converted safely to the development data type.",
        "text_to_integer": "Non-numeric production text cannot be converted to an integer.",
        "enum_value_mismatch": "Production uses enum values that are absent from the development enum.",
        "new_foreign_key_orphans": "Orphan production rows do not reference an existing parent key.",
        "new_unique_constraint_duplicates": "Duplicate production values cannot satisfy the new unique constraint.",
        "probable_column_rename": "Source values need an explicit mapping to the probable renamed column.",
        "varchar_length_reduction": "Production values longer than the development limit will not fit.",
    },
    "ru": {
        "nullable_to_not_null": "Значения NULL в продакшене не соответствуют ограничению NOT NULL из схемы разработки.",
        "incompatible_type_change": "Некоторые значения из продакшена нельзя безопасно преобразовать в тип схемы разработки.",
        "text_to_integer": "Нечисловой текст из продакшена нельзя преобразовать в целое число.",
        "enum_value_mismatch": "В продакшене используются значения enum, которых нет в схеме разработки.",
        "new_foreign_key_orphans": "Некоторые строки продакшена не ссылаются на существующий родительский ключ.",
        "new_unique_constraint_duplicates": "Дубликаты в продакшене не соответствуют новому ограничению уникальности.",
        "probable_column_rename": "Исходные значения нужно явно сопоставить с вероятно переименованным столбцом.",
        "varchar_length_reduction": "Значения длиннее нового ограничения не поместятся в столбец.",
    },
    "kk": {
        "nullable_to_not_null": "Өндірістегі NULL мәндері әзірлеу схемасының NOT NULL шектеуіне сай келмейді.",
        "incompatible_type_change": "Кейбір өндірістік мәндерді әзірлеу схемасының дерек түріне қауіпсіз түрлендіру мүмкін емес.",
        "text_to_integer": "Өндірістегі сан емес мәтінді бүтін санға түрлендіру мүмкін емес.",
        "enum_value_mismatch": "Өндірісте әзірлеу схемасында жоқ enum мәндері қолданылады.",
        "new_foreign_key_orphans": "Кейбір өндірістік жолдар қолданыстағы негізгі кілтке сілтеме жасамайды.",
        "new_unique_constraint_duplicates": "Өндірістегі телнұсқалар жаңа бірегейлік шектеуіне сай келмейді.",
        "probable_column_rename": "Бастапқы мәндерді ықтимал қайта аталған бағанға анық сәйкестендіру қажет.",
        "varchar_length_reduction": "Жаңа шектен ұзын мәндер бағанға сыймайды.",
    },
}

GENERIC_STRATEGIES = {
    "en": ["Review affected production rows", "Apply an explicitly approved mapping", "Validate the result in an isolated environment"],
    "ru": ["Проверить затронутые строки продакшена", "Применить явно одобренное сопоставление", "Проверить результат в изолированной среде"],
    "kk": ["Қамтылған өндірістік жолдарды тексеру", "Нақты мақұлданған сәйкестендіруді қолдану", "Нәтижені оқшауланған ортада тексеру"],
}

MESSAGES: dict[str, dict[str, Any]] = {
    "en": {
        "connections.credential_storage": "Passwords are stored unencrypted at rest for this hackathon MVP and are never returned by the API.",
        "connections.connected": "Connected to {database} as {user} (read-only).",
        "connections.demo_seeded": "Built-in seeded database",
        "connections.labels.prod": "Production demo", "connections.labels.dev": "Development demo",
        "connections.labels.stage": "Staging demo", "connections.labels.dryrun": "Dry run demo",
        "errors.target_required": "target is required.", "errors.invalid_mode": "mode must be demo or live.",
        "errors.production_role": "The production profile must have the production role.",
        "errors.development_role": "The development profile must have the development role.",
        "errors.profiles_different": "Production and development profiles must be different.",
        "errors.analysis_incomplete": "Analysis must complete before AI planning.",
        "errors.actions_list": "actions must be a list.", "errors.action_object": "Each action update must be an object.",
        "errors.parameters_object": "parameters must be an object.", "errors.unsupported_action": "Unsupported action type: {action_type}.",
        "errors.demo_dryrun_only": "Dry run is available only for demo data. Live database analyses are report-only.",
        "errors.string_list": "{field} must be a list of strings.", "errors.non_empty_list": "{field} must contain at least one value.",
        "errors.unsupported_demo_target": "Unsupported demo target.",
        "errors.staging_role": "The migration target must be a staging profile.",
        "errors.target_conflict": "The migration target cannot be the production or development source.",
        "errors.confirm_required": "Explicit confirmation is required to write to the staging database.",
        "validation.select_schema": "Select at least one schema.",
        "validation.timeout": "Statement timeout must be between 100 and 120000 milliseconds.",
        "validation.password": "Password is required.", "validation.required": "This field is required.",
        "validation.invalid": "Enter a valid value.", "validation.blank": "This field may not be blank.", "validation.unique": "This value is already in use.",
        "errors.not_found": "The requested resource was not found.", "errors.bad_request": "The request is invalid.",
        "analysis.demo_title": "Demo schema compatibility analysis", "analysis.failed": "Analysis failed",
        "analysis.complete": "Analysis complete", "analysis.demo_label": "DEMO DATA", "analysis.live_label": "LIVE DATABASE ANALYSIS",
        "analysis.demo_limitation": "Demo dry run is isolated to stagebridge_dryrun.",
        "analysis.live_limitation": "Live database analysis is read-only. SQL previews are advisory and are never executed.",
        "ai.model_required": "OPENAI_MODEL must be set when OPENAI_API_KEY is present.",
        "ai.empty_response": "OpenAI response did not include structured output text.",
        "ai.system": "You are a database migration reviewer. Return only a structured remediation plan. Do not return executable SQL. Recommend only the allowed action types. Write every user-facing explanation in {language}.",
        "ai.explanation": "The remediation plan is advisory. Live database SQL is never executed; use the findings and previews for a reviewed migration.",
        "ai.rationale.backfill_null_with_default": "Production NULL values must be handled before the development NOT NULL constraint can be satisfied.",
        "ai.rationale.normalize_numeric_values": "Only values proven compatible by a bounded preflight should be converted.",
        "ai.rationale.map_enum_values": "Production enum values removed from development require an explicit reviewed mapping.",
        "ai.rationale.remove_or_remap_orphans": "Orphaned source rows cannot satisfy the development foreign key.",
        "ai.rationale.deduplicate_values": "Duplicate production values cannot satisfy the development unique constraint.",
        "ai.rationale.map_renamed_column": "The column pair is a rename candidate and needs an explicit reviewed mapping.",
        "ai.rationale.reject_refresh": "This breaking structural change has no automatic remediation in the MVP.",
        "ai.rationale.validate_constraint": "Run post-load validation checks before marking the dry run passed.",
        "ai.alternatives": ["Reject the refresh until production data is corrected.", "Postpone selected development constraints for this refresh window.", "Create a manually reviewed exception file for rejected rows."],
        "ai.checks": ["Re-run all supported preflight checks after remediation.", "Review findings without automated preflight manually.", "Apply changes through the normal reviewed migration process."],
        "ai.rollback": ["The dry-run database can be reset without affecting production.", "Rejected rows are retained in dry-run audit tables.", "No production writes are performed."],
        "dryrun.live_blocked": "Live database analyses cannot enter the demo dry-run executor.",
        "dryrun.missing_actions": "Missing approved actions: {actions}.",
        "dryrun.copy_source": "Loaded production rows into dry-run raw tables.",
        "dryrun.reset": "Dropped and recreated the public schema in stagebridge_dryrun.",
        "dryrun.apply_schema": "Applied the development schema and raw loading tables.",
        "dryrun.load_users": "Loaded users with phone backfill and email deduplication.",
        "dryrun.map_customer": "Mapped customer.full_name into customer.display_name.",
        "dryrun.invalid_enum": "The enum mapping target is not part of the development enum.",
        "dryrun.load_orders": "Loaded valid orders and retained rejected rows for audit.",
        "dryrun.validation_failures": "Validation failures: {count}.",
        "dryrun.passed": "Dry run passed", "dryrun.failed": "Dry run failed",
        "dryrun.limitation": "The dry run is scoped to the seeded demo schemas and controlled action templates.",
        "migration.not_completed": "Analysis must complete before a migration run.",
        "migration.plan_required": "Generate the AI plan before running a migration.",
        "migration.reset": "Reset the isolated target schema.",
        "migration.schema_applied": "Rebuilt the development schema in the isolated target.",
        "migration.loaded": "Loaded {schema}.{table}: {moved} moved, {rejected} rejected.",
        "migration.validation": "Post-load constraint validation failures: {failures}.",
        "migration.verify": "Row-count verification mismatches (source vs target): {mismatches}.",
        "migration.objects": "Applied {count} routines/views/triggers ({failures} failed).",
        "migration.isolated_target": "isolated target database",
        "migration.constraint_failed": "Constraint {name} rejected the loaded data: {error}",
        "migration.committed": "Committed the migration to the isolated target database.",
        "migration.rolled_back": "Rolled back the migration; the target is unchanged.",
        "migration.failed": "Migration failed",
        "migration.passed": "Migration passed",
        "migration.limitation": "The migration writes only to the isolated target database. Production and development stay read-only.",
        "report.title": "StageBridge AI analysis #{id}", "report.mode": "Mode", "report.status": "Status", "report.schemas": "Schemas",
        "report.sources": "Sources", "report.production": "Production", "report.development": "Development", "report.read_only": "read-only",
        "report.summary": "Summary", "report.schema_changes": "Schema changes", "report.breaking_changes": "Breaking changes",
        "report.blocking_conflicts": "Blocking conflicts", "report.affected_rows": "Affected production rows", "report.findings": "Findings",
        "report.severity": "Severity", "report.breaking": "Breaking", "report.preflight": "Preflight", "report.why": "Why",
        "report.sample_values": "Sample values", "report.remediation": "Remediation explanation", "report.safety": "Safety",
        "report.safety_text": "This report was generated using read-only production and development sessions. SQL previews are advisory and were not executed against live databases.",
        "report.structural": "Structural schema difference.", "report.no_sql": "-- No SQL preview available", "report.yes": "yes", "report.no": "no",
        "status.Safe": "Safe", "status.Warning": "Warning", "status.Blocking": "Blocking", "status.created": "Created",
        "status.running": "Running", "status.completed": "Completed", "status.failed": "Failed", "status.not_started": "Not started",
        "status.passed": "Passed", "status.checked": "Checked", "status.not_run": "Not run", "status.unsupported_preflight": "Manual review",
    },
    "ru": {
        "connections.credential_storage": "Пароли хранятся в незашифрованном виде для этого MVP и никогда не возвращаются API.",
        "connections.connected": "Подключено к {database} от имени {user} (только чтение).", "connections.demo_seeded": "Встроенная база с тестовыми данными",
        "connections.labels.prod": "Демо продакшена", "connections.labels.dev": "Демо разработки", "connections.labels.stage": "Демо стенда", "connections.labels.dryrun": "Демо пробного запуска",
        "errors.target_required": "Необходимо указать target.", "errors.invalid_mode": "mode должен быть demo или live.",
        "errors.production_role": "Профиль продакшена должен иметь роль production.", "errors.development_role": "Профиль разработки должен иметь роль development.",
        "errors.profiles_different": "Профили продакшена и разработки должны различаться.", "errors.analysis_incomplete": "Перед созданием ИИ-плана анализ должен завершиться.",
        "errors.actions_list": "Поле actions должно быть списком.", "errors.action_object": "Каждое обновление действия должно быть объектом.",
        "errors.parameters_object": "Поле parameters должно быть объектом.", "errors.unsupported_action": "Неподдерживаемый тип действия: {action_type}.",
        "errors.demo_dryrun_only": "Пробный запуск доступен только для демо-данных. Анализы рабочих баз предназначены только для отчетов.",
        "errors.string_list": "Поле {field} должно быть списком строк.", "errors.non_empty_list": "Поле {field} должно содержать хотя бы одно значение.",
        "errors.unsupported_demo_target": "Неподдерживаемая демо-цель.", "validation.select_schema": "Выберите хотя бы одну схему.",
        "errors.staging_role": "Целью миграции должен быть staging-профиль.",
        "errors.target_conflict": "Цель миграции не может совпадать с источником (продакшен или разработка).",
        "errors.confirm_required": "Для записи в staging-базу требуется явное подтверждение.",
        "validation.timeout": "Тайм-аут запроса должен быть от 100 до 120000 миллисекунд.", "validation.password": "Укажите пароль.", "validation.required": "Обязательное поле.",
        "validation.invalid": "Введите корректное значение.", "validation.blank": "Поле не может быть пустым.", "validation.unique": "Это значение уже используется.",
        "errors.not_found": "Запрошенный ресурс не найден.", "errors.bad_request": "Некорректный запрос.",
        "analysis.demo_title": "Демо-анализ совместимости схем", "analysis.failed": "Ошибка анализа", "analysis.complete": "Анализ завершен",
        "analysis.demo_label": "ДЕМО-ДАННЫЕ", "analysis.live_label": "АНАЛИЗ РАБОЧЕЙ БАЗЫ", "analysis.demo_limitation": "Пробный запуск изолирован в stagebridge_dryrun.",
        "analysis.live_limitation": "Анализ рабочей базы выполняется только для чтения. SQL-примеры носят рекомендательный характер и не выполняются.",
        "ai.model_required": "При наличии OPENAI_API_KEY необходимо задать OPENAI_MODEL.", "ai.empty_response": "Ответ OpenAI не содержит структурированного текста.",
        "ai.system": "Вы проверяете миграцию базы данных. Верните только структурированный план исправления. Не возвращайте исполняемый SQL. Рекомендуйте только разрешенные типы действий. Все пользовательские пояснения пишите на языке: {language}.",
        "ai.explanation": "План исправления носит рекомендательный характер. SQL никогда не выполняется в рабочих базах; используйте результаты и примеры для проверенной миграции.",
        "ai.rationale.backfill_null_with_default": "Значения NULL нужно обработать до применения ограничения NOT NULL.",
        "ai.rationale.normalize_numeric_values": "Преобразовывать можно только значения, совместимость которых подтверждена ограниченной проверкой.",
        "ai.rationale.map_enum_values": "Удаленные значения enum требуют явного проверенного сопоставления.",
        "ai.rationale.remove_or_remap_orphans": "Строки без родительской записи не соответствуют внешнему ключу схемы разработки.",
        "ai.rationale.deduplicate_values": "Дубликаты в продакшене не соответствуют ограничению уникальности схемы разработки.",
        "ai.rationale.map_renamed_column": "Вероятное переименование требует явного проверенного сопоставления источника и цели.",
        "ai.rationale.reject_refresh": "Для этого критического структурного изменения нет автоматического исправления.",
        "ai.rationale.validate_constraint": "Выполните проверки после загрузки перед успешным завершением пробного запуска.",
        "ai.alternatives": ["Отклонить обновление до исправления данных продакшена.", "Отложить выбранные ограничения разработки для текущего окна обновления.", "Создать вручную проверенный файл исключений для отклоненных строк."],
        "ai.checks": ["Повторить все поддерживаемые предварительные проверки после исправления.", "Проверить вручную результаты без автоматической проверки.", "Применить изменения через обычный процесс проверенной миграции."],
        "ai.rollback": ["Тестовую базу можно сбросить без влияния на продакшен.", "Отклоненные строки сохраняются в тестовых таблицах аудита.", "Запись в продакшен не выполняется."],
        "dryrun.live_blocked": "Анализ рабочей базы нельзя передать исполнителю демо-прогона.", "dryrun.missing_actions": "Не одобрены обязательные действия: {actions}.",
        "dryrun.copy_source": "Строки продакшена загружены в тестовые сырые таблицы.", "dryrun.reset": "Схема public в stagebridge_dryrun удалена и создана заново.",
        "dryrun.apply_schema": "Схема разработки и таблицы сырой загрузки применены.", "dryrun.load_users": "Пользователи загружены с заполнением телефонов и удалением дубликатов email.",
        "dryrun.map_customer": "Поле customer.full_name сопоставлено с customer.display_name.", "dryrun.invalid_enum": "Целевое значение сопоставления отсутствует в enum схемы разработки.",
        "dryrun.load_orders": "Корректные заказы загружены, отклоненные строки сохранены для аудита.", "dryrun.validation_failures": "Ошибок проверки: {count}.",
        "dryrun.passed": "Пробный запуск пройден", "dryrun.failed": "Пробный запуск завершился ошибкой",
        "dryrun.limitation": "Пробный запуск ограничен заполненными демо-схемами и контролируемыми шаблонами действий.",
        "migration.not_completed": "Перед накатом анализ должен завершиться.",
        "migration.plan_required": "Перед накатом сформируйте ИИ-план.",
        "migration.reset": "Изолированная целевая схема сброшена.",
        "migration.schema_applied": "Схема разработки пересоздана в изолированной целевой базе.",
        "migration.loaded": "Загружено {schema}.{table}: перенесено {moved}, отклонено {rejected}.",
        "migration.validation": "Провалов проверки ограничений после загрузки: {failures}.",
        "migration.verify": "Расхождений сверки строк (источник vs цель): {mismatches}.",
        "migration.objects": "Применено функций/представлений/триггеров: {count} (с ошибками: {failures}).",
        "migration.isolated_target": "изолированная целевая база",
        "migration.constraint_failed": "Ограничение {name} отклонило загруженные данные: {error}",
        "migration.committed": "Накат зафиксирован в изолированной целевой базе.",
        "migration.rolled_back": "Накат откачен; целевая база не изменена.",
        "migration.failed": "Накат завершился ошибкой",
        "migration.passed": "Накат выполнен",
        "migration.limitation": "Накат пишет только в изолированную целевую базу. Продакшен и разработка остаются только для чтения.",
        "report.title": "Анализ StageBridge AI №{id}", "report.mode": "Режим", "report.status": "Статус", "report.schemas": "Схемы", "report.sources": "Источники",
        "report.production": "Продакшен", "report.development": "Разработка", "report.read_only": "только чтение", "report.summary": "Сводка",
        "report.schema_changes": "Изменения схемы", "report.breaking_changes": "Критические изменения", "report.blocking_conflicts": "Блокирующие конфликты",
        "report.affected_rows": "Затронутые строки продакшена", "report.findings": "Результаты", "report.severity": "Серьезность", "report.breaking": "Критическое",
        "report.preflight": "Предварительная проверка", "report.why": "Причина", "report.sample_values": "Примеры значений", "report.remediation": "Пояснение плана исправления",
        "report.safety": "Безопасность", "report.safety_text": "Отчет создан через подключения к продакшену и разработке только для чтения. SQL-примеры носят рекомендательный характер и не выполнялись в рабочих базах.",
        "report.structural": "Структурное различие схем.", "report.no_sql": "-- SQL-пример отсутствует", "report.yes": "да", "report.no": "нет",
        "status.Safe": "Безопасно", "status.Warning": "Предупреждение", "status.Blocking": "Блокирует", "status.created": "Создан", "status.running": "Выполняется",
        "status.completed": "Завершен", "status.failed": "Ошибка", "status.not_started": "Не начат", "status.passed": "Пройдено", "status.checked": "Проверено",
        "status.not_run": "Не запускалось", "status.unsupported_preflight": "Ручная проверка",
    },
    "kk": {
        "connections.credential_storage": "Осы MVP үшін құпиясөздер шифрланбай сақталады және API арқылы ешқашан қайтарылмайды.",
        "connections.connected": "{database} дерекқорына {user} атынан қосылды (тек оқу).", "connections.demo_seeded": "Дайын сынақ деректері бар кірістірілген дерекқор",
        "connections.labels.prod": "Өндіріс демосы", "connections.labels.dev": "Әзірлеу демосы", "connections.labels.stage": "Сынақ ортасының демосы", "connections.labels.dryrun": "Сынақ іске қосуының демосы",
        "errors.target_required": "target мәнін көрсету қажет.", "errors.invalid_mode": "mode мәні demo немесе live болуы керек.",
        "errors.production_role": "Өндіріс профилінің рөлі production болуы керек.", "errors.development_role": "Әзірлеу профилінің рөлі development болуы керек.",
        "errors.profiles_different": "Өндіріс және әзірлеу профильдері әртүрлі болуы керек.", "errors.analysis_incomplete": "ЖИ жоспарын құру алдында талдау аяқталуы керек.",
        "errors.actions_list": "actions өрісі тізім болуы керек.", "errors.action_object": "Әр әрекет жаңартуы нысан болуы керек.",
        "errors.parameters_object": "parameters өрісі нысан болуы керек.", "errors.unsupported_action": "Қолдау көрсетілмейтін әрекет түрі: {action_type}.",
        "errors.demo_dryrun_only": "Сынақ іске қосуы тек демо деректер үшін қолжетімді. Нақты дерекқор талдаулары тек есеп беруге арналған.",
        "errors.string_list": "{field} өрісі жолдар тізімі болуы керек.", "errors.non_empty_list": "{field} өрісінде кемінде бір мән болуы керек.",
        "errors.unsupported_demo_target": "Қолдау көрсетілмейтін демо мақсат.", "validation.select_schema": "Кемінде бір схеманы таңдаңыз.",
        "errors.staging_role": "Миграция мақсаты staging-профиль болуы керек.",
        "errors.target_conflict": "Миграция мақсаты қайнар көзбен (өндіріс не әзірлеу) сәйкес келмеуі керек.",
        "errors.confirm_required": "Staging-базаға жазу үшін нақты растау қажет.",
        "validation.timeout": "Сұрау күту уақыты 100-ден 120000 миллисекундқа дейін болуы керек.", "validation.password": "Құпиясөзді енгізіңіз.", "validation.required": "Бұл өріс міндетті.",
        "validation.invalid": "Жарамды мәнді енгізіңіз.", "validation.blank": "Өріс бос болмауы керек.", "validation.unique": "Бұл мән қолданылып жатыр.",
        "errors.not_found": "Сұралған ресурс табылмады.", "errors.bad_request": "Сұрау жарамсыз.",
        "analysis.demo_title": "Схемалар үйлесімділігінің демо талдауы", "analysis.failed": "Талдау қатесі", "analysis.complete": "Талдау аяқталды",
        "analysis.demo_label": "ДЕМО ДЕРЕКТЕР", "analysis.live_label": "НАҚТЫ ДЕРЕКҚОРДЫ ТАЛДАУ", "analysis.demo_limitation": "Сынақ іске қосуы stagebridge_dryrun ішінде оқшауланған.",
        "analysis.live_limitation": "Нақты дерекқорды талдау тек оқуға арналған. SQL үлгілері кеңес ретінде беріліп, орындалмайды.",
        "ai.model_required": "OPENAI_API_KEY бар болса, OPENAI_MODEL мәнін көрсету қажет.", "ai.empty_response": "OpenAI жауабында құрылымдалған мәтін жоқ.",
        "ai.system": "Сіз дерекқор көшіруін тексересіз. Тек құрылымдалған түзету жоспарын қайтарыңыз. Орындалатын SQL қайтармаңыз. Тек рұқсат етілген әрекет түрлерін ұсыныңыз. Барлық пайдаланушы түсіндірмесін мына тілде жазыңыз: {language}.",
        "ai.explanation": "Түзету жоспары кеңес ретінде беріледі. SQL нақты дерекқорларда ешқашан орындалмайды; нәтижелер мен үлгілерді тексерілген көшіру үшін пайдаланыңыз.",
        "ai.rationale.backfill_null_with_default": "NOT NULL шектеуін қолданар алдында өндірістегі NULL мәндерін өңдеу қажет.",
        "ai.rationale.normalize_numeric_values": "Тек шектеулі алдын ала тексеру үйлесімді деп растаған мәндерді түрлендіруге болады.",
        "ai.rationale.map_enum_values": "Жойылған enum мәндері нақты тексерілген сәйкестендіруді қажет етеді.",
        "ai.rationale.remove_or_remap_orphans": "Негізгі жазбасы жоқ жолдар әзірлеу схемасының сыртқы кілтіне сай келмейді.",
        "ai.rationale.deduplicate_values": "Өндірістегі телнұсқалар әзірлеу схемасының бірегейлік шектеуіне сай келмейді.",
        "ai.rationale.map_renamed_column": "Ықтимал қайта атау бастапқы және мақсатты бағандарды анық сәйкестендіруді қажет етеді.",
        "ai.rationale.reject_refresh": "Бұл критикалық құрылымдық өзгерістің автоматты түзетуі жоқ.",
        "ai.rationale.validate_constraint": "Сынақ іске қосуын сәтті деп белгілеу алдында жүктеуден кейінгі тексерулерді орындаңыз.",
        "ai.alternatives": ["Өндірістік деректер түзетілгенше жаңартуды қабылдамау.", "Осы жаңарту кезеңінде таңдалған әзірлеу шектеулерін кейінге қалдыру.", "Қабылданбаған жолдар үшін қолмен тексерілген ерекшелік файлын жасау."],
        "ai.checks": ["Түзетуден кейін барлық қолдау көрсетілетін алдын ала тексерулерді қайталау.", "Автоматты алдын ала тексеруі жоқ нәтижелерді қолмен тексеру.", "Өзгерістерді қалыпты тексерілген көшіру үдерісі арқылы қолдану."],
        "ai.rollback": ["Сынақ дерекқорын өндіріске әсер етпей қалпына келтіруге болады.", "Қабылданбаған жолдар сынақ аудит кестелерінде сақталады.", "Өндірістік дерекқорға жазу орындалмайды."],
        "dryrun.live_blocked": "Нақты дерекқор талдауын демо сынақ орындаушысына жіберуге болмайды.", "dryrun.missing_actions": "Міндетті әрекеттер мақұлданбаған: {actions}.",
        "dryrun.copy_source": "Өндірістік жолдар сынақтың бастапқы кестелеріне жүктелді.", "dryrun.reset": "stagebridge_dryrun ішіндегі public схемасы жойылып, қайта жасалды.",
        "dryrun.apply_schema": "Әзірлеу схемасы мен бастапқы жүктеу кестелері қолданылды.", "dryrun.load_users": "Пайдаланушылар телефондарды толтыру және email телнұсқаларын жою арқылы жүктелді.",
        "dryrun.map_customer": "customer.full_name өрісі customer.display_name өрісімен сәйкестендірілді.", "dryrun.invalid_enum": "Сәйкестендірудің мақсатты мәні әзірлеу enum құрамында жоқ.",
        "dryrun.load_orders": "Жарамды тапсырыстар жүктелді, қабылданбаған жолдар аудит үшін сақталды.", "dryrun.validation_failures": "Тексеру қателері: {count}.",
        "dryrun.passed": "Сынақ іске қосуы сәтті өтті", "dryrun.failed": "Сынақ іске қосуы сәтсіз аяқталды",
        "dryrun.limitation": "Сынақ іске қосуы толтырылған демо схемаларымен және бақыланатын әрекет үлгілерімен шектелген.",
        "migration.not_completed": "Накат алдында талдау аяқталуы керек.",
        "migration.plan_required": "Накат алдында ЖИ жоспарын жасаңыз.",
        "migration.reset": "Оқшауланған мақсатты схема қалпына келтірілді.",
        "migration.schema_applied": "Әзірлеу схемасы оқшауланған мақсатты базада қайта құрылды.",
        "migration.loaded": "{schema}.{table} жүктелді: {moved} көшірілді, {rejected} қабылданбады.",
        "migration.validation": "Жүктеуден кейінгі шектеу тексерулерінің қателері: {failures}.",
        "migration.verify": "Жол санын салыстыру сәйкессіздіктері (қайнар vs мақсат): {mismatches}.",
        "migration.objects": "Қолданылған функциялар/көріністер/триггерлер: {count} (қателермен: {failures}).",
        "migration.isolated_target": "оқшауланған мақсатты база",
        "migration.constraint_failed": "{name} шектеуі жүктелген деректерді қабылдамады: {error}",
        "migration.committed": "Накат оқшауланған мақсатты базаға тіркелді.",
        "migration.rolled_back": "Накат қайтарылды; мақсатты база өзгермеді.",
        "migration.failed": "Накат сәтсіз аяқталды",
        "migration.passed": "Накат орындалды",
        "migration.limitation": "Накат тек оқшауланған мақсатты базаға жазады. Өндіріс пен әзірлеу тек оқуға арналған.",
        "report.title": "StageBridge AI №{id} талдауы", "report.mode": "Режим", "report.status": "Күй", "report.schemas": "Схемалар", "report.sources": "Көздер",
        "report.production": "Өндіріс", "report.development": "Әзірлеу", "report.read_only": "тек оқу", "report.summary": "Жиынтық",
        "report.schema_changes": "Схема өзгерістері", "report.breaking_changes": "Критикалық өзгерістер", "report.blocking_conflicts": "Бұғаттаушы қайшылықтар",
        "report.affected_rows": "Қамтылған өндірістік жолдар", "report.findings": "Нәтижелер", "report.severity": "Маңыздылық", "report.breaking": "Критикалық",
        "report.preflight": "Алдын ала тексеру", "report.why": "Себебі", "report.sample_values": "Мән үлгілері", "report.remediation": "Түзету жоспарының түсіндірмесі",
        "report.safety": "Қауіпсіздік", "report.safety_text": "Есеп өндіріс және әзірлеу дерекқорларына тек оқуға арналған қосылымдар арқылы жасалды. SQL үлгілері кеңес ретінде беріліп, нақты дерекқорларда орындалмады.",
        "report.structural": "Құрылымдық схема айырмашылығы.", "report.no_sql": "-- SQL үлгісі жоқ", "report.yes": "иә", "report.no": "жоқ",
        "status.Safe": "Қауіпсіз", "status.Warning": "Ескерту", "status.Blocking": "Бұғаттайды", "status.created": "Жасалды", "status.running": "Орындалуда",
        "status.completed": "Аяқталды", "status.failed": "Сәтсіз", "status.not_started": "Басталмады", "status.passed": "Сәтті", "status.checked": "Тексерілді",
        "status.not_run": "Іске қосылмады", "status.unsupported_preflight": "Қолмен тексеру",
    },
}


def normalize_locale(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_LOCALE
    code = value.strip().lower().split(",", 1)[0].split(";", 1)[0].split("-", 1)[0]
    return code if code in SUPPORTED_LOCALES else DEFAULT_LOCALE


def request_locale(request) -> str:
    explicit = request.data.get("locale") if hasattr(request, "data") else None
    if not explicit and hasattr(request, "query_params"):
        explicit = request.query_params.get("locale")
    return normalize_locale(explicit or request.headers.get("Accept-Language", ""))


def translate(key: str, locale: str = DEFAULT_LOCALE, **params: Any) -> str:
    normalized = normalize_locale(locale)
    value = MESSAGES.get(normalized, {}).get(key, MESSAGES[FALLBACK_LOCALE].get(key, key))
    if not isinstance(value, str):
        return key
    try:
        return value.format(**params)
    except (KeyError, ValueError):
        return value


def translate_list(key: str, locale: str = DEFAULT_LOCALE) -> list[str]:
    normalized = normalize_locale(locale)
    value = MESSAGES.get(normalized, {}).get(key, MESSAGES[FALLBACK_LOCALE].get(key, []))
    return list(value) if isinstance(value, list) else []


def translate_category(category: str, locale: str = DEFAULT_LOCALE) -> str:
    normalized = normalize_locale(locale)
    return CATEGORY_LABELS.get(normalized, CATEGORY_LABELS[FALLBACK_LOCALE]).get(category, category.replace("_", " "))


def translate_conflict_explanation(category: str, locale: str = DEFAULT_LOCALE) -> str:
    normalized = normalize_locale(locale)
    return CONFLICT_EXPLANATIONS.get(normalized, {}).get(category, translate("report.structural", normalized))


def generic_strategies(locale: str = DEFAULT_LOCALE) -> list[str]:
    normalized = normalize_locale(locale)
    return list(GENERIC_STRATEGIES.get(normalized, GENERIC_STRATEGIES[FALLBACK_LOCALE]))


def translate_status(value: str, locale: str = DEFAULT_LOCALE) -> str:
    return translate(f"status.{value}", locale)

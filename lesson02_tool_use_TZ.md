# Урок 2: Tool use с реальными API — ТЗ

## Контекст для нового чата

Я прохожу учебный план **AI Engineering** через проект **JobScout** — личный AI-агент по поиску работы. Прошёл урок 1, начинаю урок 2.

**Репозиторий:** https://github.com/Creampanda/jobscout

**Что сделано в уроке 1:**
- Парсер вакансий через forced tool use (Anthropic-compatible SDK)
- Pydantic для типизированной схемы (`JobPosting`, `SalaryRange`)
- Двухпровайдерная LLM-обвязка (Anthropic / DeepSeek через единый SDK)
- Per-call traces с токенами/стоимостью/`system_prompt_hash`
- Per-run results.jsonl с версионированием через `RUN_NAME`
- Промпты как `.md` файлы под git
- Eval set из 12 вакансий, ITERATIONS.md с честным логом (4 итерации, одна — реверт)

**Текущая структура:**
```
src/jobscout/
  parsers/job_parser.py          # forced-tool-use extraction
  parsers/types.py               # ParseResult, ParseMetadata
  prompts/job_parser/system.md   # versioned prompt
  schemas.py                     # JobPosting, SalaryRange
  llm.py                         # Anthropic SDK wrapper (Anthropic + DeepSeek)
  pricing.py                     # per-call cost (Decimal)
  config.py                      # .env-driven settings

data/jobs_raw/                   # 12 real job postings (test set)
evals/lesson01_parser/
  run.py
  ground_truth.jsonl
  ITERATIONS.md
  results/<RUN_NAME>/results.jsonl
traces/                          # per-call traces (gitignored)
BACKLOG.md
```

**Стек:** Python 3.12, uv, Anthropic SDK, Pydantic v2, pydantic-settings.

**Открытые вопросы из урока 1 (в BACKLOG):**
5 классов ошибок парсера — stack-bleed, generic categories, internal titles, missed red_flags, name canonicalization. Не решаем сейчас, будем закрывать через автоматические эвалы в уроке 8.

---

# ТЗ урока 2

## Цель

Расширить JobScout: вместо парсинга текста вакансий из `data/jobs_raw/`, агент сам идёт во внешние источники, фильтрует выдачу, и возвращает структурированные `JobPosting` через тот же tool-call паттерн, что и в уроке 1.

Ключевая новая способность — **многошаговый цикл tool use**. В уроке 1 был ровно один tool call (forced для structured output). Сейчас — реальный цикл с несколькими раундами, разными инструментами и решением модели «что звать дальше».

## Что должно работать на выходе

```bash
RUN_NAME=v1_baseline uv run python evals/lesson02_agent/run.py --skills go,kafka,backend
```

- Агент через 3–8 раундов tool use тащит вакансии из Remotive и/или Arbeitnow, опционально дёргает Wikipedia для интересных компаний, и для подходящих вакансий зовёт тот же extractor-инструмент из урока 1, который возвращает `JobPosting`.
- Результаты пишутся в `evals/lesson02_agent/results/<RUN_NAME>/results.jsonl` — по строке на вакансию.
- Каждый tool call логируется в трейс — отдельный JSONL с именем инструмента, аргументами, размером ответа, latency, ошибкой если была.
- Прогон на 3 разных наборах скиллов: например `go,kafka,backend`, `python,llm,backend`, `data,airflow,etl`.

## Структура файлов (что добавляем)

```
src/jobscout/
  agents/                          # НОВОЕ
    __init__.py
    job_finder.py                  # многошаговый цикл tool use
    types.py                       # AgentRun, AgentResult, ToolCallTrace
  tools/                           # НОВОЕ
    __init__.py
    registry.py                    # маппинг name → callable + tool definitions
    remotive.py                    # search_remote_jobs
    arbeitnow.py                   # search_european_jobs
    wikipedia.py                   # get_company_info
    extract_job.py                 # extract_job_posting (обёртка над парсером урока 1)
  prompts/
    job_finder/system.md           # НОВОЕ — системный промпт агента

evals/lesson02_agent/              # НОВОЕ
  run.py                           # CLI runner
  ITERATIONS.md                    # лог итераций по аналогии с уроком 1
  results/<RUN_NAME>/
    results.jsonl                  # по строке на найденный JobPosting
    traces.jsonl                   # по строке на tool call
    summary.json                   # сводка: раунды, токены, $, кол-во найденных
```

## Что переиспользовать из урока 1 как есть

- `llm.py` — двухпровайдерная обвязка, без изменений
- `schemas.py` — `JobPosting`, `SalaryRange` — без изменений
- `pricing.py` — расчёт стоимости каждого вызова
- `parsers/job_parser.py` — обернётся в инструмент `extract_job_posting`, сам парсер не трогаем
- `prompts/job_parser/system.md` — продолжает использоваться внутри extractor-инструмента
- Паттерны: версионирование промптов через `.md` + хеш в трейсе, `<RUN_NAME>` директория, ITERATIONS.md

## Контракты инструментов

### 1. `search_remote_jobs`
```python
def search_remote_jobs(limit: int = 50) -> dict:
    """
    Returns recent remote jobs from Remotive (worldwide, English).
    No server-side filtering — model filters results by relevance.
    """
```
- HTTP: `GET https://remotive.com/api/remote-jobs`
- **Важно:** API закеширован на CDN (Cloudflare, `cf-cache-status: HIT`, age ~24h). Параметры query string (`search`, `category`, `limit`) не доходят до origin — фильтрация только на клиенте/в модели.
- Возвращает модели: `{"count": int, "jobs": [{"id", "title", "company_name", "category", "candidate_required_location", "salary", "url", "tags", "description_snippet"}]}` — **description обрезаем до первых ~500 символов и/или strip-им HTML**, иначе один вызов сожрёт 50K+ токенов
- Сохраняем `url`, чтобы можно было дёрнуть детали отдельно (на будущее — full-fetch инструмент сейчас не делаем)

### 2. `search_european_jobs`
```python
def search_european_jobs(page: int = 1) -> dict:
    """
    Returns European jobs from Arbeitnow (mix of remote/onsite, English+German).
    """
```
- HTTP: `GET https://www.arbeitnow.com/api/job-board-api?page={page}`
- Возвращает: `{"page": int, "count": int, "jobs": [...]}` с тем же урезанием description
- 100 джобов на страницу

### 3. `get_company_info`
```python
def get_company_info(name: str) -> dict:
    """
    Returns brief company description from Wikipedia.
    """
```
- HTTP: `GET https://en.wikipedia.org/api/rest_v1/page/summary/{name}`
- Возвращает: `{"title", "extract", "url"}` или `{"error": "not_found"}` — описание текстом без HTML

### 4. `extract_job_posting`
```python
def extract_job_posting(job_text: str, source_url: str) -> dict:
    """
    Parses a job posting into structured JobPosting.
    Use this for jobs you've decided to keep after filtering.
    """
```
- Внутри вызывает `parsers/job_parser.py` из урока 1
- Возвращает `JobPosting.model_dump()`

## Цикл агента (`agents/job_finder.py`)

Псевдокод:

```python
def run_agent(skills: list[str], max_rounds: int = 8) -> AgentResult:
    messages = [{"role": "user", "content": f"Find relevant jobs for skills: {skills}"}]
    tool_traces = []
    extracted_jobs = []
    
    for round_idx in range(max_rounds):
        response = llm.messages_create(
            system=load_prompt("job_finder/system.md"),
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice={"type": "auto"},
        )
        
        if response.stop_reason == "end_turn":
            break
        
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result, trace = execute_tool(block.name, block.input)
                    tool_traces.append(trace)
                    if block.name == "extract_job_posting" and "error" not in result:
                        extracted_jobs.append(result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                        "is_error": "error" in result,
                    })
            messages.append({"role": "user", "content": tool_results})
    
    return AgentResult(jobs=extracted_jobs, traces=tool_traces, rounds=round_idx+1, ...)
```

Требования:
- **`max_rounds = 8`** как hard limit
- **Bookkeeping стоимости** — суммировать токены и `$` по всем раундам через `pricing.py`
- **`is_error: True`** для tool_result при HTTP-ошибках или невалидных аргументах — не падать, давать модели возможность исправиться
- **Параллельные tool calls** в одном раунде поддерживать (модель может за раз позвать и Remotive, и Arbeitnow) — все исполнить, все результаты собрать в один `user` message

## Системный промпт агента

Файл: `src/jobscout/prompts/job_finder/system.md`. Версионируется как в уроке 1.

Должен содержать:
- роль («ты помогаешь искать релевантные вакансии под скиллы пользователя»)
- описание стратегии (сначала собрать выдачу, потом отфильтровать, потом для интересных — extract; не делать extract для всего подряд, это дорого)
- правило остановки (когда найдено N (например, 3–7) релевантных вакансий — заканчивай)
- явное указание про лимит раундов
- что фильтровать — title и description совпадают со скиллами хотя бы частично, локация подходит, не явный mismatch уровня (для backend-инженера не звать `extract` на вакансии маркетолога)

Версии в `ITERATIONS.md`, формат тот же — change → diff → decision.

## Логирование (трейсы)

`traces.jsonl` — по строке на каждый tool call:

```json
{
  "run_name": "v1_baseline",
  "round_idx": 2,
  "tool_use_id": "toolu_01...",
  "tool_name": "search_remote_jobs",
  "input": {"limit": 50},
  "output_size_bytes": 12453,
  "output_summary": "22 jobs returned",
  "latency_ms": 487,
  "error": null,
  "timestamp": "2026-05-14T..."
}
```

Плюс отдельный `summary.json` на прогон:
```json
{
  "run_name": "v1_baseline",
  "skills": ["go", "kafka", "backend"],
  "rounds_used": 5,
  "tool_calls_total": 8,
  "tool_calls_by_name": {"search_remote_jobs": 1, "search_european_jobs": 1, "extract_job_posting": 4, "get_company_info": 2},
  "jobs_extracted": 4,
  "total_input_tokens": 23410,
  "total_output_tokens": 1820,
  "total_cost_usd": "0.043",
  "stop_reason": "end_turn",
  "system_prompt_hash": "abc123..."
}
```

## Definition of Done

- Прогон на 3 разных наборах скиллов завершается успешно
- В каждом прогоне:
  - модель использует **хотя бы 2 разных** инструмента
  - модель **не зовёт** `extract_job_posting` на >50% от всех найденных вакансий (значит, фильтрация работает)
  - `max_rounds` не достигается (значит, модель умеет завершать сама)
  - все найденные `JobPosting` валидны по схеме
- `summary.json` содержит реальные цифры по токенам и стоимости
- `ITERATIONS.md` начат: минимум v1_baseline + минимум одна итерация с изменением промпта (например, после первого прогона ты найдёшь, что модель тащит слишком много вакансий в extract — поправишь промпт, увидишь diff)
- Update в `BACKLOG.md`: что замечено в этом уроке, но отложено

## Что в BACKLOG (явно НЕ делаем)

- Пагинация Arbeitnow за пределы первой страницы
- Параллельный HTTP fetch на стороне Python (между tool calls внутри одного раунда — sequential ОК)
- Кеширование ответов API
- Дедупликация вакансий (одна и та же может прийти и из Remotive, и из Arbeitnow)
- Запись в БД
- MCP-сервер (это урок 4)
- Эвалы tool selection accuracy («модель позвала правильный тул?») — это урок 8

---

## Справочная информация по API

### Remotive
- Endpoint: `GET https://remotive.com/api/remote-jobs`
- Без ключа, без регистрации
- ToS: ссылаться на Remotive как источник, не отправлять их вакансии в третьи job-сайты (для нашего use case норм — мы ничего не публикуем)
- Лимиты: не чаще 4 раз в день рекомендуется, >2/мин блокируется
- **Подтверждённая проблема:** Cloudflare кеширует ответ ~24h без учёта query string. `search`, `category`, `limit` не влияют. Фильтрация — клиентская.
- Структура ответа:
  ```json
  {
    "0-legal-notice": "...",
    "job-count": 22,
    "jobs": [{
      "id": 123,
      "url": "...",
      "title": "Senior Backend Engineer",
      "company_name": "...",
      "category": "Software Development",
      "job_type": "full_time",
      "publication_date": "2026-02-15T10:23:26",
      "candidate_required_location": "Worldwide",
      "salary": "$80,000 - $120,000",
      "description": "<p>Full HTML description...</p>"
    }]
  }
  ```

### Arbeitnow
- Endpoint: `GET https://www.arbeitnow.com/api/job-board-api`
- Без ключа, без регистрации
- Фокус — Европа/Германия, mix remote/onsite, EN + DE
- 100 джобов на страницу, пагинация через `?page=2`
- Структура ответа:
  ```json
  {
    "data": [{
      "slug": "...",
      "company_name": "...",
      "title": "...",
      "description": "<p>HTML...</p>",
      "remote": false,
      "url": "...",
      "tags": [...],
      "job_types": [...],
      "location": "Dingolfing",
      "created_at": 1778322632
    }]
  }
  ```

### Wikipedia
- Endpoint: `GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}`
- Без ключа
- Возвращает `title`, `extract` (краткое описание), `content_urls.desktop.page`

---

## План работы по этапам

1. **Setup:** создать структуру папок `tools/`, `agents/`, `evals/lesson02_agent/`. Пустые `__init__.py`.
2. **Tools (изолированно):** реализовать 4 инструмента как обычные Python-функции. Тестировать каждый отдельным маленьким скриптом, прежде чем включать в агента. Особенно — обрезку description в job-search инструментах.
3. **Registry:** `tools/registry.py` с tool definitions (name, description, input_schema) и dispatch-функцией `execute_tool(name, input)`.
4. **Системный промпт:** черновик v1 в `prompts/job_finder/system.md`.
5. **Цикл агента:** `agents/job_finder.py` — основной цикл tool use, обработка `stop_reason`, accumulate messages, accumulate cost.
6. **Runner:** `evals/lesson02_agent/run.py` — CLI с `--skills`, пишет results/traces/summary.
7. **v1_baseline прогон** на одном наборе скиллов. Разбор: что звала модель, в каком порядке, где косячила.
8. **v2 итерация промпта** по результатам v1. Снова прогон. ITERATIONS.md.
9. **Финальные прогоны** на 3 наборах скиллов с лучшей версией промпта.
10. **Обновить BACKLOG.md** новыми классами проблем, замеченными в процессе.

---

## Changelog постановки (изменения после первичного ТЗ)

Постановка выше частично пересмотрена в ходе обсуждения. Изменения зафиксированы здесь отдельно, чтобы сохранить историю решений (исходный текст ТЗ не правился). **При расхождении приоритет — за этой секцией.**

### Δ1. Wikipedia / `get_company_info` — убран из урока 2

Инструмент `get_company_info` через Wikipedia REST API исключён из состава инструментов урока 2.

- **Причина:** большинство компаний из Remotive/Arbeitnow (стартапы, агентства, средний бизнес) в Wikipedia отсутствуют. Инструмент почти всегда возвращал бы `not_found` — бесполезен как сигнал и как учебный пример (модель быстро научилась бы его игнорировать).
- **Следствие для состава инструментов:** остаётся три — `search_remote_jobs` (Remotive), `search_european_jobs` (Arbeitnow), `extract_job_posting` (парсер урока 1). Везде в ТЗ выше, где упоминается `get_company_info` (контракты, псевдокод, `tool_calls_by_name` в summary.json), этот инструмент следует игнорировать.
- Поиск адекватной замены для обогащения контекстом о компании (источник с лучшим покрытием) — **вынесен в урок 2.5**.

### Δ2. `read_my_profile` / фильтрация по резюме — вынесено в урок 2.5

Рассматривался инструмент `read_my_profile()` (чтение CV из локального файла, фильтрация вакансий по реальному профилю вместо абстрактных `--skills`).

- **Решение:** не тащить в урок 2. Вход агента остаётся `--skills`. Профиль и фильтрация по резюме — отдельный **урок 2.5**.
- **Причина:** не смешивать два новых концепта (механика многошагового tool use + профиль-driven фильтрация) в одном заходе. Сначала чистая механика на простом входе.

### Δ3. Фильтр языка (только английский) — добавлен в постановку

Arbeitnow возвращает вакансии на немецком и английском, язык в ответе API **не размечен**, серверного параметра по языку нет (официально работают только `visa_sponsorship` и пагинация).

- **Куда кладём правило:** в **системный промпт агента** (`prompts/job_finder/system.md`), НЕ в description инструмента.
  - Description инструмента отвечает на вопрос «что это за инструмент и когда его звать» → туда идёт только *констатация факта*: «Arbeitnow returns jobs in both English and German; language is not labeled».
  - Системный промпт отвечает «как агенту вести себя с тем, что инструменты вернули» → туда идёт *поведенческое правило*: «оставляй только англоязычные вакансии, немецкие отбрасывай до решения про extract».
  - Разделение принципиальное: иначе при росте числа инструментов правила фильтрации расползутся по description'ам всех тулов и потеряют централизованную версионируемость. Системный промпт уже версионируется через ITERATIONS.md.
- **Рекомендация по итерациям:** языковой фильтр — хороший кандидат на v2-итерацию. v1_baseline без правила → в `results.jsonl` всплывут немецкие вакансии → v2 добавляет правило → diff в ITERATIONS.md показывает, что починилось. Это даёт естественный измеримый шаг для лога итераций.
- **Поправка к контракту `search_european_jobs`:** в сигнатуру добавляется опциональный `visa_sponsorship: bool | None = None` (роли со спонсорством визы почти всегда на английском — косвенно снижает долю немецких). Описание инструмента дополняется констатацией про смешанный язык.

### Δ4. Дополнения к Definition of Done

К критериям приёмки добавляется:
- в `results.jsonl` нет вакансий преимущественно на немецком (проверка работы языкового фильтра).

### Δ5. Уточнение про Remotive (подтверждено практикой)

Кеш Cloudflare у Remotive проверен curl-ом: все варианты URL (`search=`, `category=`, `limit=`) возвращают идентичный JSON с одинаковым `age` (~24h, `cf-cache-status: HIT`). Серверная фильтрация у этого API не работает в принципе — только клиентская. Зафиксировано как подтверждённое ограничение, не как открытый вопрос.

### Δ6. Состав инструментов после всех изменений

| Инструмент             | Источник       | Тип / режим фильтрации                         |
| ---------------------- | -------------- | ---------------------------------------------- |
| `search_remote_jobs`   | Remotive       | список, фильтрация только клиентская (кеш CDN) |
| `search_european_jobs` | Arbeitnow      | список, клиентская + опц. `visa_sponsorship`   |
| `extract_job_posting`  | парсер урока 1 | structured extraction                          |

Wikipedia — нет. `read_my_profile` — нет (урок 2.5).
# Morpheus — Plan Unapređenja Code Sistema

> **Status:** Predlog za implementaciju
> **Autor:** Analiza (AI) + vlasnik odobrava
> **Datum:** 17. jul 2026
> **Verzija platforme:** v0.15.4

---

## 1. Diagnoza — gde smo danas

### Jake strane (ne dirati)
- **11 Immutable Laws** su jasni i sprovodljivi — većina timova nema ni jedan dokumentovan zakon.
- **Strogo slojevita arhitektura:** Core → SDK → Themes → Plugins → Apps, jednosmerne zavisnosti.
- **Agentic-first protokoli** (MCP/ACP/UCP, `/llms.txt`, GraphQL descriptions) — diferencijacija na tržištu.
- **Outbox + NATS JetStream** — garantovana dostava eventova, zero-loss.
- **CI/CD kompletan:** ci, cd, accessibility, lighthouse, dependabot.
- **Produkcija živa:** dotbooks.store.

### Slabe tačke (cilj ovog plana)
| # | Problem | Posledica |
|---|---------|-----------|
| 1 | **108 plugini** — širina prerasta bandwidth jednog maintainera | Plugini zastarevaju, kvalitet varira, "duhovi" u codebase-u |
| 2 | **Zakoni se sprovode po volji, ne automatizovano** | Drift: svaki plugin polako narušava slojevitost |
| 3 | **Test pokrivenost nepoznata po pluginu** | Refaktorisanje je kocka; strah od merge-a |
| 4 | **Nema lifecycle politike za plugine** | Niko ne zna koji je plugin "core", koji je eksperiment |
| 5 | **Linda panel postoji ali nije enforcement u CI** | AI-generisane promene ulaze bez panela kad je gužva |
| 6 | **Nema vidljivosti zdravlja u runtime-u** | Outbox lag, plugin failures, query cost — slepi smo |

---

## 2. Principi plana

1. **Automatizuj zakone.** Zakon koji se ne proverava u CI je predlog, ne zakon.
2. **Suzi pre nego što proširiš.** 20 odličnih plugini > 108 prosečnih.
3. **Svaki plugin ima vlasnički list (scorecard).** Zdravlje je merljivo, ne osećaj.
4. **Ne diraj ono što radi.** dotbooks.store je dokaz — core engine je zdrav.

---

## 3. P0 — Automatsko sprovođenje zakona (Architecture Guards)

### 3.1 Import Linter (`tools/lint_imports.py`)
**Cilj:** Blokiraj svaki import koji krši slojevitost — u CI, pre merge-a.

**Pravila:**
- `core/` ne sme da importuje ništa iz `plugins/`, `themes/`, `apps/`.
- `plugins/installed/A/` ne sme da importuje `plugins/installed/B/` (interna).
- `themes/` i `storefront/` ne sme da importuje `models.py` bilo kog plugina (LAW 3).
- `storefront/views` ne sme ORM pozive (LAW 3) — AST provera na `*.objects.filter/get` van services.

**Implementacija:**
```python
# tools/lint_imports.py — AST analiza svih .py fajlova
# Exit code != 0 ako bilo koji import krši matricu dozvoljenih zavisnosti
```
- [ ] Napisati linter (~150 linija, `ast` modul)
- [ ] Dodati u CI kao **blocking** job (fail build na kršenje)
- [ ] Prvi run: izlistati postojeće prekršaje → `docs/ARCHITECTURE_DEBT.md`
- [ ] **Ne blokirati odmah:** 2 nedelje grace period sa `warning` modom, pa `error` mod

**Metrika:** broj import prekršaja: cilj 0 za 30 dana.

### 3.2 Schema Description Gate (LAW 0 enforcement)
**Cilj:** Svaki GraphQL tip/mutacija mora imati `description` (to je agent prompt).

**Implementacija:**
- [ ] CI job koji introspektira schema i failuje ako >2% tipova nema opis
- [ ] `strawberry` linter plugin ili custom introspection skript
- [ ] Auto-generisati izveštaj: `docs/SCHEMA_COVERAGE.md` (nedeljno, cron)

**Metrika:** schema description coverage ≥ 98%.

### 3.3 Money/FSM Guard (LAW 6)
**Cilj:** Blokiraj float za novac i direktne mutacije state-a.

**Implementacija:**
- [ ] AST linter: `float(` ili `Decimal(` u polju sa "price/amount/total" u imenu → error
- [ ] AST linter: `.status =` na modelima sa FSM poljem → error (mora `order.confirm()`)
- [ ] Dodati u isti `lint_imports.py` kao zasebne rule setove

---

## 4. P0 — Test piramida po pluginu

### 4.1 Coverage Gate per Plugin
**Trenutno:** nepoznato. **Cilj:** vidljivo + blokirajuće za tier-1 plugine.

**Implementacija:**
- [ ] `pytest --cov=plugins/installed/<name>` po pluginu u CI matrix jobu
- [ ] `coverage.json` artifact → agregatni report
- [ ] Tier-1 plugini (vidi §5.1): **min 80% line coverage** — fail ispod
- [ ] Tier-2: min 50%, Tier-3 (experimental): bez gate-a ali report

**Metrika:** median coverage tier-1 pluginova ≥ 80% za 60 dana.

### 4.2 Hook Contract Tests
**Cilj:** Ako plugin A puca `ORDER_PAID`, plugin B koji sluša mora imati test koji to simulira.

**Implementacija:**
- [ ] Za svaki hook u `MorpheusEvents`: lista subscriber pluginova (auto-discovery)
- [ ] Generički contract test: fire event → assert subscriber service pozvan sa ispravnim payload-om
- [ ] Template: `plugins/installed/_templates/contract_test.py`

**Metrika:** 100% hook subscribera tier-1 pluginova ima contract test.

### 4.3 Golden-Path E2E
**Cilj:** Jedan test koji prolazi ceo purchase flow: catalog → cart → checkout → payment (mock) → order → fulfillment → email (outbox assert).

**Implementacija:**
- [ ] `tests/e2e/test_golden_path.py` — koristi `internal_graphql()` kao storefront (LAW 3 ga čini živim integration testom)
- [ ] Pokreće se na svaki PR + noćni build sa real PostgreSQL/Redis/NATS (docker-compose)

**Metrika:** golden path zelen na main-u 100% vremena. Ako pukne — release blokiran.

---

## 5. P1 — Plugin lifecycle: od 108 ka održivom portfoliju

### 5.1 Plugin Tier sistem
**Cilj:** Jasno ko je core, ko je eksperiment.

| Tier | Kriterijum | Pravila | Primeri |
|------|-----------|---------|---------|
| **T1 — Core** | dotbooks.store ga koristi u produkciji | 80% coverage, contract tests, import lint clean, review panel obavezan | catalog, checkout, orders, payments, storefront, seo, linda |
| **T2 — Supported** | Radi, testiran, ali nije kritičan | 50% coverage, import lint clean | reviews, wishlist, referrals |
| **T3 — Experimental** | Novi ili polumrtav | Bez gate-a, jasno označen u adminu | ~40 pluginova |

**Implementacija:**
- [ ] `plugins/installed/<name>/plugin.toml` — dodaj `tier = 1|2|3`
- [ ] Registry čita tier i prikazuje u adminu (badge)
- [ ] CI gates primenjuju pravila po tier-u

### 5.2 Plugin Scorecard (`/admin/plugins/health`)
**Cilj:** Jedna stranica: zdravlje svakog plugina na pogled.

**Metrike po pluginu:**
- coverage %, import prekršaji, contract testovi da/ne
- poslednji commit, open TODO/FIXME count
- runtime: hook failure rate, task queue lag, error rate (iz logs/Sentry)

**Implementacija:**
- [ ] Management command `python manage.py plugin_health --json` → artefakt
- [ ] Admin view koji renderuje tabelu sa semaforima 🟢🟡🔴
- [ ] Nedeljni cron: generiše `docs/PLUGIN_HEALTH.md` i commituje

### 5.3 Deprecation politika
- [ ] Plugin bez commita 90 dana + nije tier-1/2 → **auto-predlog za arhivu** (issue sa labelom `deprecation-candidate`)
- [ ] Arhivirani plugini sele u `plugins/archived/` — van build matrice, čitljivi ali mrtvi
- [ ] Cilj: 108 → **≤60 aktivnih** za 90 dana

---

## 6. P1 — Developer Experience (DX)

### 6.1 Plugin Generator
**Cilj:** Novi plugin za 2 minuta, arhitektonski ispravan od prvog fajla.

```bash
python manage.py new_plugin loyalty_points --tier 3
# Generiše: plugin.toml, manifest, services.py (template),
# graphql.py (sa descriptions), hooks.py, tests/ (sa contract test template)
```
- [ ] Template direktorijum: `plugins/installed/_templates/new_plugin/`
- [ ] Generator command + docs

### 6.2 Pre-commit Hooks
- [ ] `.pre-commit-config.yaml`: ruff format/lint, import linter (fast mode), schema check (cached)
- [ ] `pre-commit install` deo onboarding docs-a

### 6.3 Linda Panel → CI Enforcement
**Cilj:** AI-generisane izmene ne ulaze bez panela — čak ni kad je gužva.

**Implementacija:**
- [ ] PR label `ai-generated` obavezan za Linda/agent PR-ove
- [ ] CI proverava: ako label postoji → panel review artefakt mora biti priložen (`.linda/panel-<pr>.json`)
- [ ] Panel verdict `APPROVE` je merge requirement; `REJECT` blokira

---

## 7. P2 — Observability (vidljivost u runtime-u)

### 7.1 Outbox/NATS Dashboard
- [ ] Metrike: outbox backlog size, publish lag p95, DLQ count, per-event-type failure rate
- [ ] Export u Prometheus format (`/metrics` endpoint) ili jednostavan admin view

### 7.2 GraphQL Query Cost
- [ ] Cost analysis middleware: complexity score po query-ju (depth × breadth)
- [ ] Log slow queries (>500ms) sa resolver breakdown-om
- [ ] Alert na p99 > 2s

### 7.3 Plugin Error Attribution
- [ ] Exception handler taguje koji je plugin prouzrokovao grešku (context var kroz hook pipeline)
- [ ] Sentry tag `plugin=<name>` → per-plugin error rate

---

## 8. Izvršni plan — 30 / 60 / 90 dana

### Prvih 30 dana (fondacija)
| Nedelja | Deliverable | Verifikacija |
|---------|-------------|--------------|
| 1 | Import linter + CI (warning mode) | `docs/ARCHITECTURE_DEBT.md` generisan |
| 2 | Schema description gate + report | `docs/SCHEMA_COVERAGE.md` ≥ baseline |
| 3 | Tier sistem (`plugin.toml` svuda) + plugin health command | `/admin/plugins/health` v1 |
| 4 | Golden-path E2E zelen u CI | test prolazi na main |

### 60 dana (zatezanje)
- Coverage gates za tier-1 (80%) — blocking
- Contract tests za sve tier-1 hook subscribere
- Import linter: warning → **error** mode
- Plugin generator + pre-commit
- Prvi talas arhiviranja (108 → ~75)

### 90 dana (stabilizacija)
- ≤60 aktivnih pluginova
- Linda panel CI enforcement
- Observability dashboard (outbox + query cost + plugin errors)
- Plugin health report — nedeljno automatski

---

## 9. Rizici i ublažavanje

| Rizik | Ublažavanje |
|-------|-------------|
| Linter otkrije 500 prekršaja → demotivacija | Grace period, warning mode, fokus na nove fajlove prvo (`--diff` mod) |
| Coverage gates blokiraju hitne fixeve | `hotfix` label bypass + obavezan issue za backfill testova u 7 dana |
| Arhiviranje pluginova slomi nečiju prodavnicu | Deprecation period 30 dana + changelog + migration guide po pluginu |
| Previše procesa za solo developera | Sve je automatika u CI — nula ručnog rada posle setupa |

---

## 10. Merljivi ishodi (definition of done)

1. **0 import prekršaja** u CI (linter blocking, zeleno)
2. **≥98% schema descriptions** (LAW 0)
3. **Tier-1 median coverage ≥80%**, golden path zelen 100%
4. **≤60 aktivnih pluginova**, svi sa `plugin.toml` tier-om
5. **Linda panel obavezan** za AI PR-ove u CI
6. **`/admin/plugins/health`** — jedna stranica, semafor za svaki plugin

---

*Napomena: ovaj plan ne menja ni jedan od 11 zakona — samo ih čini automatski sprovedivim. Core engine ostaje netaknut; sva nova logika je u `tools/`, CI i adminu.*

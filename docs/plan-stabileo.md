# Plan — lo que vale la pena tomar de Stabileo

**Fuente:** [`lambdaclass/stabileo`](https://github.com/lambdaclass/stabileo)
(AGPL-3.0, solver propio en Rust/WebAssembly, normas CIRSOC), revisado el
2026-11-13 (v0.5.0).
**Fecha:** 2026-11-13.
**Perfil que guía la selección:** OpenSees Studio es una herramienta de
**análisis y diseño profesional**. Quedan fuera la docencia (método de rigidez
paso a paso, ejercicios), la IA, lo web (recálculo en vivo, enlaces), las normas
latinoamericanas y el portugués; también el análisis armónico y el colapso
plástico.

Regla de licencia: no se copia código. Se reimplementa sobre OpenSees a partir
de la literatura y de los códigos publicados. Todas las piezas necesarias
existen en OpenSeesPy 3.8 (probado: `ShellDKGQ`, `ShellNLDKGQ`, `ShellDKGT`,
`TDConcreteMC10`, `PySimple1`, `TzSimple1`, `QzSimple1`, `InitStressMaterial`,
`remove element`).

Cada punto es un PR con su ayuda, README/README.es, CHANGELOG y los gates de
`CLAUDE.md`. Cada entrega suma sus benchmarks externos al Verification Manual
(punto 9).

---

## Fase 0 — Confianza en los resultados

| # | Entrega | Estado |
|---|---|---|
| 10 | **Snapshots de resultados y "Results changed".** Cada caso de cada ejemplo fijado por una huella en `tests/data/results_snapshots.json`; CI falla si un número se mueve más de 1e-5; `--write --reason` registra el antes/después en `docs/results-changes.md`. | Hecho |
| 11 | **Diagnóstico de mecanismos.** Check Stability nombra el mecanismo (nudos, GDL, elementos), lo dibuja en el canvas y se revisa antes de cada corrida, con un mensaje accionable. | Pendiente |

## Fase 1 — Análisis

| # | Entrega | Verificación | Estado |
|---|---|---|---|
| 1 | Láminas `ShellDKGQ`, `ShellNLDKGQ`, `ShellDKGT` (triángulos) | Placas de Timoshenko, Scordelis-Lo, hemisferio pinchado, Morley | Pendiente |
| 2 | Construcción por etapas: fases que agregan/quitan grupos, apoyos y cargas sobre el estado anterior | Voladizo por tramos contra cálculo a mano | Pendiente |
| 3 | Pretensado (`InitStressMaterial`, trazado, pérdidas) y fluencia/retracción (`TDConcreteMC10`) en el tiempo | Viga pretensada (P·e), fib MC2010 | Pendiente |
| 4 | Interacción suelo-estructura: asistente de pilote con resortes p-y / t-z / q-z por estrato | Casos de Reese y Van Impe | Pendiente |

## Fase 2 — Diseño

| # | Entrega | Verificación | Estado |
|---|---|---|---|
| 5 | Hormigón armado ACI 318-19: vigas, columnas P-M biaxial, muros, detallado sísmico; D/C, reporte y memoria | ACI SP-17 | Pendiente |
| 6 | Placas base (AISC DG1 + ACI 318 cap. 17) y uniones abulonadas/soldadas de corte y momento con prying | Ejemplos AISC / DG1 | Pendiente |

## Fase 3 — Producto

| # | Entrega | Estado |
|---|---|---|
| 8 | Interfaz en español: infraestructura de traducción de Qt, selector de idioma, menús, diálogos y ayuda | Pendiente |

## Transversal

| # | Entrega | Estado |
|---|---|---|
| 9 | Verificación externa (NAFEMS, ANSYS VM, Code_Aster) en el Verification Manual: por entrega y una tanda dedicada al cerrar la Fase 1 (~25 casos) | Pendiente |

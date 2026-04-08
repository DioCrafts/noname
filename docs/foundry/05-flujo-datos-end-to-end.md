# Flujo de Datos End-to-End en Palantir Foundry — Apuntes

> Caso completo (práctico) de extremo a extremo: **Fuente externa → Magritte (Agents) → Bronze/Silver/Gold → Ontología (Funnel/Phonograph/ES8) → Workshop/AIP → Actions (write-back)**, con consideraciones **on‑prem (OpenShift/Rubix)**.
>
> Última actualización: 2026-04-08

---

## Índice

1. [Vista general del flujo](#1-vista-general-del-flujo)
2. [Caso de ejemplo: Pedidos/Clientes](#2-caso-de-ejemplo-pedidosclientes)
3. [Ingesta (Magritte + Agents) → Bronze](#3-ingesta-magritte--agents--bronze)
4. [Transformaciones → Silver](#4-transformaciones--silver)
5. [Curación → Gold](#5-curación--gold)
6. [Incrementales: watermarks, lookback e idempotencia](#6-incrementales-watermarks-lookback-e-idempotencia)
7. [Calidad de datos y contratos de esquema](#7-calidad-de-datos-y-contratos-de-esquema)
8. [Publicación a Ontología (backing datasets)](#8-publicación-a-ontología-backing-datasets)
9. [Indexing: Funnel → Phonograph/ES8 → OSS](#9-indexing-funnel--phonographes8--oss)
10. [Consumo: Workshop](#10-consumo-workshop)
11. [Consumo: AIP/LLMs (grounding + Actions)](#11-consumo-aipllms-grounding--actions)
12. [Write-back: Actions y datasets de escritura](#12-write-back-actions-y-datasets-de-escritura)
13. [On‑prem (OpenShift/Rubix): red, TLS, proxies y air‑gapped](#13-on-prem-openshiftrubix-red-tls-proxies-y-air-gapped)
14. [Observabilidad y troubleshooting](#14-observabilidad-y-troubleshooting)
15. [Checklist end-to-end (antes de producción)](#15-checklist-end-to-end-antes-de-producción)
16. [Referencias internas del repo](#16-referencias-internas-del-repo)

---

## 1. Vista general del flujo

Diagrama “de manual”:

# Post-mortem técnico — [Título: qué se degradó/rompió y dónde]

> **Plantilla.** Copia este fichero, renómbralo `post-mortem-AAAA-MM-tema.md` y sustituye los textos entre corchetes. La estructura sigue el [post-mortem real del repo](../../post-mortem-2026-04-ontologia-highbury.md) — úsalo como ejemplo de nivel de detalle.
>
> **Principio:** un post-mortem es **sin culpables** (blameless). Buscamos entender el sistema, no señalar personas. Escríbelo en lenguaje claro: el lector puede no haber vivido el incidente.

**Fecha del incidente:** [AAAA-MM-DD — AAAA-MM-DD]
**Entorno:** [producción / pre-producción · cloud / on-prem]
**Servicio(s) afectado(s):** [nombre de servicios, ej. `hb-search-node`]
**Impacto:** [una frase: qué notaron los usuarios]
**Estado:** [resuelto / mitigado / en seguimiento]
**Autor(es):** [quién escribe] · **Revisado por:** [quién valida]

---

## 1. Resumen ejecutivo

[5–10 líneas que cualquier persona del equipo pueda leer en 1 minuto: qué pasó, cuánto duró, a quién afectó, cuál fue la causa más probable y cómo se resolvió. Escríbelo al final, cuando ya sepas todo.]

## 2. Impacto

### Impacto funcional
- [Qué dejó de funcionar para los usuarios, y para cuántos]
- [Procesos de negocio afectados, SLAs incumplidos]

### Impacto técnico
- [Servicios degradados, errores observados, datos retrasados/perdidos]

## 3. Infraestructura afectada

[Tabla o lista de nodos/servicios/recursos implicados. Incluye lo que *parecía* implicado aunque luego se descartara — ayuda al siguiente diagnóstico.]

| Recurso | Rol | Estado durante el incidente |
|---|---|---|
| [nodo/servicio] | [qué hace] | [síntoma] |

## 4. Síntomas observados

### 4.1 Métricas
[Qué mostraban los dashboards: valores concretos, no "estaba alto".]

### 4.2 Logs
```text
[Mensajes de error literales — son oro para el siguiente incidente similar]
```

### 4.3 Comportamiento del sistema
[Qué se veía desde fuera: lentitud, timeouts, colas…]

## 5. Línea temporal del incidente

[Por fases, con hora. Incluye las hipótesis descartadas: el camino errado también enseña.]

- **[HH:MM] Detección** — [cómo nos enteramos: ¿alerta o aviso de usuario?]
- **[HH:MM] Primera hipótesis** — [qué se pensó y qué se hizo]
- **[HH:MM] Nuevo dato / giro** — [qué cambió el diagnóstico]
- **[HH:MM] Escalación** — [a quién: vendor, otro equipo]
- **[HH:MM] Mitigación** — [qué paró el daño]
- **[HH:MM] Resolución** — [qué lo arregló de verdad]

## 6. Causa raíz

### 6.1 Causa raíz principal
[La causa de fondo, numerada si son varias encadenadas. "Causa raíz" ≠ "lo último que se tocó".]

### 6.2 Mecanismo técnico del fallo
[Cómo la causa produjo los síntomas, paso a paso. Diagramas ASCII bienvenidos.]

## 7. Factores contribuyentes

[Lo que no causó el incidente pero lo hizo más probable, más largo o más difícil de diagnosticar: suposiciones no validadas, señales ambiguas, falta de monitorización…]

## 8. Qué NO fue la causa

[Hipótesis investigadas y descartadas, con la evidencia que las descartó. Esta sección ahorra horas en el próximo incidente parecido.]

## 9. Acciones realizadas para resolverlo

[Qué se investigó, qué se cambió y qué configuración quedó aplicada. Incluir configs/comandos literales.]

## 10. Procedimiento de diagnóstico paso a paso

[Reconstrucción "limpia" del diagnóstico, como runbook: si volviera a pasar, ¿cuál es el camino directo? Candidato a incorporarse al doc [11-errores-comunes-y-troubleshooting.md](../foundry/11-errores-comunes-y-troubleshooting.md).]

## 11. Diagrama causal

```
[causa raíz] ──▶ [efecto intermedio] ──▶ [síntoma visible] ──▶ [impacto en usuarios]
```

## 12. Lecciones aprendidas

[Qué sabemos ahora que no sabíamos antes. Sobre el sistema, no sobre personas.]

## 13. Acciones preventivas

| Acción | Responsable | Plazo | Estado |
|---|---|---|---|
| [corto plazo] | [nombre/equipo] | [fecha] | ⬜ |
| [medio plazo] | | | ⬜ |
| [largo plazo] | | | ⬜ |

> Sin responsable y fecha, una acción preventiva es solo una intención. Revisar este cuadro en las reuniones de equipo hasta cerrarlo.

## 14. Recomendaciones operativas

[Cambios de práctica diaria: qué monitorizar, qué validar antes de desplegar, qué documentar.]

## 15. Anexo — Comandos útiles de diagnóstico

```bash
# [comandos que sirvieron durante el incidente, comentados]
```

## 16. Conclusión final

[2–4 líneas: el incidente en una mirada retrospectiva. ¿Qué frase queremos que recuerde quien lea esto dentro de un año?]

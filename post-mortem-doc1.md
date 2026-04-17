

# 🔴 Post-Mortem: Degradación de la Ontología en Palantir Foundry

**Fecha del incidente:** Abril 2026
**Autor:** *(tu nombre)*
**Severidad:** Alta — Ontología degradada para todos los usuarios
**Estado:** ✅ Resuelto

---

## 1. Resumen ejecutivo

Los servicios de búsqueda de la ontología de Palantir Foundry (Highbury Search Nodes) experimentaron una degradación severa de rendimiento. Las búsquedas y filtros en la ontología se volvieron extremadamente lentos, afectando a todos los usuarios del entorno Gemini.

**Causa raíz:** Los 2 nodos de búsqueda existentes tenían más shards de índice de los que su page cache (RAM) podía retener, provocando **cache thrashing** — un ciclo continuo de lecturas a disco que saturó el throughput de disco al 100%.

**Resolución:** Se añadió un tercer nodo de búsqueda (`dell-jht9zc3`) y se configuró el `hb-coordinator` para redistribuir los shards de forma agresiva, reduciendo la presión de page cache en cada nodo.

---

## 2. Entorno afectado

### Infraestructura

| Componente | Detalle |
|---|---|
| Plataforma | Palantir Foundry |
| Entorno | Gemini |
| Servicio afectado | Highbury Search Nodes |
| Servicio coordinador | hb-coordinator |

### Servidores involucrados

| Nombre del servicio | ID | Servidor físico | Rol |
|---|---|---|---|
| `hb-search-node-foundry-1` | 673192857 | `dell-6xyhf33` (alias `dell-6jxhf33.palantir.local`) | Nodo de búsqueda (existente) |
| *(nodo 2)* | 673240239 | `dell-67yxlf33` (alias `dell-6yxlf33`) | Nodo de búsqueda (existente) |
| *(nodo 3)* | 673690997 | `dell-jht9zc3` | Nodo de búsqueda (añadido para resolver el incidente) |

### Configuración previa al incidente

```yaml
# hb-coordinator — configuración ANTES del incidente
allocation:
  node-blocklist:
    - dell-6jxhf33.palantir.local
    - dell-6yxlf33
```

Solo 2 nodos en el blocklist del coordinator, es decir, solo 2 nodos dedicados exclusivamente a búsqueda.

---

## 3. Cronología del incidente

| Fase | Evento | Detalle |
|---|---|---|
| **Detección** | Se detecta ontología lenta | Usuarios reportan tiempos de respuesta muy altos en búsquedas y filtros de la ontología |
| **Diagnóstico inicial** | Revisión de métricas de infraestructura | Dashboard muestra **Disk Throughput per Device al 100%** en `dell-6xyhf33` y `dell-67yxlf33` |
| **Acción 1** | Se provisiona un tercer nodo | Se añade `dell-jht9zc3` (ID 673690997) al cluster para aumentar capacidad de cómputo |
| **Problema 2** | El nodo nuevo no puede unirse al cluster | Logs en `dell-jht9zc3` muestran errores de `QosException$Throttle` con razón `user-static-limits-queue-full` |
| **Escalación** | Se contacta a soporte de Palantir | Se comparten logs y métricas |
| **Diagnóstico de soporte** | Soporte identifica causa raíz | Ingeniero de Palantir determina que los 2 nodos existentes están sufriendo **contención de page cache** — demasiados shards para la RAM disponible |
| **Resolución** | Se modifica configuración del hb-coordinator | Se añade `dell-jht9zc3` al `node-blocklist` y se suben los límites de rebalanceo a 100 |
| **Verificación** | Ontología recupera rendimiento normal | Disk throughput baja, búsquedas vuelven a velocidad normal |

---

## 4. Causa raíz — Análisis técnico detallado

### 4.1. Qué es el page cache y por qué importa

El **page cache** es una región de la RAM del sistema operativo Linux que se utiliza para cachear datos leídos del disco. Cuando un proceso lee un fichero, el kernel guarda esos datos en RAM para que futuras lecturas del mismo fichero sean instantáneas (desde RAM) en lugar de lentas (desde disco).

Highbury Search Nodes leen ficheros de índice de búsqueda intensivamente. El rendimiento de Highbury depende directamente de que los índices estén en page cache (RAM) y no tengan que leerse del disco en cada query.

### 4.2. La distribución de memoria en cada nodo

```
RAM total del servidor (ejemplo):
┌─────────────────────────────────────────────┐
│                                             │
│  ┌──────────────────┐                       │
│  │ Java Heap        │  (Highbury/JVM)       │
│  │ ~50% de la RAM   │                       │
│  └──────────────────┘                       │
│                                             │
│  ┌──────────────────┐                       │
│  │ Sistema Operativo│  (kernel, procesos)   │
│  │ ~5-10% de la RAM │                       │
│  └──────────────────┘                       │
│                                             │
│  ┌──────────────────┐                       │
│  │ PAGE CACHE       │  (lo que queda)       │
│  │ ~40-45% de RAM   │  ← AQUÍ se cachean   │
│  │                  │    los índices         │
│  └──────────────────┘                       │
│                                             │
└─────────────────────────────────────────────┘
```

El page cache usa **toda la RAM que no está ocupada** por otros procesos. No se configura explícitamente: el kernel Linux lo gestiona automáticamente.

### 4.3. El problema: cache thrashing

Con solo **2 nodos** sirviendo toda la ontología, cada nodo tenía asignados un número elevado de shards (fragmentos del índice). El volumen total de datos de los índices **superaba con creces** la capacidad de page cache de cada nodo.

**Esto provoca un fenómeno llamado cache thrashing:**

```
Paso 1: Query "contratos" necesita Shard A y B
        → Se leen del DISCO y se cargan en page cache
        → Page cache se llena

Paso 2: Query "facturas" necesita Shard C y D
        → NO HAY ESPACIO en page cache
        → El kernel EXPULSA Shard A y B de la caché
        → Se leen Shard C y D del DISCO

Paso 3: Otra query "contratos" necesita Shard A y B de nuevo
        → YA NO ESTÁN en page cache (fueron expulsados)
        → HAY QUE RELEERLOS DEL DISCO
        → El kernel EXPULSA Shard C y D

... ciclo infinito de lecturas a disco
```

**Resultado:** El disco nunca para de leer → **throughput al 100% permanentemente**.

### 4.4. Por qué el nodo nuevo no podía unirse

Cuando se añadió `dell-jht9zc3`, este intentó registrarse en el cluster enviando **heartbeats** (señales de vida) al nodo master. Sin embargo, el master ya estaba saturado gestionando los 2 nodos con problemas de I/O, y su **cola de peticiones QoS** estaba llena.

```
dell-jht9zc3 ──── heartbeat ────→ Master Node
                                     │
                                     ▼
                              Cola QoS: LLENA
                                     │
                                     ▼
                              QosException$Throttle
                              reason: user-static-limits-queue-full
                                     │
                                     ▼
                              RECHAZADO ❌
```

**Error exacto encontrado en los logs:**

```
Ruta de logs: /opt/palantir/services/foundry/hb-search-node*/var/log/
Comando: tail -f service.log | deployctl slslog

Failed to heartbeat DB nodes in the cluster, this is likely caused by 
an issue with client.

com.palantir.conjure.java.api.errors.QosException.throttle 
  QosException.java:77

Error handling request due to QoS
  HB_MASTER_REQUEST_ID: 1e05617f7381bfbc
  OWNING_RID: ri.workshop.main.module.5dhr.....
  qosReason: user-static-limits-queue-full
  rootCause: com.palantir.conjure.java.api.errors.QosException$Throttle
```

---

## 5. Resolución — Paso a paso

### Paso 1: Diagnóstico desde los servidores

#### 1.1. Conexión SSH al nodo con errores
```bash
ssh <usuario>@dell-jht9zc3
```

#### 1.2. Navegación al directorio de logs
```bash
cd /opt/palantir/services/foundry/
ls -la | grep hb-search          # identificar la carpeta exacta
cd hb-search-node*/var/log/
ls -la                            # verificar nombre del fichero de log
```

#### 1.3. Visualización de logs en tiempo real
```bash
# Ver logs formateados (herramienta de Palantir)
tail -f service.log | deployctl slslog

# Filtrar solo errores
tail -f service.log | deployctl slslog 2>&1 | grep -iE "error|exception|fatal"

# Filtrar errores EXCLUYENDO los de throttle (para buscar otros problemas)
tail -5000 service.log | deployctl slslog 2>&1 | grep -iE "error|exception" | grep -v "QosException"

# Exportar errores a fichero para compartir con soporte
tail -5000 service.log | deployctl slslog > /tmp/errores_jht9zc3.log 2>&1
```

#### 1.4. Verificación del estado de disco
```bash
# En cada uno de los 3 servidores:
iostat -xz 2          # %util cercano a 100% confirma saturación
iotop -o              # ver qué procesos consumen más I/O
df -h                 # verificar espacio libre
smartctl -a /dev/sda  # salud física del disco
```

### Paso 2: Escalación a soporte de Palantir

Se contactó a soporte con la siguiente información:
- Métricas de Disk Throughput al 100% en los 2 nodos originales
- Logs del nodo nuevo mostrando `QosException$Throttle` con `queue-full`
- IDs de los 3 nodos y servidores Dell asociados

### Paso 3: Modificación de la configuración del hb-coordinator

Soporte de Palantir realizó los siguientes cambios en la configuración del servicio **hb-coordinator**:

#### Configuración ANTES (no funcionaba)
```yaml
# hb-coordinator config — ANTES
allocation:
  node-blocklist:
    - dell-6jxhf33.palantir.local
    - dell-6yxlf33
```
- Solo 2 nodos de búsqueda.
- Límites de rebalanceo por defecto (conservadores).
- El nodo nuevo no podía unirse por QoS throttling.

#### Configuración DESPUÉS (solución aplicada)
```yaml
# hb-coordinator config — DESPUÉS
allocation:
  max-concurrent-moves: 100
  max-concurrent-moves-during-cluster-expansion: 100
  max-concurrent-rebalances-during-cluster-expansion: 100
  node-blocklist:
    - dell-6jxhf33.palantir.local
    - dell-6yxlf33
    - dell-jht9zc3                    # ← AÑADIDO
```

#### Qué hace cada parámetro

| Parámetro | Valor anterior | Valor nuevo | Efecto |
|---|---|---|---|
| `max-concurrent-moves` | Default (bajo) | `100` | Permite mover hasta 100 shards simultáneamente entre nodos |
| `max-concurrent-moves-during-cluster-expansion` | Default (bajo) | `100` | Lo mismo pero específicamente cuando se detecta un nuevo nodo |
| `max-concurrent-rebalances-during-cluster-expansion` | Default (bajo) | `100` | Permite 100 operaciones de rebalanceo simultáneas durante expansión |
| `node-blocklist` | 2 nodos | 3 nodos | Registra `dell-jht9zc3` como nodo exclusivo de búsqueda (no coordinator) |

#### Por qué `node-blocklist` no significa "bloquear"

El nombre es confuso. En el contexto de `hb-coordinator`, el **blocklist** indica qué nodos **no deben ejecutar el servicio coordinator**. Es decir, estos nodos se dedican **exclusivamente** a tareas de búsqueda. Al añadir `dell-jht9zc3` al blocklist:

- ✅ Se le asigna rol de **search worker**
- ✅ Se le enviarán shards durante el rebalanceo
- ❌ No ejecutará lógica de coordinación (eso lo hace otro nodo)

### Paso 4: Rebalanceo de shards

Tras aplicar la configuración, el cluster inició un rebalanceo agresivo:

```
ANTES del rebalanceo:
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ dell-6xyhf33     │  │ dell-67yxlf33    │  │ dell-jht9zc3     │
│ ~50 shards       │  │ ~50 shards       │  │ 0 shards         │
│ Page cache: ❌    │  │ Page cache: ❌    │  │ Page cache: ✅    │
│ Disco: 100% 🔴   │  │ Disco: 100% 🔴   │  │ Disco: 0% 🟢     │
└──────────────────┘  └──────────────────┘  └──────────────────┘

     ──── Rebalanceo con max-concurrent-moves: 100 ────
     ──── Shards moviéndose agresivamente al nodo 3 ────

DESPUÉS del rebalanceo:
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ dell-6xyhf33     │  │ dell-67yxlf33    │  │ dell-jht9zc3     │
│ ~33 shards       │  │ ~33 shards       │  │ ~34 shards       │
│ Page cache: ✅    │  │ Page cache: ✅    │  │ Page cache: ✅    │
│ Disco: ~65% 🟡   │  │ Disco: ~65% 🟡   │  │ Disco: ~65% 🟡   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Paso 5: Verificación

Tras el rebalanceo:
- [ ] Disk Throughput de los 3 nodos bajó a niveles normales
- [ ] Las búsquedas de ontología recuperaron velocidad normal
- [ ] Los logs dejaron de mostrar errores de `QosException$Throttle`
- [ ] El nodo `dell-jht9zc3` aparece activo en el cluster y sirviendo queries

---

## 6. Diagrama completo del incidente

```
                         ESTADO INICIAL
                         ══════════════
                    2 nodos, ontología funcionando
                               │
                               ▼
                    Volumen de datos crece
                    Más shards por nodo
                               │
                               ▼
               ┌───────────────────────────────┐
               │  CACHE THRASHING              │
               │  Los shards se expulsan       │
               │  mutuamente del page cache    │
               │  dentro de cada nodo          │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  DISCO AL 100%                │
               │  Lecturas continuas a disco   │
               │  dell-6xyhf33 y dell-67yxlf33 │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  ONTOLOGÍA LENTA              │
               │  Usuarios afectados           │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  ACCIÓN: Añadir nodo nuevo    │
               │  dell-jht9zc3 (673690997)     │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  PROBLEMA: QoS Throttle       │
               │  queue-full — nodo no puede   │
               │  hacer heartbeat al master    │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  ESCALACIÓN A SOPORTE         │
               │  Comparten logs y métricas    │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  SOLUCIÓN:                    │
               │  1. Añadir dell-jht9zc3 al    │
               │     node-blocklist            │
               │  2. Subir max-concurrent-     │
               │     moves a 100               │
               │  3. Rebalanceo agresivo       │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  RESULTADO:                   │
               │  - Shards redistribuidos      │
               │  - Page cache respira         │
               │  - Disco baja del 100%        │
               │  - Ontología recuperada ✅     │
               └───────────────────────────────┘
```

---

## 7. Lecciones aprendidas

| # | Lección | Acción preventiva |
|---|---|---|
| 1 | El ratio shards/page cache es crítico para el rendimiento de Highbury | Monitorizar la relación entre volumen de índices y RAM disponible por nodo |
| 2 | El Disk Throughput al 100% sostenido es síntoma de cache thrashing, no de disco lento | Crear alerta cuando Disk Throughput > 85% durante más de 10 minutos |
| 3 | Un cluster saturado puede impedir la incorporación de nuevos nodos (QoS throttle) | Planificar ampliaciones ANTES de llegar al límite de capacidad |
| 4 | Los límites de rebalanceo por defecto pueden ser demasiado conservadores para emergencias | Documentar cómo ajustar `max-concurrent-moves` y cuándo hacerlo |
| 5 | El `node-blocklist` del hb-coordinator tiene un nombre confuso | Documentar que blocklist = "este nodo es worker de búsqueda, no coordinator" |

---

## 8. Acciones de seguimiento

| # | Acción | Responsable | Estado | Fecha límite |
|---|---|---|---|---|
| 1 | Crear alerta de Disk Throughput > 85% en todos los search nodes | *(nombre)* | ⬜ Pendiente | |
| 2 | Crear alerta de ratio shards/nodo para anticipar necesidad de escalar | *(nombre)* | ⬜ Pendiente | |
| 3 | Evaluar upgrade de discos a NVMe/SSD si el volumen sigue creciendo | *(nombre)* | ⬜ Pendiente | |
| 4 | Documentar procedimiento de añadir nodos nuevos (esta guía) | *(nombre)* | ✅ Hecho | |
| 5 | Revisar si los valores de `max-concurrent-moves: 100` deben mantenerse o revertirse a defaults tras el rebalanceo | *(nombre)* | ⬜ Pendiente | |
| 6 | Planificar capacidad: ¿cuántos nodos necesitaremos en 6/12 meses? | *(nombre)* | ⬜ Pendiente | |

---

## 9. Contactos de referencia

| Rol | Quién | Cuándo contactar |
|---|---|---|
| Soporte Palantir | *(canal/email)* | Errores de QoS, configuración de hb-coordinator, problemas de cluster |
| Equipo de infraestructura | *(nombre)* | Provisión de servidores, discos, red |
| Equipo de ontología | *(nombre)* | Optimización de índices, queries pesadas |

---

## 10. Referencias y comandos rápidos

### Acceso a logs
```bash
ssh <usuario>@<servidor>
cd /opt/palantir/services/foundry/hb-search-node*/var/log/
tail -f service.log | deployctl slslog
```

### Diagnóstico rápido de disco
```bash
iostat -xz 2       # %util > 85% = problema
iotop -o            # qué proceso consume I/O
df -h               # espacio libre
```

### Exportar diagnóstico para soporte
```bash
tail -5000 service.log | deployctl slslog > /tmp/errores.log 2>&1
iostat -xz 1 5 > /tmp/disco.log
top -bn1 | head -20 > /tmp/recursos.log
free -h >> /tmp/recursos.log
df -h >> /tmp/espacio.log
```

---

*Documento generado: Abril 2026*
*Última actualización: _(fecha)_*
*Próxima revisión: _(fecha + 3 meses)_*

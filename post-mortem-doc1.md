# Post-mortem técnico — Degradación severa de Ontología en Palantir Foundry (Highbury Search)

**Fecha del incidente:** abril de 2026  
**Entorno:** Palantir Foundry on-premises  
**Infraestructura:** datacenter local, servidores Dell  
**Servicio afectado:** `hb-search-node` / `hb-coordinator`  
**Impacto:** degradación severa de rendimiento en búsquedas de ontología  
**Estado:** resuelto

---

## 1. Resumen ejecutivo

La ontología de Foundry sufrió una degradación severa de rendimiento en el entorno on-premises. Durante el incidente, varios `hb-search-node` mostraban **Disk Throughput per Device al 100%**, las búsquedas iban muy lentas y aparecieron errores de tipo:

```text
qosReason: user-static-limits-queue-full
rootCause: QosException$Throttle
com.palantir.conjure.java.api.errors.QosException.throttle
QosException.java:77
Error handling request due to QoS
```

Inicialmente, el síntoma se interpretó como un problema de saturación del cluster y posible contención de page cache. Sin embargo, tras el análisis y las acciones correctivas, la causa más probable del incidente fue:

1. **Despliegue de más de un nodo Highbury en el mismo servidor físico**, compartiendo recursos críticos.
2. **Rendimiento de disco insuficiente**, agravado porque los discos de esos servidores **no estaban en RAID 0**, reduciendo significativamente el throughput / IOPS disponibles.
3. Como consecuencia, se produjo **saturación de I/O**, aumento de latencia interna, colas llenas y errores de **QoS throttling**.
4. La solución definitiva fue **retirar los nodos que compartían servidor**, reintroducirlos **sin compartir recursos**, y corregir la asignación para evitar co-location problemática.

En paralelo, se aplicaron ajustes en `hb-coordinator` para facilitar el rebalanceo y la expansión del cluster.

---

## 2. Impacto

### Impacto funcional
- Búsquedas y navegación en la ontología significativamente lentas.
- Posible degradación en aplicaciones y workflows dependientes de búsquedas de objetos/relaciones.
- Aumento de tiempos de respuesta percibidos por usuarios finales.

### Impacto técnico
- Saturación de disco en nodos Highbury.
- Heartbeats y/o llamadas internas del cluster degradadas.
- Errores de throttling QoS por colas llenas.
- Redistribución de shards dificultada.
- Riesgo de diagnóstico ambiguo por múltiples cuellos de botella simultáneos.

---

## 3. Infraestructura afectada

### Nodos mencionados durante el incidente

| Servicio / nodo | ID | Host Dell | Observaciones |
|---|---:|---|---|
| `hb-search-node-foundry-1` | `673192857` | `dell-6xyhf33` / `dell-6jxhf33.palantir.local` | Nodo existente |
| `hb-search-node` | `673240239` | `dell-67yxlf33` / `dell-6yxlf33` | Nodo existente |
| `hb-search-node` | `673690997` | `dell-jht9zc3` | Nodo añadido durante la mitigación |

> Nota: en la conversación aparecen ligeras variaciones de hostname (`6xyhf33` vs `6jxhf33`). En la documentación final conviene normalizar los nombres exactos desde CMDB / inventario.

---

## 4. Síntomas observados

### 4.1 Métricas
- **Disk Throughput per Device al 100%** en al menos dos nodos.
- Ontología muy lenta.
- Cluster con dificultad para absorber un nodo adicional.

### 4.2 Logs
Se observaron errores como:

```text
Failed to heartbeat DB nodes in the cluster, this is likely caused by an issue with client

com.palantir.conjure.java.api.errors.QosException.throttle
QosException.java:77

Error handling request due to QoS
HB_MASTER_REQUEST_ID: 1e05617f7381bfbc
OWNING_RID: ri.workshop.main.module.5dhr.....
qosReason: user-static-limits-queue-full
rootCause: com.palantir.conjure.java.api.errors.QosException$Throttle
```

### 4.3 Comportamiento del sistema
- Al añadir nodos para escalar, la mejora esperada no fue inmediata.
- Hubo errores desde el nodo nuevo / nodos en expansión.
- El problema desapareció al **retirar nodos colocados en el mismo servidor** y reintroducirlos sin compartir recursos.

---

## 5. Línea temporal del incidente

> Ajusta horas exactas si luego las recuperáis de tickets, dashboards o Slack.

### Fase 1 — Detección
- Usuarios/equipo detectan que la ontología va muy lenta.
- Se revisan dashboards de infraestructura.
- Se identifica que dos servidores muestran **disk throughput al 100%**.

### Fase 2 — Primera hipótesis
- Se sospecha de saturación de búsqueda / Highbury.
- Se contempla falta de capacidad y/o presión sobre page cache.
- Se decide añadir capacidad con un nodo adicional (`dell-jht9zc3`).

### Fase 3 — Nuevo síntoma tras ampliación
- El nodo nuevo / llamadas internas muestran errores de QoS:
  - `user-static-limits-queue-full`
  - `QosException$Throttle`
- Se interpreta que la cola de peticiones internas está llena o que el coordinador/master no puede absorber más carga en ese momento.

### Fase 4 — Escalación con Palantir
- Soporte / ingeniería de Palantir analiza el patrón.
- Se observa que el problema apareció cuando **se metió más de un nodo hb en el mismo servidor**.
- Se comenta que en otros clientes este patrón no había fallado, aunque con **volumetría de objetos distinta**.

### Fase 5 — Mitigación y resolución
- Se **quitan los nodos que estaban compartiendo servidor**.
- Se vuelven a añadir **sin compartir recursos**.
- Se identifica además que esos servidores **no tenían los discos en RAID 0**, lo que degradaba aún más el rendimiento de disco.
- Tras redistribuir correctamente y evitar co-location problemática, el servicio vuelve a la normalidad.

---

## 6. Causa raíz

## 6.1 Causa raíz principal
La causa raíz más probable fue una **mala adecuación entre el patrón de despliegue y la capacidad real de I/O del host**, concretamente:

- **Más de un `hb-search-node` desplegado en el mismo servidor físico**.
- Ambos nodos compartían recursos críticos del host:
  - discos
  - page cache del sistema
  - cola de I/O
  - ancho de banda de almacenamiento
  - CPU/RAM indirectamente
- El almacenamiento del servidor además no estaba configurado en **RAID 0**, lo que limitaba aún más el rendimiento agregado disponible para un workload intensivo en lectura/escritura como Highbury.

## 6.2 Mecanismo técnico del fallo

### A) Co-location de múltiples hb nodes en el mismo host
Aunque lógicamente el cluster “ve” varios nodos, físicamente esos nodos competían por el mismo hardware. Eso rompe parte del supuesto de escalado horizontal:

```text
Escalado esperado:
1 nodo por servidor  -> más hosts -> más disco total -> más page cache total

Escalado problemático:
2 nodos en 1 servidor -> más procesos, pero mismo disco físico -> misma limitación real
```

### B) Contención de page cache
Aquí es importante precisar el lenguaje:

- Los **nodos no compiten entre servidores** por page cache.
- Sí **compiten dentro del mismo servidor físico** si hay varios procesos/nodos consumiendo memoria y leyendo índices distintos.
- Si dos `hb-search-node` están en el mismo host, ambos presionan:
  - la misma RAM física
  - el mismo page cache Linux
  - los mismos discos

Eso puede producir **cache thrashing**:
- un nodo carga bloques/índices en page cache,
- el otro los expulsa al necesitar otros,
- ambos fuerzan relecturas desde disco,
- el disco se satura.

### C) Cuello de botella de disco agravado por RAID
El viernes, incluso tras parte de la mitigación, el rendimiento seguía mal porque **los discos no estaban en RAID 0**.

En un motor de búsqueda / indexación, especialmente on-prem:
- el throughput secuencial importa,
- pero también importan mucho los **IOPS** y la latencia de lectura aleatoria,
- una configuración de disco inadecuada puede hacer inviable un patrón de despliegue que sobre el papel parecía aceptable.

### D) Manifestación en forma de QoS throttling
El error:

```text
qosReason: user-static-limits-queue-full
rootCause: QosException$Throttle
```

No era necesariamente la causa primaria, sino un **síntoma aguas abajo**.

Interpretación más probable:
- el cluster / coordinador / servicio destino estaba respondiendo más lentamente de lo normal,
- las peticiones internas se acumulaban,
- la cola de QoS alcanzaba su límite,
- Foundry empezaba a hacer throttle para autoprotección.

Es decir:

```text
mala topología de despliegue
+ rendimiento insuficiente de disco
→ saturación de I/O
→ latencias internas altas
→ colas llenas
→ QoS throttle
```

---

## 7. Factores contribuyentes

### 7.1 Topología de despliegue no validada para esta volumetría
Palantir indicó que el mismo patrón se había probado en otros clientes, pero con distinta volumetría de objetos. Eso encaja con que el problema no sea el patrón en abstracto, sino su interacción con:
- número de objetos
- tamaño de índices
- intensidad de consulta
- capacidad del hardware

### 7.2 Suposición de que “más nodos lógicos” equivale a más capacidad real
Si dos nodos viven en el mismo host y comparten disco, no se obtiene una duplicación real de capacidad de I/O.

### 7.3 Limitación de almacenamiento
La falta de RAID 0 en discos con carga intensiva de Highbury reducía el margen operativo.

### 7.4 Señal diagnóstica ambigua
El error QoS podía hacer pensar inicialmente en:
- un problema de límites por usuario,
- una app Workshop ruidosa,
- o una mala configuración de colas.

Pero en este caso el throttling parece haber sido un **efecto secundario** del cuello de botella de infraestructura.

---

## 8. Qué NO fue la causa principal

Es importante dejar claro qué hipótesis se consideraron y cómo quedan reinterpretadas:

### 8.1 “Un usuario o Workshop estaba enviando demasiadas peticiones”
**No hay evidencia suficiente** en la información final para sostener que esa fuera la causa principal del incidente. El `OWNING_RID` puede identificar el contexto de una petición, pero no demuestra por sí solo que el origen fuese una app mal configurada.

### 8.2 “Había que subir QoS static limits por usuario”
Subir límites podía haber mitigado síntomas, pero no solucionaba la raíz. De hecho, en un entorno ya saturado, aumentar límites de cola podría empeorar la presión sobre el sistema.

### 8.3 “El problema era solo page cache”
La explicación de page cache sigue siendo válida como mecanismo técnico parcial, pero la documentación final debe reflejar que el **desencadenante operativo** fue la **co-location de múltiples nodos hb en el mismo servidor con almacenamiento insuficiente**.

---

## 9. Acciones realizadas para resolverlo

## 9.1 Investigación
1. Revisión de dashboards de infraestructura.
2. Observación de `Disk Throughput per Device` al 100%.
3. Inspección de logs de `hb-search-node`.
4. Identificación de errores `QosException$Throttle`.
5. Escalación con ingeniería de Palantir.

## 9.2 Cambios realizados
1. Se retiraron nodos Highbury que compartían el mismo servidor físico.
2. Se reintrodujeron nodos evitando compartir recursos.
3. Se ajustó la configuración de `hb-coordinator` para facilitar rebalanceo / expansión.
4. Se revisó el problema de rendimiento de disco asociado a la configuración RAID.

## 9.3 Configuración aplicada en `hb-coordinator`
Se aplicó una configuración de expansión agresiva:

```yaml
allocation:
  max-concurrent-moves: 100
  max-concurrent-moves-during-cluster-expansion: 100
  max-concurrent-rebalances-during-cluster-expansion: 100
  node-blocklist:
    - dell-6jxhf33.palantir.local
    - dell-6yxlf33
    - dell-jht9zc3
```

### Interpretación técnica
- Los valores altos de `max-concurrent-*` aceleran la movilidad de shards durante expansión del cluster.
- Añadir `dell-jht9zc3` a `node-blocklist` de `hb-coordinator` indica que ese host no debe ejecutar el coordinador y se reserva para el rol esperado dentro de la topología.

> Nota importante: esta parte debe describirse con cuidado según cómo use exactamente Palantir ese parámetro en vuestra versión. En conversaciones previas se interpretó como “reservar el nodo para search y no coordinator”. Conviene validarlo con la documentación interna o con soporte antes de publicarlo como afirmación definitiva.

---

## 10. Procedimiento técnico paso a paso de diagnóstico y resolución

## Paso 1 — Confirmar síntoma en monitoring
Verificar:
- `Disk Throughput per Device`
- latencia de búsqueda
- salud general del cluster
- si hay hosts con múltiples `hb-search-node`

## Paso 2 — Revisar logs del servicio
Ruta típica observada:

```bash
cd /opt/palantir/services/foundry/hb-search-node*/var/log
tail -f service.log | deployctl slslog
```

Filtrado de errores:

```bash
tail -f service.log | deployctl slslog 2>&1 | grep -iE "error|exception|fatal|qos|throttle"
```

## Paso 3 — Correlacionar con infraestructura
En cada host afectado:

```bash
iostat -xz 2
iotop -o
df -h
lsblk
cat /proc/mdstat
```

Objetivo:
- confirmar saturación de disco,
- identificar layout de discos,
- validar RAID,
- comprobar si hay varios servicios Highbury por host.

## Paso 4 — Validar topología real
Comprobar explícitamente:
- cuántos `hb-search-node` hay por servidor físico,
- qué recursos comparten,
- si el despliegue esperado era 1 nodo por host o n nodos por host.

## Paso 5 — Mitigación inmediata
Si se detecta co-location problemática:
- retirar nodos co-localizados,
- redistribuir nodos a hosts separados,
- reducir sharing de disco/page cache.

## Paso 6 — Acelerar recuperación
Una vez la topología es correcta:
- permitir rebalanceo agresivo con parámetros `max-concurrent-*`,
- monitorizar que el rebalanceo no reintroduzca saturación severa.

## Paso 7 — Verificación final
Confirmar:
- caída sostenida del uso de disco,
- desaparición de errores QoS,
- mejora de latencia en ontología,
- distribución estable de shards.

---

## 11. Diagrama causal

```text
Se despliegan múltiples hb-search-node en el mismo servidor
                    │
                    ▼
      Comparten disco, RAM y page cache del host
                    │
                    ▼
     Aumenta la presión sobre I/O y cache del sistema
                    │
                    ▼
       Los índices ya no caben bien en page cache
                    │
                    ▼
            Cache thrashing / relecturas
                    │
                    ▼
            Disco saturado al 100%
                    │
                    ▼
      Latencias internas del cluster se disparan
                    │
                    ▼
   Las colas QoS se llenan y aparece throttling
                    │
                    ▼
      Ontología lenta / degradación generalizada
```

---

## 12. Lecciones aprendidas

### 12.1 No confundir nodos lógicos con capacidad física
Añadir más procesos/nodos en el mismo servidor no equivale a escalar horizontalmente si el cuello de botella es el hardware subyacente.

### 12.2 Highbury es extremadamente sensible al rendimiento de disco
Especialmente en entornos con gran volumetría de objetos, el diseño de almacenamiento importa mucho.

### 12.3 Los errores de QoS pueden ser secundarios
Un `QosException$Throttle` no implica necesariamente un problema de límites “funcional”; puede ser un síntoma de infraestructura saturada.

### 12.4 La volumetría importa
Una topología válida en otro cliente puede no serlo en este entorno debido a:
- más objetos,
- índices mayores,
- patrones de consulta distintos.

---

## 13. Acciones preventivas

### Corto plazo
- Prohibir temporalmente despliegues de múltiples `hb-search-node` en el mismo host salvo validación explícita.
- Validar configuración de discos / RAID en hosts candidatos.
- Documentar la topología soportada para Highbury.

### Medio plazo
- Definir capacity planning específico para:
  - nº de objetos,
  - tamaño de índices,
  - RAM por nodo,
  - IOPS por host,
  - ratio shards/host.
- Crear alertas para:
  - Disk Throughput > 85%
  - latencia de búsqueda
  - incremento de `QosException$Throttle`
  - hosts con múltiples hb nodes

### Largo plazo
- Estandarizar hardware mínimo para nodos Highbury.
- Revisar con Palantir la guía de despliegue recomendada para vuestra volumetría real.
- Establecer pruebas de carga previas a cambios topológicos.

---

## 14. Recomendaciones operativas

1. **1 hb-search-node por servidor físico**, salvo validación de capacidad muy específica.
2. Verificar siempre:
   - tipo de disco,
   - RAID,
   - RAM disponible para page cache,
   - contención de recursos entre servicios.
3. Tratar `QosException$Throttle` como:
   - posible síntoma de límites,
   - pero también posible síntoma de latencia/saturación aguas abajo.
4. Antes de expandir cluster:
   - comprobar salud del coordinador,
   - comprobar capacidad real del storage,
   - validar que el host nuevo aporta capacidad física real.

---

## 15. Anexo — Comandos útiles de diagnóstico

```bash
# logs del servicio
cd /opt/palantir/services/foundry/hb-search-node*/var/log
tail -f service.log | deployctl slslog

# filtrar errores qos / throttle
tail -5000 service.log | deployctl slslog 2>&1 | grep -iE "qos|throttle|queue-full|error|exception"

# uso de disco
iostat -xz 2
iotop -o
df -h

# layout de discos / raid
lsblk
cat /proc/mdstat

# memoria
free -h
vmstat 1

# procesos Highbury
ps aux | grep hb-search
```

---

## 16. Conclusión final

Sí hubo síntomas compatibles con presión de page cache, pero el post-mortem actualizado debe dejar claro que la **causa principal del incidente** fue la **colocación de múltiples nodos Highbury en el mismo servidor físico en un entorno cuyo almacenamiento no tenía rendimiento suficiente**, agravado por una **configuración de discos no óptima (sin RAID 0)** para ese patrón de carga.

La resolución efectiva no fue “subir límites QoS”, sino:
- **retirar la co-location problemática**,
- **redistribuir nodos sin compartir recursos críticos**,
- y **restaurar una topología donde cada nodo aporte capacidad física real**.

---

# Regla de análisis de mano de obra

## Base de cálculo

- Jornada mensual: **168 HH/mes**.
- Dotación equivalente promedio: `HH totales / (168 × plazo total del proyecto en meses)`.
- Meses-hombre: `HH totales / 168`.
- La mano de obra subcontratada se mantiene como recurso de naturaleza **O**; no se transforma en subcontrato **S**.
- Una cotización integral o un subcontrato comercial se mantiene como naturaleza **S** y no forma parte de la dotación HH.
- La dotación mensual de una fila es `HH / (168 × meses activos de su ventana)`.
- Las partidas de costo directo reciben una ventana mensual sugerida por clase de obra, siempre editable. La mano de obra de Gastos Generales conserva el plazo declarado en GG.
- El **peak** es la mayor suma mensual simultánea de empresa CD, empresa GG y mano de obra subcontratada.

## Clasificación para decisiones

Cada fila debe conservar cuatro dimensiones independientes:

1. **Imputación:** Costo Directo o Gastos Generales.
2. **Dependencia:** Empresa o Subcontrato.
3. **Tipo:** Jornal, Maestro, Profesional o Mando medio.
4. **Especialidad del maestro:** Carpintero, Albañil, Yesero, Pintor, Eléctrico, Clima, Gases Clínicos, Terminaciones, Paisajismo, Instalador cubierta, Aplicador impermeabilización, Sanitario u otra especialidad identificada.

La consolidación suma similares sin perder las dimensiones anteriores; por ejemplo, **Jornal · Empresa · Costo Directo** y **Jornal · Subcontrato · Costo Directo** permanecen separados y trazables a cada partida.

## Códigos y tarifas

| Código | Recurso | Tarifa |
|---|---|---:|
| OMACSV | Mano de Obra Maestro San Vicente | $8.928/HH |
| OJOCSV | Mano de obra Jornal San Vicente | $4.166/HH |
| OPROCSV | Mano de obra profesional CSV de costo directo | $3.000.000 / 168 HH |
| OGGCSV | Profesionales de Gastos Generales | Tarifa efectiva declarada en GG |
| OGGMMCSV | Mandos medios de Gastos Generales | Tarifa efectiva declarada en GG |
| OGGMICSV | Maestros indirectos de Gastos Generales | Tarifa efectiva declarada en GG |
| OGGJICSV | Jornales indirectos de Gastos Generales | Tarifa efectiva declarada en GG |
| OMACSUBxxx | Maestro subcontratado por oficio | $11.904/HH |
| OJOSUBxxx | Jornal subcontratado por oficio | $4.761/HH |

Sufijos de oficio: `MOL` moldaje, `ENF` enfierradura, `TAB` tabiquería, `REV` revestimientos, `CIE` cielos especiales, `CER` puertas/ventanas/muros cortina, `SAN` artefactos sanitarios, `EQU` equipos y artefactos, `CD` corrientes débiles, `ESP` especialidades y `GEN` general.

En corrientes débiles, la cuadrilla analizable por EETT utiliza la familia `OCD`, naturaleza `O` y dependencia `SUBCONTRATO`. Se consolida en un maestro especialista y un ayudante, con las tarifas subcontratadas vigentes de $11.904/HH y $4.761/HH. No se suman además cuadrillas San Vicente, eléctricas, de carpintería o de cielos dentro del mismo APU.

En climatización y ventilación, la cuadrilla analizable por EETT utiliza la familia `OCL`, naturaleza `O` y dependencia `SUBCONTRATO`. Se consolida en un maestro especialista y un ayudante, con las tarifas subcontratadas vigentes de $11.904/HH y $4.761/HH. No se suman además cuadrillas San Vicente, eléctricas, de carpintería o de montaje de equipos dentro del mismo APU.

## Distribución de respaldo

Las distribuciones porcentuales siguientes se aplican únicamente cuando la partida no tiene un APU desglosado verificable por EETT, o cuando existe una cotización/subcontrato externo sin desglose de recursos y HH. Si las EETT y el APU permiten analizar materiales, oficios, HH, equipos y rendimientos, se utiliza ese desglose real y sus dependencias; no se aplica un reparto porcentual adicional.

Cuando se abre un subcontrato integral con el respaldo 25 % / 60 % / 15 %, el 25 % es el costo total de mano de obra, incluidas las leyes sociales. Si se conserva `O%AUX = 0,35`, los recursos directos `O` representan `0,25 ÷ 1,35` del costo de origen y el auxiliar completa el 25 %. La transformación debe conservar exactamente el costo directo original.

En una cotización por unidad instalada sin HH declaradas, no se copian horas globales del proveedor ni se interpretan porcentajes como productividad física. La apertura de respaldo puede expresar el costo directo `O` como una cuadrilla equivalente 1 maestro + 1 ayudante: las HH iguales por unidad se obtienen dividiendo `0,25 ÷ 1,35 × precio instalado` por la suma de las tarifas horarias vigentes. El Inspector debe identificar estas HH como equivalentes económicos y mantener pendiente el rendimiento productivo hasta recibir el desglose o programa del subcontratista.

- Instalación de faenas: 100% CSV.
- Movimiento de tierra: 100% CSV.
- Hormigón: 100% CSV.
- Moldaje: 100% mano de obra subcontratada de moldaje.
- Fierro de construcción y enfierradura: 100% mano de obra subcontratada de enfierradura.
- Impermeabilización: subcontrato comercial; fuera de dotación HH.
- Tabiquería: 20% CSV + 80% mano de obra subcontratada.
- Revestimientos: 20% CSV + 80% mano de obra subcontratada.
- Sellos: 100% CSV.
- Cielos de volcanita: 100% CSV.
- Otros cielos: 20% CSV + 80% mano de obra subcontratada.
- Puertas, ventanas y muros cortina: 10% CSV + 90% mano de obra subcontratada.
- Colocación de artefactos sanitarios: 10% CSV + 90% mano de obra subcontratada.
- Colocación de otros equipos o artefactos: 10% CSV + 90% mano de obra subcontratada.
- Especialidades con cotización de subcontrato: subcontrato comercial, fuera de dotación HH.
- Especialidades sin cotización de subcontrato: 100% CSV.
- Gestión documental o tramitación administrativa: OPROCSV.
- Mano de obra declarada en Gastos Generales: `OGGCSV` para profesionales, `OGGMMCSV` para mandos medios, `OGGMICSV` para maestros indirectos —carpinteros, albañiles, yeseros, maestros de mantención y trazadores— y `OGGJICSV` para jornales indirectos. La clasificación automática puede corregirse manualmente en la vista Gastos Generales.

Cuando corresponde usar este respaldo, el APU conserva **una sola fila económica por recurso** —por ejemplo, un maestro y un ayudante— con dependencia `MIXTA`. La vista **Análisis M.O.** aplica el porcentaje a las HH y al costo de planificación; no se duplican filas del APU ni se reemplaza el precio presupuestado BC3. `MIXTA` no se utiliza en una partida que ya tenga dependencia y APU verificables.

## Informe

La vista **Análisis M.O.** debe mostrar código CodeAPU, destino, subdestino, código PRESTO de mano de obra, dependencia, oficio, tarifa, HH, meses-hombre, dotación equivalente, costo modelado, regla aplicada y partida de origen. El código CodeAPU respeta el orden tipo + destino + subdestino + partida + correlativo definido en `REGLA_NOMENCLATURA_RECURSOS.md`. Debe separar las HH excluidas por corresponder a subcontratos comerciales.

El encabezado debe identificar en tarjetas la dotación CSV, la dotación subcontratada, los hombres totales, el costo presupuestado de mano de obra y la suma monetaria del auxiliar `O%AUX`. El costo presupuestado es la suma de los recursos de naturaleza `O` del presupuesto BC3 e incluye `O%AUX` una sola vez; debe coincidir con Recursos y Cierre comercial. Las valorizaciones obtenidas como `HH × tarifa estándar` se usan para planificación y nunca sustituyen ni se rotulan como costo presupuestado.

El resumen principal de la vista y de los informes Excel/PDF comienza con una síntesis visible de seis totales: **HH CD**, **HH GG**, **HH total**, **costo CD**, **costo GG** y **costo total**. A continuación se presenta en dos tablas: **M.O. propia de la empresa oferente asignada al proyecto** (`OJOCSV`, `OMACSV`, `OPROCSV`, `OGGCSV`, `OGGMMCSV`, `OGGMICSV`, `OGGJICSV`) y **M.O. potencialmente subcontratada**. Los códigos históricos `CSV` no autorizan mostrar Constructora San Vicente como empresa de un proyecto distinto. Cada tabla agrupa por tipo y, cuando corresponda, especialidad, y muestra columnas separadas de **HH CD**, **HH GG**, **HH total**, **costo CD**, **costo GG** y **costo total**. El cierre muestra el **total general de HH y costo**. `O%AUX` se presenta como una línea separada, sin HH ni tipo de trabajador, y se suma una sola vez al total de costo directo. La mano de obra declarada en Gastos Generales usa el costo efectivo registrado en GG, incluyendo sus leyes sociales.

La vista y los informes Excel/PDF incorporan un histograma mensual de dotación con barras apiladas para **PROPIA** y **SUB**, el total visible sobre cada mes y una matriz numérica inmediatamente debajo con tres filas: **PROPIA**, **SUB** y **TOTAL**. PROPIA reúne la dotación de la empresa oferente asignada al proyecto, de costo directo y gastos generales; si el proyecto no tiene empresa asignada, se muestra **Empresa oferente no definida** y nunca se hereda el nombre de otro proyecto. SUB corresponde a la dotación potencialmente subcontratada. Todas las cantidades de personas se muestran redondeadas al entero superior.

La vista debe incorporar además:

- Histograma mensual apilado por empresa CD, empresa GG y subcontratos, con identificación explícita del mes de peak.
- Programación editable de inicio y término por partida.
- Resumen consolidado por imputación, dependencia, tipo y especialidad.
- Revisión de cargos indirectos: portero, paletero, jornal de patio, junior/estafeta, bodeguero, aseo y rigger/señalero. Una fila con cantidad cero no cuenta como considerada.
- Dimensionamiento por peak de artefactos sanitarios, casilleros y agua potable. Los artefactos siguen la tabla del artículo 23 del DS 594 y los casilleros el artículo 27.
- Superficies de comedor, vestuario y bodega como supuestos editables de planificación; no deben presentarse como mínimos legales si la norma no fija esos m².


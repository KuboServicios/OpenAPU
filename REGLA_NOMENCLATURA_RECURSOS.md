# Regla general de codificación de recursos CodeAPU / PRESTO

Versión de clasificación semántica: **CodeAPU v9**.

## 0. Análisis POLHEM interno

POLHEM es una herramienta de análisis interno, fuera de la operación visible de CodeAPU. Puede conservarse como antecedente de estudio y trazabilidad, pero no es una puerta de entrada, no bloquea la creación de APU y no condiciona la exportación PRESTO/BC3.

Cuando exista un análisis POLHEM previo, su orden conceptual puede orientar la revisión interna:

```text
PROYECTO -> ZONA -> SISTEMA -> ENTIDAD -> PARTIDA -> RECURSOS/APU
```

La partida conserva dos representaciones auditables:

- código POLHEM completo: `<PROYECTO>-<ZONA>-<SISTEMA>-<ENTIDAD>-<CORRELATIVO>`, por ejemplo `CREN-PAC-EST-MC-001`;
- alias de partida PRESTO, limitado a 13 caracteres y scoped al archivo del proyecto: `<ZONA><SISTEMA><ENTIDAD><CORRELATIVO>`, por ejemplo `PACESTMC001`.

Zona, sistema y entidad POLHEM deben provenir de antecedentes del proyecto o quedar pendientes; no se inventan desde el nombre de un recurso. Su ausencia no impide cerrar ni exportar el proyecto en CodeAPU.

## 1. Principio general

CodeAPU conserva dos códigos distintos porque identifican objetos diferentes:

1. **Código PRESTO de partida:** conserva el código contractual o el alias definido para el archivo; si existe alias POLHEM, se mantiene sólo como antecedente interno.
2. **Código PRESTO de recurso:** identifica el concepto maestro reutilizable M/O/E/S que se intercambia mediante BC3.
3. **Código CodeAPU histórico:** identifica la aparición o uso del recurso dentro de una partida y conserva compatibilidad y trazabilidad.

Un mismo recurso maestro puede aparecer en varias partidas con cantidades distintas. En ese caso conserva su código PRESTO y recibe un código CodeAPU diferente en cada relación.

El código de partida POLHEM y el código maestro de recurso identifican objetos distintos. Ninguno se deriva del otro. Los códigos históricos importados se conservan en `legacyPrestoCode` y no se sobrescriben silenciosamente.

## 2. Código contextual CodeAPU

### 2.0 Regla específica Cerro Renca: código PRESTO territorial

En el proyecto **Cerro Renca** (`1261-28-LR26` / `30484581`) el código PRESTO vigente de cada recurso no auxiliar se forma obligatoriamente desde lo macro a lo micro:

```text
<TIPO_RECURSO>-<DESTINO>-<SUBDESTINO>-<CORRELATIVO_RECURSO>
```

Ejemplo:

```text
M-Z02-S01-001
```

Se lee como **material · Camino A–B · movimiento de tierras · primer recurso del contexto**. El correlativo utiliza tres dígitos y se asigna por identidad de recurso —descripción, unidad y precio unitario— dentro de cada combinación tipo + destino + subdestino. Si el mismo recurso interviene en dos partidas del mismo contexto conserva el código PRESTO y ambas partidas permanecen visibles como usos.

Para Cerro Renca este código:

- se persiste en `prestoCode` y `code` y es el código que se visualiza y exporta;
- conserva el código PRESTO anterior en `legacyPrestoCode` para trazabilidad;
- conserva la familia semántica en `resourceFamilyCode`, separada del código territorial;
- no sustituye el código CodeAPU completo, que incorpora la partida y audita cada relación;
- no altera el código contractual de la partida.

Los destinos contractuales son `Z01` a `Z11`. `Z00` es una raíz técnica reservada exclusivamente para recursos transversales cuya partida no individualiza uno de los once sectores; no constituye un destino contractual adicional. Los subdestinos válidos son `S01` a `S18`.

Las filas auxiliares conservan `M%AUX`, `O%AUX` y `E%AUX`, porque esos códigos activan las fórmulas porcentuales de CodeAPU. Sus nombres canónicos son, respectivamente, `Pérdidas y consumibles`, `Leyes sociales` y `Combustible y mantenimiento`.

Esta política es específica del proyecto y se registra como `CERRO_RENCA_TERRITORIAL_V1`. Los demás proyectos continúan usando su catálogo maestro semántico salvo que cuenten con una regla territorial propia y explícitamente autorizada.

El código CodeAPU se forma obligatoriamente, siempre en este orden y con guiones visibles como separadores:

```text
<TIPO_RECURSO>-<DESTINO>-<SUBDESTINO>-<PARTIDA>-<CORRELATIVO_RELACION>
```

Ejemplo:

```text
O-IF-EL-1.1.2-01
```

Se lee como **mano de obra · instalación de faenas · instalación eléctrica · partida 1.1.2 · primera relación de ese contexto**.

### 2.1 Componentes obligatorios

| Componente | Campo lógico | Regla | Ejemplo |
|---|---|---|---|
| Tipo de recurso | `resourceType` | `M`, `O`, `E` o `S` | `O` |
| Destino | `destinationCode` | Sector principal del itemizado | `IF` |
| Subdestino | `subdestinationCode` | Proceso, especialidad o paquete de trabajo | `EL` |
| Partida | `partidaSourceCode` | Conserva el código visible `originalCode` de la partida | `1.1.2` |
| Correlativo | `relationCorrelative` | Dos dígitos, estable dentro del contexto | `01` |

El correlativo se asigna en orden de aparición dentro de cada combinación **tipo + destino + subdestino + partida**. Reordenar visualmente las filas no modifica un correlativo ya asignado. Si una relación se elimina, sus correlativos no se renumeran automáticamente.

### 2.2 Tipos de recurso

| Código | Naturaleza |
|---|---|
| `M` | Material |
| `O` | Mano de obra propia o subcontratada por oficio |
| `E` | Equipo o maquinaria propia o arrendada |
| `S` | Subcontrato comercial, suministro o paquete integral |

La dependencia no forma parte del tipo ni del código CodeAPU. Se conserva en un campo independiente:

- `Empresa` o nombre de la constructora para personal propio;
- `Subcontrato` para personal contratado por oficio;
- `Mixta` sólo como respaldo cuando una única fila económica de mano de obra, sin APU verificable o proveniente de un subcontrato externo sin desglose, se distribuye porcentualmente en la vista Análisis M.O.;
- `Compra`, `Arriendo`, `Propio` u otra condición aplicable para materiales y equipos.

Por tanto, un maestro eléctrico subcontratado sigue siendo `O`; solamente un alcance integral contratado como paquete se clasifica `S`.

### 2.3 Destinos

| Código | Destino del itemizado |
|---|---|
| `IF` | Instalación de Faenas |
| `OP` | Obras Previas |
| `OG` | Obra Gruesa |
| `TE` | Terminaciones |
| `ESSA` | Especialidad Sanitaria |
| `ESEL` | Especialidad Electricidad, corrientes débiles y luminarias |
| `ESCL` | Especialidad Climatización |
| `ESGC` | Especialidad Gases Clínicos |
| `ESOE` | Especialidad Obras Exteriores |
| `ESPJ` | Especialidad Paisajismo |
| `ESTV` | Especialidad Transporte Vertical |
| `ESSV` | Especialidad SERVIU |
| `OF` | Obras Finales, terminación y entrega final |
| `GG` | Gastos Generales |

El destino pertenece a la partida. Se obtiene primero de una asignación explícita del proyecto y, en su ausencia, se infiere desde el capítulo y su ruta jerárquica. Toda inferencia queda marcada como `inferida`; la revisión humana la cambia a `confirmada`.

### 2.4 Subdestinos

El subdestino expresa el proceso o paquete de trabajo en que se utiliza el recurso. Pertenece a la relación partida–recurso y no a la identidad del concepto maestro.

El catálogo es administrable y versionado. Su base inicial es:

| Código | Subdestino |
|---|---|
| `CT` | Contenedores e instalaciones modulares |
| `MT` | Movimiento de tierra |
| `HO` | Hormigones |
| `EN` | Enfierradura |
| `MO` | Montaje |
| `MD` | Moldajes |
| `AL` | Albañilería |
| `IM` | Impermeabilización |
| `TA` | Tabiquería |
| `CI` | Cielos |
| `RE` | Revestimientos |
| `PI` | Pintura |
| `PV` | Puertas y ventanas |
| `CU` | Cubiertas |
| `SA` | Sanitario |
| `EL` | Electricidad |
| `CL` | Climatización |
| `GC` | Gases clínicos |
| `FL` | Fletes y traslados |
| `OE` | Obras exteriores |
| `PJ` | Paisajismo |
| `TV` | Transporte vertical |
| `GE` | General o pendiente de clasificación |

La asignación automática de subdestino queda marcada como `inferida`; la selección del usuario queda como `confirmada`.

## 3. Código maestro PRESTO

El código PRESTO identifica el recurso maestro en el catálogo y en los registros `~C`/`~D` del BC3. Cuando CodeAPU crea un concepto nuevo, utiliza:

```text
<FAMILIA_RECURSO><CORRELATIVO_FAMILIA>
```

La familia recomendada es un prefijo semántico de tres caracteres cuyo primer carácter concuerda con la naturaleza:

```text
MCT01  Material · Contenedores · recurso 01
OKP01  Mano de obra · KUBO · Maestro primera · recurso 01
OEP01  Mano de obra · Eléctrica · Maestro primera · recurso 01
SIF01  Subcontrato · Instalación de faenas · recurso 01
```

Campos relacionados:

| Campo lógico | Función | Ejemplo |
|---|---|---|
| `resourceFamilyCode` | Familia de agrupación para informes PRESTO | `MCT` |
| `familyItemSequence` | Correlativo del concepto dentro de su familia | `01` |
| `prestoCode` | Código maestro completo | `MCT01` |

La familia describe **qué es el recurso**; el destino y subdestino describen **dónde y para qué se usa**. La familia PRESTO no forma parte del código CodeAPU.

La familia nunca se deduce solamente desde los tres primeros caracteres de un código técnico o histórico. Antes de asignarla se contrasta la descripción del recurso, la ruta completa de capítulo y subcapítulo, la descripción de la partida, el destino y el subdestino. Dos recursos consecutivos no pertenecen a una misma familia por compartir accidentalmente un prefijo.

La clasificación aplica esta jerarquía de evidencia:

1. la descripción técnica identifica qué es el recurso;
2. el capítulo, subcapítulo y partida resuelven exclusivamente términos ambiguos y paquetes de uso;
3. el destino y subdestino completan la clasificación cuando las descripciones no bastan;
4. una coincidencia parcial no prevalece sobre el sentido completo. Por ejemplo, `mueble despacho` es mobiliario interior y no un flete, y `válvula compuerta` no pertenece a puertas.

Una familia reconocida directamente desde el recurso nunca se reemplaza por el contexto. `MHO02 · Hormigón G05` conserva el mismo código maestro cuando se utiliza en obra gruesa, terminaciones, una cámara eléctrica o una partida SERVIU. Esos usos se distinguen mediante el código CodeAPU, no creando nuevos hormigones.

La familia `MHO` identifica el hormigón, concreto o mortero como recurso, no cualquier elemento que solamente los mencione. Por ejemplo, `Fierro estriado para hormigón` es `MEN`; un anclaje, poste, cámara, disco o revestimiento “para/de hormigón” conserva su propia familia o queda en `MGE` para revisión. El contexto no debe forzar una familia técnica sobre un recurso cuyo nombre describe otra cosa.

El catálogo maestro parte con una semilla estable solicitada para hormigones: `MHO01 · Hormigón pobre`, `MHO02 · Hormigón G05` y `MHO03 · Hormigón H05`. Los códigos reservados se mantienen aunque uno de esos conceptos todavía no aparezca en los proyectos actuales. Los demás correlativos se asignan sin reutilizar códigos existentes.

La identidad maestra tampoco contiene el precio. Los valores comerciales se conservan como historial fechado y como precio adoptado por cada proyecto. Antes de exportar un BC3, cada proyecto debe resolver qué precio utiliza para el código maestro, porque dentro de un mismo archivo PRESTO un código no puede declarar precios contradictorios.

Ejemplos mínimos de clasificación semántica:

| Familia | Significado | Ejemplo |
|---|---|---|
| `MAS` | Materiales · artefactos sanitarios | Artefacto sanitario y sus componentes directos de instalación, como fijación, desagüe o sifón |
| `MGR` | Materiales · grifería | Grifo, mezclador, fluxor, rociador o puesto de lavado del grupo de griferías |
| `MAB` | Materiales · accesorios de baño | Portarrollos, dispensador, barra de apoyo, jabonera, percha o mudador |
| `MBA` | Materiales · baldosas | Baldosa microvibrada |
| `MCC` | Materiales · cañerías de cobre | Cañería Cu L de 3/4" |
| `MPJ` | Materiales · paisajismo | Crespón de 2,00 m |
| `MRI` | Materiales · riego | Aspersor o accesorio de riego |
| `MPV` | Materiales · pavimentos | Adoquín o pavimento |
| `MPU` | Materiales · puertas y ventanas | Puerta, ventana o muro cortina |
| `MTA` | Materiales · tabiques | Perfil o placa de tabique |
| `MUI` | Materiales · muebles interiores | Mueble incorporado, adosado, mesón o locker interior |
| `MOE` | Materiales · mobiliario urbano | Escaño, bicicletero o basurero exterior |
| `MSÑ` | Materiales · señalética | Señalética general, de emergencia o accesible |
| `MTV` | Materiales · transporte vertical | Ascensores, montacamillas y componentes del sistema de transporte vertical |
| `OTV` | Mano de obra · transporte vertical | Instalación especializada subcontratada de ascensores o montacamillas |
| `ETV` | Equipos · transporte vertical | Equipos y herramientas especializados para montaje y puesta en marcha |
| `MPCI` | Materiales · protección contra incendio | Extintores, gabinetes y componentes directos del sistema contra incendio |
| `OPCI` | Mano de obra · protección contra incendio | Instalación y fijación especializada de extintores y gabinetes |
| `EPCI` | Equipos · protección contra incendio | Herramientas y equipos utilizados para instalación y puesta en servicio |
| `MREAS` | Materiales · residuos sólidos | Materiales y elementos directos del recinto o manejo de residuos sólidos, como pretiles de contención y armarios galvanizados |
| `MCD` | Materiales · corrientes débiles | Cableado, canalizaciones, equipos terminales y componentes directos de telecomunicaciones, seguridad y control |
| `OCD` | Mano de obra · corrientes débiles | Instalación, conexionado, certificación, programación y puesta en marcha especializada subcontratada |
| `ECD` | Equipos · corrientes débiles | Herramientas, instrumentos y equipos auxiliares para montaje, certificación y puesta en marcha |
| `MCL` | Materiales · climatización y ventilación | Materiales, equipos terminales y componentes directos del sistema de clima y ventilación |
| `OCL` | Mano de obra · climatización y ventilación | Montaje, conexión, regulación, pruebas y puesta en marcha especializada subcontratada |
| `ECL` | Equipos · climatización y ventilación | Herramientas, instrumentos y equipos auxiliares para montaje, pruebas y balanceo |
| `MTO` | Materiales · topografía | Replanteo, cerquillo, trazado y compactación inicial |
| `MCJ` | Materiales · cubrejuntas | Cubrejuntas de muro, piso, esquina o fachada |
| `MGM` | Materiales · guardamuros y protecciones | Guardamuros, cantoneras y protecciones |
| `MVE` | Materiales · ventanas, muros cortina y espejos | Ventana, muro cortina o espejo |
| `MEM` | Materiales · estructuras metálicas | Estructura, marco, plataforma, baranda o pasamanos metálico |
| `MAR` | Materiales · áridos | Arena, gravilla, ripio, estabilizado o base granular |
| `MPE` | Materiales · pavimentos exteriores no SERVIU | Calzada, vereda o pavimento exterior fuera del destino `ESSV` |
| `MCP` | Materiales · cierros perimetrales | Cierro metálico, albañilería, pandereta, bulldog, reja o murete del paquete de cierros |
| `MAO` | Materiales · aseo de obra | Aseo permanente o final de obra |
| `MCAP` | `CAP` · Capacitación | Capacitación y entrega formativa |
| `MCV` | Materiales · canaleta vehicular | Canaleta o rejilla de acceso vehicular |
| `MCS` | Materiales · cortina separadora | Cortina separadora y su sistema de rieles |
| `MSRV` | `SRV` · SERVIU | Materiales de partidas cuyo destino confirmado es `ESSV` |

`MSÑ` es la familia PRESTO solicitada para agrupar materiales de señalética. Conserva `M` como primer carácter —por tanto mantiene naturaleza material— y utiliza `SÑ` como abreviación semántica de señalética. Los códigos históricos `MSE` se mantienen legibles como antecedentes, pero los conceptos nuevos y las normalizaciones confirmadas de señalética utilizan `MSÑ`.

En el capítulo de circulaciones verticales se utilizan las familias PRESTO `MTV`, `OTV` y `ETV` para materiales, mano de obra y equipos, respectivamente. La mano de obra especializada conserva naturaleza `O` y dependencia `SUBCONTRATO`; no se transforma en un recurso integral `S`. El destino es `ESTV` y el subdestino `TV`.

En el capítulo de protección contra incendio se utilizan las familias PRESTO `MPCI`, `OPCI` y `EPCI` para materiales, mano de obra y equipos, respectivamente. La dependencia permanece en un campo separado y no se deduce desde la familia.

En el capítulo de residuos sólidos, todos los recursos de naturaleza material utilizan la familia PRESTO `MREAS`. La instrucción no cambia la naturaleza económica: la mano de obra propia de Constructora San Vicente permanece como `O`, utiliza los códigos maestros `OMA01` y `OJO01` y registra dependencia `KUBO`; los equipos permanecen como `E`.

En el capítulo de corrientes débiles todos los recursos se codifican como `MCD`, `OCD` o `ECD` según su naturaleza, con destino `ESEL` y subdestino `CD`. La mano de obra `OCD` es especializada, conserva naturaleza `O` y registra dependencia `SUBCONTRATO`. Un mismo APU no duplica esa cuadrilla con personal San Vicente, eléctrico o de cielos. Las canalizaciones de apoyo incluidas en el capítulo eléctrico 23 conservan sus familias eléctricas; esta separación evita mezclar el alcance funcional del capítulo 24 con la infraestructura física presupuestada en el capítulo 23.

En el capítulo de climatización y ventilación todos los recursos se codifican como `MCL`, `OCL` o `ECL`, con destino `ESCL` y subdestino `CL`. La mano de obra `OCL` conserva naturaleza `O` y dependencia `SUBCONTRATO`; se consolida en una sola cuadrilla especializada por APU. Cañerías, tableros, canalizaciones y controles contenidos en ese capítulo conservan la familia climática porque forman parte del sistema de clima. Los modelos diferentes no se fusionan bajo un mismo código maestro.

La apertura de una cotización instalada no crea identidades maestras nuevas por proveedor, precio o porcentaje. En ductos se reutiliza el material `MCL` por descripción y unidad, la cuadrilla `OCL` por oficio y los equipos `ECL` por función. Proveedor, fecha, valor instalado, distribución de respaldo y comparación histórica pertenecen a la relación y al Inspector; el precio no forma parte del código PRESTO.

`CAP` se conserva como rótulo ejecutivo. Mientras el concepto importado mantenga naturaleza `M`, su familia técnica es `MCAP`; un código `CAP` no tendría una naturaleza M/O/E/S válida. Si la capacitación se redefine posteriormente como servicio, el cambio de naturaleza debe aprobarse expresamente y no forma parte de una normalización de códigos neutra.

`SRV` se conserva como rótulo ejecutivo de la agrupación SERVIU. Para materiales, la familia técnica es `MSRV`; así se conserva la naturaleza `M` y el destino contextual `ESSV`. Mano de obra, equipos y subcontratos del mismo destino mantienen sus respectivas naturalezas y no reciben un código material.

La cañería de cobre conserva familia `MCC`; su uso sanitario, de riego, climatización o gases se expresa mediante `subdestinationCode` (`SA`, `PJ`, `CL` o `GC`) y mediante el destino de la partida. Si la descripción no basta para resolver el uso, se utiliza la especialidad de destino y la clasificación permanece `inferida` hasta revisión.

El identificador histórico importado se conserva en `legacyPrestoCode`. Cuando el usuario ordena una normalización, CodeAPU genera `prestoCode` semántico sin sobrescribir ese identificador histórico. Las colisiones de significado entre familias deben presentarse para decisión del usuario.

El código PRESTO debe ser único y compatible con el límite BC3 aplicable. Si requiere un identificador técnico de intercambio, CodeAPU conserva además el código maestro visible y la correspondencia auditable.

## 4. Ejemplos de doble codificación

| Recurso | Dependencia | Código CodeAPU | Familia PRESTO | Código PRESTO |
|---|---|---|---|---|
| Contenedor oficina | Arriendo | `M-IF-CT-1.1.2-01` | `MCT` | `MCT01` |
| Maestro primera de montaje | KUBO | `O-IF-MO-1.1.2-01` | `OKP` | `OKP01` |
| Maestro primera eléctrico | Subcontrato | `O-IF-EL-1.1.2-01` | `OEP` | `OEP01` |
| Maestro primera sanitario | Subcontrato | `O-IF-SA-1.1.2-01` | `OSP` | `OSP01` |
| Grúa de apoyo al montaje | Arriendo | `E-IF-MO-1.1.2-01` | `EIF` | `EIFGR50` |
| Flete integral de contenedores | Subcontrato | `S-IF-FL-1.1.2-01` | `SIF` | `SIF01` |

Si `MCT01` se reutiliza en otra partida, conserva el código PRESTO `MCT01`, pero su nuevo código CodeAPU incorpora el destino, subdestino, partida y correlativo correspondientes a esa relación.

## 5. Reglas operativas

1. El código maestro PRESTO pertenece al concepto; el código CodeAPU pertenece a la relación partida–recurso.
2. La cantidad, el factor y el rendimiento pertenecen a la relación y pueden variar sin crear un nuevo recurso maestro.
3. Los subanálisis reutilizados conservan su código PRESTO. Al expandirlos en informes, cada contribución recibe el código CodeAPU de la partida consumidora.
4. `M%AUX`, `O%AUX` y `E%AUX` se mantienen como códigos maestros internos de cálculo; cada aparición puede recibir un código CodeAPU contextual, sin cambiar su base ni su tasa.
5. Un cambio visual de orden nunca altera códigos, cantidades, precios o importes.
6. Ninguna vista puede reconstruir tipo, destino, subdestino, partida o dependencia mediante reglas alternativas.
7. Toda codificación inferida debe registrar origen, regla aplicada y estado de confirmación.

## 6. Presentación en CodeAPU

### Vista APU

La vista APU permite crear y revisar recursos sin exponer ni exigir POLHEM. La grilla muestra por defecto **tipo, código PRESTO maestro del recurso, descripción, unidad, cantidad/factor, precio unitario e importe**. Los antecedentes POLHEM, si existen, permanecen en la auditoría interna.

La descripción maestra usa un nombre natural y preferentemente no supera 40 caracteres para evitar saltos de línea en PRESTO e informes. Conserva el identificador comercial o tipológico mínimo —por ejemplo `VP1`, un diámetro, potencia, capacidad o modelo— y traslada el desarrollo de EETT a la nota y fuente del recurso. No se abrevia cortando palabras ni se reemplaza el nombre por una especificación completa.

El código PRESTO y el nombre deben ser semánticamente coherentes: la familia del código expresa la misma naturaleza técnica que el sustantivo principal de la descripción. Se eliminan colas genéricas como `calidad y dimensiones según EETT`, `según especificaciones técnicas` o equivalentes, porque no diferencian recursos. La descripción sí conserva espesor, diámetro, resistencia, especie, tipo, potencia, capacidad o modelo cuando esos atributos cambian la identidad técnica. La referencia a EETT queda en `resourceSource`, `resourceNotes` o el antecedente de la partida.

El código CodeAPU completo y sus componentes se consultan en el Inspector de la fila o mediante columnas opcionales. El usuario puede activar una vista ampliada de codificación, pero CodeAPU no repite permanentemente todos los componentes si ya están contenidos en el código.

### Vistas de análisis de recursos

Las vistas **Análisis M.O.**, **Análisis de Maquinaria**, **Análisis de Recursos** y **Flujo de Costos** utilizan las mismas dimensiones persistidas y ofrecen filtros combinables por:

- tipo `M/O/E/S`;
- dependencia;
- destino;
- subdestino;
- partida;
- familia PRESTO;
- código PRESTO;
- código CodeAPU;
- estado `inferido/confirmado`;
- fuente, cotización o validación cuando corresponda.

Los resultados pueden agruparse por familia PRESTO —por ejemplo `MCT`, `MAB`, `MTA`— para reproducir resúmenes ejecutivos, sin perder la trazabilidad al código CodeAPU y a la partida de origen.

## 7. Correspondencia inicial del proyecto RECREO

- Capítulo 1 → `IF`.
- Capítulo 2 → `OP`.
- Capítulos 3 y 4 → `OG`.
- Capítulos 5 al 15 y 18 → `TE`.
- Capítulo 16 → `ESSA`.
- Capítulo 17: 17.1 → `OP`; 17.2–17.9 → `ESSV`; 17.10–17.12 → `TE`; 17.13 → `ESPJ`.
- Capítulo 19 → `ESTV`.
- Capítulos 20 y 21 requieren confirmación del destino específico; no se usa un código genérico fuera del catálogo.
- Capítulos 22 y 26 → `ESSA`.
- Capítulos 23 y 24 → `ESEL`.
- Capítulo 25 → `ESCL`.
- Capítulo 27 → `ESGC`.
- Capítulo 28 → `OF`.

## 8. Catálogo maestro local de recursos

CodeAPU puede consolidar los recursos de todos sus proyectos en `catalogo_recursos_codeapu.json`. Este archivo alimenta la base maestra sin modificar los proyectos de origen y conserva cuatro capas separadas:

1. **Identidad técnica:** naturaleza + descripción técnica normalizada + unidad canónica. No contiene proyecto, precio, destino, subdestino ni partida.
2. **Código maestro PRESTO:** código estable y reutilizable de la forma familia + correlativo. Una vez asignado no se reutiliza para otro concepto.
3. **Historial de precios:** precio, moneda, fuente, fecha disponible y proyecto donde fue observado. Una variación de precio no crea por sí sola un recurso nuevo.
4. **Usos contextuales:** proyecto, partida, código CodeAPU, destino, subdestino, cantidad, factor y precio adoptado en esa relación.

Las normalizaciones seguras de identidad comprenden mayúsculas, tildes, puntuación, prefijos genéricos como `SUMINISTRO` y equivalencias expresas como `G5 = G05`. No se fusionan automáticamente recursos con atributos técnicos diferentes, aunque sus nombres sean parecidos.

Los subanálisis no se fusionan entre proyectos solamente por compartir descripción: su composición puede ser distinta. Los auxiliares `M%AUX`, `O%AUX` y `E%AUX` se conservan como conceptos especiales.

El catálogo registra advertencias cuando encuentra múltiples códigos actuales, varias familias candidatas, precios diferentes dentro de un mismo proyecto, texto de origen dañado o permanencia en una familia `GE`. Estas advertencias no impiden construir el JSON, pero deben resolverse antes de considerarlo un catálogo confirmado.

Un código PRESTO observado en un proyecto sólo se reutiliza automáticamente cuando su familia fue confirmada. Los códigos inferidos antiguos se conservan como antecedentes, pero no gobiernan la numeración inicial del catálogo. La opción técnica `--rebuild-codes` se reserva para corregir una catalogación inicial aún no confirmada; después de esa corrección, las ejecuciones normales conservan la numeración del JSON anterior.

El código de catálogo se asigna de manera determinista en la primera consolidación. Las actualizaciones futuras deben cargar el catálogo existente, preservar todos sus códigos y agregar correlativos nuevos; nunca deben regenerar o renumerar códigos históricos por cambiar el orden de los proyectos.


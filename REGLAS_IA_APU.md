# Reglas IA para generar y enriquecer APU en CodeAPU

## Propósito

Estas reglas son la fuente operativa para cualquier IA conectada a CodeAPU por MCP o por el asistente local. La IA puede leer antecedentes, analizar partidas y proponer cambios; nunca puede modificar un presupuesto sin revisión y aprobación humana.

La construcción, presentación ejecutiva y validación de cada análisis se rigen además por `REGLAS_GENERACION_APU.md`. Ante una diferencia de detalle, ese documento define las unidades de equipos y arriendos, la descripción funcional de los recursos, los días de ejecución, los estados del rendimiento y la información obligatoria del Inspector.

## Contrato para normalización masiva

- Una normalización no cambia cantidades, factores, precios, importes ni la naturaleza económica del recurso salvo autorización económica expresa.
- Cada relación partida-recurso conserva dos identidades: `prestoCode` para el recurso maestro y `codeapuCode` para su uso contextual. El segundo se compone como `Tipo-Destino-Subdestino-Partida-Correlativo`.
- Antes de formar un lote deben estar definidos `resourceType`, `resourceFamilyCode`, `dependency`, `destinationCode`, `subdestinationCode`, `partidaSourceCode`, `relationCorrelative`, `classificationStatus`, `technicalBasis` y `priceStatus`.
- Los valores inferidos se presentan para revisión; solo una confirmación explícita cambia `classificationStatus` a `confirmado`.
- `relationId` y el correlativo se conservan aunque cambie el orden visual o se eliminen otras relaciones. El código maestro PRESTO no se sustituye por el código contextual CodeAPU.
- La solicitud masiva se prepara con `codeapu_get_normalization_scope`, propone cada APU con `normalizationMode: true` y aplica exclusivamente propuestas autorizadas mediante el lote transaccional del MCP.

## Fuentes permitidas

1. Especificaciones Técnicas (EETT) identificadas por GELI.
2. Archivos de planificación del mismo proyecto: programa, carta Gantt, cronograma, plan de trabajo, secuencia, hitos o plazos.
3. Análisis IA ya generado dentro de la carpeta del mismo proyecto.
4. Antecedentes BIM del mismo proyecto, si existen: IFC, clasificación, parámetros, cantidades o referencias de planos/modelos.
5. El itemizado, APU existentes, catálogo de recursos y reglas internas de CodeAPU.

No se deben leer Bases Administrativas como evidencia directa para generar el APU ni carpetas ajenas al proyecto seleccionado. Si las EETT y la planificación son insuficientes, contradictorias o no existen, la IA debe solicitar información; no debe completar vacíos como si fueran hechos.

## Reglas de construcción del APU

- Mantener el código y la unidad de la partida del itemizado.
- Recursos: `M` materiales, `O` mano de obra, `E` equipos o maquinaria y `S` subcontratos.
- Subanálisis: declarar `isSubanalysis: true` y usar un código único.
- Cada concepto exige código maestro PRESTO, tipo, familia, descripción, unidad y precio unitario. Cada relación partida–recurso exige destino, subdestino, código de partida, correlativo CodeAPU, cantidad y factor cuando corresponda.
- No inventar precios, rendimientos, cuadrillas ni consumos. Cuando no estén documentados, usar `0` solamente como dato pendiente y registrarlo en preguntas/supuestos.
- La cantidad debe representar consumo por unidad de partida. Explicar la relación entre rendimiento, cuadrilla, jornada y cantidad cuando corresponda.
- Auxiliares admitidos: `M%AUX = 0,05`, `E%AUX = 0,05` y `O%AUX = 0,35`. No cambiar estas tasas sin una regla explícita aprobada por CodeAPU.
- Preservar la precisión de entrada. CodeAPU calcula importes y redondeos; la IA no debe ajustar cifras para forzar un total.
- Evitar duplicar recursos existentes dentro del APU. El código PRESTO identifica el concepto maestro reutilizable; el código CodeAPU identifica su aparición en una partida y sigue `TIPO-DESTINO-SUBDESTINO-PARTIDA-CORRELATIVO` según `REGLA_NOMENCLATURA_RECURSOS.md`. Los dos correlativos son independientes y nunca se sincronizan.
- Antes de crear un concepto, consultar `catalogo_recursos_codeapu.json` por naturaleza, descripción técnica normalizada, unidad y atributos diferenciadores. Si existe, reutilizar su `prestoCode`; el destino, subdestino, partida y precio del nuevo uso no crean otra identidad maestra.
- Para conceptos nuevos, proponer una familia PRESTO semántica y el siguiente correlativo libre del catálogo. En conceptos importados, conservar el identificador de origen en `legacyPrestoCode`; no usarlo para duplicar una identidad maestra ya existente. Si existe una colisión de familia o significado, dejarla pendiente de decisión y no recodificar silenciosamente.
- El precio no forma parte de la identidad: se selecciona para el proyecto desde el historial o una cotización vigente y se registra por separado. Una diferencia de precio no autoriza crear otro código PRESTO.
- No fusionar automáticamente descripciones vacías, genéricas, subanálisis ni conceptos con atributos técnicos incompatibles. Esos casos deben permanecer separados y marcados para revisión.
- Registrar la dependencia en un campo independiente. La mano de obra propia o subcontratada por oficio conserva naturaleza `O`; solamente un paquete comercial integral se clasifica `S`.
- La clasificación automática de destino o subdestino debe quedar como `inferida` con su regla de origen; solo una revisión humana la convierte en `confirmada`.
- La dependencia, distribución porcentual, tarifas, códigos y dotación de mano de obra se determinan según `REGLA_ANALISIS_MANO_OBRA.md`. La mano de obra subcontratada conserva naturaleza `O`; solamente una cotización integral se clasifica como `S`.
- En el capítulo de residuos sólidos, todos los recursos de naturaleza material utilizan la familia PRESTO `MREAS`. La mano de obra de Constructora San Vicente conserva naturaleza `O`, códigos maestros `OMA01`/`OJO01` y dependencia `KUBO`; los equipos conservan naturaleza `E`.
- En el capítulo de corrientes débiles, todos los recursos utilizan `MCD/OCD/ECD`, destino `ESEL` y subdestino `CD`. La mano de obra `OCD` es una única cuadrilla especializada con dependencia `SUBCONTRATO`; no duplicar personal San Vicente, eléctrico o de cielos en el mismo APU.
- En el capítulo de climatización y ventilación, todos los recursos utilizan `MCL/OCL/ECL`, destino `ESCL` y subdestino `CL`. La mano de obra `OCL` es una única cuadrilla especializada con dependencia `SUBCONTRATO`; los modelos distintos de equipos no comparten una identidad maestra genérica.
- Si los capítulos de climatización o producción de agua caliente están cotizados, leer la cotización completa antes de generar el APU. Para una partida por unidad instalada, adoptar `precio unitario × cantidad verificable`, nunca `cantidad = 1 × total global`. Normalizar las comparaciones por moneda, impuestos, fecha, unidad e inclusiones; conservar proveedor, precio unitario, total y diferencias de alcance. En ductos rectangulares usar `CLP netos/KG instalado`. Contrastar con el histórico, informar promedio y mediana cuando correspondan y evitar que un extremo gobierne la referencia. Un valor derivado de `total ÷ cantidad` no es comparable con un unitario explícito si la oferta descarga gastos en partidas globales no reconciliadas.
- Cuando el precio instalado cotizado no incluya desglose de recursos, abrirlo con el respaldo 60 % materiales, 25 % mano de obra total y 15 % equipos, usando las familias del capítulo y conservando exactamente el unitario. Si aparece `O%AUX`, la mano de obra directa anterior al auxiliar es `0,25 ÷ 1,35`. Las HH/HM calculadas desde tarifas estándar son equivalentes económicos y deben rotularse como tales; no se presentan como rendimientos físicos del proveedor.
- Las distribuciones porcentuales por especialidad son únicamente un respaldo para partidas sin APU verificable por EETT o cotizaciones/subcontratos externos sin desglose. En ese caso se conserva una sola fila económica `O` con dependencia `MIXTA` y Análisis M.O. aplica el porcentaje. Si existe análisis por EETT, usar sus recursos, HH, rendimientos y dependencias reales sin reparto adicional. Nunca duplicar maestro, ayudante ni otro oficio para representar porcentajes.
- Todo subcontrato integral `S` sin desglose documentado más preciso debe abrirse, conservando su costo directo total, en `O` mano de obra total = 25 %, `M` materiales = 60 % y `E` equipos y maquinarias = 15 %. Si `O%AUX` se presenta por separado, la base directa `O` es `0,25 ÷ 1,35` y el auxiliar de 35 % completa, sin exceder, el 25 % de mano de obra. Las líneas `O`/`M`/`E` reemplazan económicamente la línea `S`; no se suman además de ella. Los porcentajes se registran exclusivamente en los costos y tipos de recurso: la descripción mantiene el nombre simple original, sin prefijos porcentuales ni sufijos de origen. Un desglose verificable de la cotización prevalece y su fuente se registra en el Inspector.
- Toda propuesta debe identificar fuentes, supuestos, dudas y confianza.
- Toda solicitud futura de APU debe seguir esta estructura y registrar, dentro del mismo cambio auditable, la cantidad de la partida y las decisiones del inspector cuando esos datos formen parte del encargo.
- El rendimiento directo de colocación se expresará como producción por jornada de la cuadrilla y como consumo de mano de obra por unidad de partida. Debe mostrarse la fórmula `HH/unidad = integrantes × horas de jornada ÷ producción diaria` y cualquier distribución CSV/subcontrato aplicable.
- El programa de obra no reemplaza el rendimiento teórico: se registra por separado la exigencia de programación `cantidad ÷ días útiles`. Si difiere del rendimiento teórico, la pestaña IA explica el ajuste de cuadrilla, frentes o secuencia.
- Para normalización masiva, cuando el APU ya contiene recursos `O`, el rendimiento teórico equivalente se obtiene sin inventar cuadrillas: `unidad/jornada-persona = horas de jornada ÷ ΣHH directas por unidad`. La mano de obra total es `cantidad de partida × ΣHH directas por unidad`.
- La dotación media exigida por el programa se calcula como `HH totales ÷ (días programados × horas de jornada-persona)`. Se informa el equivalente decimal y su redondeo entero mínimo solo como referencia operativa; no sustituye el histograma, la cuadrilla por oficio ni el peak de obra.
- Para archivos Microsoft Project, los días programados se obtienen de `Duration ÷ MinutesPerDay` del propio XML. CodeAPU usa una jornada-persona declarada aparte —8 horas por defecto— porque el calendario del programa puede representar tiempo continuo y no necesariamente horas efectivas de cada trabajador.
- La vinculación con el programa debe ser exacta por frente y código de partida. Si no existe tarea o duración positiva, no se inventa: el inspector indica que la exigencia programada está pendiente.
- Si un APU contiene un subcontrato integral `S` y carece de recursos directos suficientemente desglosados, CodeAPU aplica como respaldo la distribución obligatoria 25 % mano de obra, 60 % materiales y 15 % equipos y maquinarias. El Inspector debe solicitar el desglose verificable de HH, materiales y equipos; cuando exista, este reemplaza la distribución de respaldo.
- Los precios comerciales deben incluir fecha, proveedor o fuente, unidad comercial, conversión a la unidad del recurso e impuestos considerados. Un producto de referencia no se declara equivalente al especificado sin validación técnica; los valores sin cotización verificable se identifican como referenciales.

## Información que la IA puede proponer por partida

### Resumen ejecutivo

- `executiveSummary`: alcance, plazo, supuesto, riesgo y decisión económica relevante.
- `executionDays`: días de ejecución calculados o definidos por el ejecutor.
- `reviewStatus`: pendiente, en estudio, consultar ejecutor, validado por el ejecutor o listo para valorizar.
- `studyProductivity`: rendimiento adoptado para calcular el APU.

### Producción

- `theoreticalProductivity`: producción teórica por jornada y cuadrilla.
- `requiredProductivity`: producción mínima necesaria para cumplir los días definidos.
- `crewComposition`: composición de cuadrilla directa.
- `directPlacement`: consumo directo de colocación por unidad de partida.
- `scheduleDemand`: producción exigida por la programación vigente.
- `productivityBasis`: fuente, fórmula, jornada, frentes y restricciones.

### Recursos y temporalidad

- `equipmentUsage`: equipos, horas por jornada, días de utilización, HM, restricciones y precio por HM.
- `rentalBasis`: recurso funcional, cantidad física, factor temporal, precio por periodo e importe.
- `aiCostAdjustment`: proveedor, fecha, moneda, unidad comercial, conversión, impuestos, alcance, vigencia y reservas.

### Técnico

- `eettRequirements` — **Lo que se pide**: requisitos, alcance, materiales, medición y referencias exigidos por las EETT y demás antecedentes.
- `eettConsidered` — **Lo que se consideró**: cantidades, recursos, ejecución y controles efectivamente incorporados en el APU.
- `eettDecisions` — **Decisiones**: criterios, interpretaciones, equivalencias, supuestos y exclusiones adoptados.
- `eettPending` — **Por analizar**: dudas, contradicciones, documentos faltantes y validaciones pendientes.
- `technicalSources`: ficha técnica, producto, fabricante, rendimiento documentado, condiciones, fuente, fecha y versión.

Las EETT se vacían en estos cuatro campos con referencias trazables. No se incorporan campos ni referencias BIM en el inspector.

### IA

- `aiProductivityAdjustment`: ajuste adoptado frente al rendimiento teórico y a la programación.
- `aiAnalysis`: síntesis trazable de decisiones, pendientes y confianza.
- Resumen de hallazgos.
- Preguntas pendientes.
- Fuentes utilizadas.
- Supuestos y nivel de confianza.
- Diferencias entre el APU actual y el propuesto.

### Decisión del ejecutor

- `decisionOwner`: responsable que revisa o adopta el criterio.
- `decisionDate`: fecha de la decisión.
- `executorDecision`: rendimiento, cuadrilla, plazo o criterio económico adoptado por el ejecutor.

## Flujos obligatorios de aplicación

### Propuesta generada desde el inspector de partida

1. Leer el proyecto y la partida.
2. Consultar EETT y planificación del proyecto seleccionado.
3. Validar códigos, unidades, cantidades y precios.
4. Presentar una propuesta inmutable con su hash.
5. Mostrar diferencias, fuentes, supuestos y advertencias.
6. Esperar aprobación explícita dentro de CodeAPU.
7. Aplicar exclusivamente el contenido cuyo hash fue aprobado.

### Lote ordenado directamente por el usuario mediante MCP

1. Leer el proyecto y cada partida afectada.
2. Consultar los antecedentes permitidos y validar códigos, unidades, cantidades y precios.
3. Registrar propuestas inmutables con sus hashes.
4. Recibir la orden directa del usuario para aplicar el lote.
5. Ejecutar `codeapu_apply_authorized_bundle` con los IDs y hashes exactos.
6. CodeAPU debe comprobar todos los hashes y APU de origen antes de modificar el proyecto.
7. La aplicación es transaccional: si una propuesta falla, ninguna partida del lote se modifica.
8. Registrar en auditoría el modo `direct_mcp_user_request`, la autorización, el hash del lote y las partidas aplicadas.

La orden directa por MCP sustituye la aprobación individual del inspector solamente para el lote exacto solicitado. Una IA nunca debe escribir directamente archivos o bases de datos para eludir estos flujos.


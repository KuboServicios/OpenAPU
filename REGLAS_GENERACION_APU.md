# Reglas de generación y revisión de APU en CodeAPU

## 1. Propósito y lector objetivo

El APU es desarrollado por un ingeniero de estudio de propuestas para que pueda ser revisado por el Gerente General, el ejecutor de la obra y otros tomadores de decisiones.

Cada análisis debe ser:

- claro y conciso;
- técnicamente verificable;
- trazable en cantidades, factores, rendimientos, precios y fuentes;
- suficiente para reconocer los supuestos y riesgos que pueden cambiar el costo o el plazo.

La lectura ejecutiva debe permitir responder, sin reconstruir el análisis: qué se ejecutará, cuánto se ejecutará, en cuántos días, con qué cuadrilla y maquinaria, qué se arrendará, durante cuánto tiempo y qué decisión respalda el rendimiento adoptado.

## 2. Estructura mínima del APU

- Se mantiene el código y la unidad de la partida definidos en el itemizado.
- Cada recurso se clasifica como `M` material, `O` mano de obra, `E` equipo o maquinaria, `S` subcontrato o subanálisis identificado expresamente.
- Cada recurso exige código maestro PRESTO, tipo, familia, descripción, unidad y precio unitario.
- Cada relación partida–recurso exige destino, subdestino, código de partida, correlativo CodeAPU, cantidad y, cuando corresponda, factor.
- La dependencia —empresa, subcontrato, propio, compra o arriendo— se conserva como dimensión independiente y nunca se deduce únicamente desde `M/O/E/S`.
- Cuando corresponda, también debe declarar un factor de consumo o temporalidad.
- La cantidad pertenece a la relación entre la partida y el recurso; un mismo recurso puede tener cantidades diferentes en APU distintos.
- El importe se calcula con los valores declarados, sin ajustes artificiales para forzar el total.

```text
Importe del recurso = cantidad × factor × precio unitario
```

Cuando no exista factor independiente, se considera `factor = 1`.

### 2.1. Doble codificación obligatoria

Todo recurso de un APU conserva dos identificadores:

- **Código PRESTO:** identifica el concepto maestro reutilizable y se intercambia mediante BC3.
- **Código CodeAPU:** identifica la relación entre ese concepto y una partida específica.

La cantidad, el factor y el rendimiento pertenecen a la relación. Por ello, un mismo código PRESTO puede participar en varios APU y recibir un código CodeAPU diferente en cada uno.

El código CodeAPU se forma en este orden, sin intercambiar ni omitir componentes:

```text
<TIPO_RECURSO>-<DESTINO>-<SUBDESTINO>-<PARTIDA>-<CORRELATIVO_RELACION>
```

1. **Tipo de recurso:** `M` material, `O` mano de obra, `E` equipo o maquinaria y `S` subcontrato integral.
2. **Destino:** se utiliza exclusivamente uno de los códigos de la tabla siguiente.
3. **Subdestino:** identifica el proceso, especialidad o paquete de trabajo según el catálogo versionado de `REGLA_NOMENCLATURA_RECURSOS.md`.
4. **Partida:** conserva el código visible `originalCode` de la partida del itemizado.
5. **Correlativo de relación:** siempre se informa con dos dígitos (`01`, `02`, `03`, etc.) y se asigna en orden estable dentro de cada combinación tipo + destino + subdestino + partida.

| Código | Sector del itemizado |
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
| `OF` | Obras Finales |
| `GG` | Gastos Generales |

Ejemplo contextual CodeAPU:

```text
O-IF-EL-1.1.2-01
```

Se lee como `O` mano de obra + `IF` instalación de faenas + `EL` instalación eléctrica + partida `1.1.2` + relación correlativa `01`.

El código PRESTO se forma, para conceptos nuevos, con una familia semántica y un correlativo propio:

```text
<FAMILIA_RECURSO><CORRELATIVO_FAMILIA>
```

Ejemplos: `MCT01` contenedor oficina, `OKP01` maestro primera KUBO y `OEP01` maestro primera eléctrico. Los códigos importados se conservan; CodeAPU no recodifica silenciosamente conceptos históricos. Los dos correlativos son independientes y nunca se sincronizan.

La dependencia se registra separadamente y no cambia el tipo del recurso. La mano de obra propia y la mano de obra subcontratada por oficio son `O`; solamente un paquete comercial integral es `S`.

Para circulaciones verticales, los recursos utilizan las familias PRESTO `MTV` para materiales, `OTV` para mano de obra y `ETV` para equipos. La mano de obra de transporte vertical se registra como naturaleza `O` con dependencia `SUBCONTRATO`, destino `ESTV` y subdestino `TV`.

Para protección contra incendio, los recursos utilizan las familias PRESTO `MPCI` para materiales, `OPCI` para mano de obra y `EPCI` para equipos. Estas familias se aplican a extintores, gabinetes y su instalación sin alterar la naturaleza ni la dependencia del recurso.

Para residuos sólidos, todos los recursos de naturaleza material utilizan la familia PRESTO `MREAS`. La mano de obra de Constructora San Vicente conserva naturaleza `O`, códigos maestros `OMA01`/`OJO01` y dependencia `KUBO`; los equipos conservan naturaleza `E`.

Para instalaciones sanitarias, las cañerías de cobre y PVC, bombas, llaves de paso, nichos, soportes, accesorios e instalación utilizan las familias PRESTO `MSA`, `OSA` y `ESA`. La mano de obra `OSA` corresponde al subcontrato sanitario autorizado y usa dependencia `SUBCONTRATO`; no se reemplaza por mano de obra propia de San Vicente. El estanque de agua potable y su sala de máquinas constituyen el subcontrato independiente SEA y usan exclusivamente `MSEA`, `OSEA` y `ESEA`.

El movimiento de tierra dentro del capítulo sanitario no hereda `MSA/OSA/ESA`: conserva materiales de áridos y rellenos, mano de obra propia `OMA01`/`OJO01` con dependencia `KUBO`, y maquinaria de movimiento de tierra con dependencia `ARRIENDO`, reutilizando identidades y tarifas vigentes del capítulo 2. Esta excepción comprende excavaciones, rellenos, camas y capas de áridos, retiro de excedentes y transporte a botadero.

Para instalaciones eléctricas, los materiales, la mano de obra y los equipos se agrupan respectivamente en `MEL`, `OEL` y `EEL`. La mano de obra `OEL` es subcontratada y usa dependencia `SUBCONTRATO`. El alcance incluye tramitación de empalme, acometidas y postes, tableros, conductores y cableado, canalizaciones eléctricas y de corrientes débiles, mallas de puesta a tierra, ensayos, capacitación, colocación de luminarias y postes, enchufes, centros de luz, interruptores y arranques eléctricos para equipos de clima, gases clínicos y sanitarios.

Para el capítulo de corrientes débiles, todos los recursos se agrupan por naturaleza en `MCD`, `OCD` y `ECD`, con destino `ESEL` y subdestino técnico `CD`. Comprende el enlace y emplazamiento de telecomunicaciones, cableado estructurado y puntos IP, Wi-Fi, racks, detección de incendios, sonorización normal y de emergencia, CCTV, intrusión, control de accesos, turnomático y equipos complementarios. La mano de obra especializada `OCD` conserva naturaleza `O` y dependencia `SUBCONTRATO`; cada APU utiliza una sola cuadrilla sin duplicarla con mano de obra San Vicente o de otra especialidad. Las canalizaciones de corrientes débiles incluidas físicamente dentro del capítulo eléctrico 23 siguen `MEL/OEL/EEL`; los sistemas funcionales del capítulo de corrientes débiles usan `MCD/OCD/ECD`.

Para el capítulo de climatización y ventilación, todos los recursos se agrupan por naturaleza en `MCL`, `OCL` y `ECL`, con destino `ESCL` y subdestino `CL`. La regla comprende ductos y accesorios, redes hidráulicas, válvulas, cañerías y aislaciones, rejillas y difusores, chiller y bombas de calor, fan-coils, manejadoras, equipos split y VRV, ventiladores, estanques, bombas, tableros y controles propios de clima, condensados, pruebas y puesta en marcha. La mano de obra `OCL` es especializada y usa dependencia `SUBCONTRATO`; cada APU conserva una sola cuadrilla de climatización y no suma además mano de obra San Vicente, eléctrica, de carpintería o de equipos. Los modelos técnicamente diferentes deben tener identidades maestras distintas aunque compartan un nombre genérico.

Cuando climatización o producción de agua caliente dispongan de cotizaciones por unidad instalada, el APU se construye desde ese precio unitario cotizado y no desde el total global del proveedor. Cada oferta se normaliza a pesos netos por la misma unidad, alcance, fecha e impuestos; se conservan proveedor, cantidad, precio unitario, total, inclusiones y exclusiones. Un total dividido por su cantidad sólo es comparable si el alcance instalado es equivalente. Si la cotización muestra un precio unitario redondeado que no reproduce exactamente el total, CodeAPU usa el precio unitario explícito para el APU y registra la diferencia de redondeo en el Inspector.

Para controlar cotizaciones infladas, el valor histórico se utiliza como contraste y no se suma al precio actual. Con tres o más valores comparables se informa la mediana, además del promedio, para que un extremo no arrastre la referencia; con dos valores se muestran ambos y no se selecciona silenciosamente uno sin una decisión documentada. Una oferta que omite el precio unitario o distribuye gastos generales, fletes, leyes sociales u otros costos en partidas separadas no se mezcla en el promedio instalado hasta reconciliar su alcance.

En ductos rectangulares medidos en `KG`, la unidad de comparación es `CLP netos/KG instalado`: la cantidad de la partida es el peso verificable de la cotización o cubicación y el precio del APU es pesos por kilogramo instalado. Nunca se usa `cantidad = 1` con el total completo del paquete como precio por kilogramo. Fittings, soportes, sellos, aislación y accesorios que tengan partidas propias no se duplican dentro del kilogramo instalado. Si el proveedor no entrega desglose de recursos, el precio instalado se abre económicamente en `MCL/OCL/ECL` mediante el respaldo 60 % / 25 % / 15 %, conservando exactamente el precio unitario adoptado; `O%AUX` queda absorbido dentro del 25 % de mano de obra. Las HH y HM resultantes de dividir esos componentes por tarifas estándar son equivalentes económicos de estudio, no rendimientos físicos declarados por el proveedor.

El grupo electrógeno constituye el subdestino técnico `GEN` y utiliza exclusivamente `MGEN`, `OGEN` y `EGEN` para materiales, mano de obra y equipos. Comprende el generador, transferencia automática, combustible inicial, montaje, accesorios y obras anexas propias del conjunto. El movimiento de tierra de instalaciones eléctricas no hereda `MEL/OEL/EEL`: reutiliza mano de obra propia y maquinaria de movimiento de tierra del capítulo 2, con sus dependencias y tarifas vigentes.

Sólo cuando no existe un APU desglosado verificable por EETT o se dispone de una cotización/subcontrato externo sin desglose, puede aplicarse una distribución porcentual de respaldo: se registra una sola fila económica `O` con dependencia `MIXTA` y el reparto se realiza en **Análisis M.O.** Nunca se duplican maestro, ayudante u otro oficio dentro del APU para representar porcentajes. Cuando el APU puede analizarse por EETT, se usan sus recursos, HH, rendimientos y dependencias reales sin reparto porcentual adicional.

Esta codificación alimenta las vistas **Análisis M.O.**, **Análisis de Maquinaria**, **Análisis de Recursos** y **Flujo de Costos**. Todas deben usar el mismo tipo, destino, subdestino, partida, dependencia, familia y códigos persistidos; no pueden reclasificar el recurso con catálogos u órdenes diferentes. Si una referencia PRESTO supera el límite BC3, el exportador utiliza un identificador técnico compatible y conserva la correspondencia auditable con el código maestro visible.

### 2.2. Procedimiento de codificación al generar un APU

Para cada línea, CodeAPU o la IA debe:

1. buscar y reutilizar el concepto maestro PRESTO cuando coincidan naturaleza, descripción técnica normalizada, unidad y atributos diferenciadores; el precio se selecciona después desde su historial o se registra como una nueva observación;
2. crear un concepto maestro nuevo solamente si no existe uno equivalente;
3. validar o asignar `resourceType` y `resourceFamilyCode`;
4. heredar o confirmar el `destinationCode` de la partida;
5. asignar el `subdestinationCode` correspondiente al proceso;
6. conservar `partidaSourceCode` desde el itemizado;
7. asignar un `relationCorrelative` estable;
8. generar el `codeapuCode` sin utilizarlo como sustituto del `prestoCode`;
9. registrar la dependencia, el origen de la clasificación y su estado `inferido` o `confirmado`.

La clasificación semántica usa la descripción técnica del recurso como evidencia principal. La ruta de capítulo y subcapítulo, la partida, el destino y el subdestino actúan como contexto para resolver ambigüedades. Una palabra aislada nunca debe cambiar la naturaleza del concepto: `mueble despacho` se clasifica como mueble interior, no como flete; el capítulo `Mobiliario urbano` conduce a `MOE`; y el capítulo `Señalética` conduce a la familia material `MSÑ`.

Si falta destino, subdestino, familia o dependencia, el APU puede guardarse como borrador, pero queda pendiente de codificación y no se considera listo para cierre o exportación definitiva.

### 2.3. Orden obligatorio de presentación de recursos

Las filas del APU se presentan y guardan en una secuencia estable por naturaleza:

```text
M → M%AUX → O → O%AUX → E → E%AUX → S
```

Primero se muestran los recursos directos de cada naturaleza y, cuando existe, su auxiliar inmediatamente después. Dentro de cada grupo se conserva el orden relativo de incorporación. Los subanálisis se ubican según la naturaleza de su código. Reordenar filas nunca modifica códigos, unidades, cantidades, precios ni importes.

## 3. Descripción autosuficiente del recurso

La descripción debe ser breve, reconocible y suficientemente específica para distinguir la función del recurso. No debe reemplazar el detalle técnico ni contener el desarrollo completo del cálculo.

Para la presentación e intercambio con PRESTO se adopta como criterio preferente un máximo de **40 caracteres**. No es un límite técnico absoluto, pero superarlo requiere una razón de identificación que no pueda trasladarse al Inspector sin perder claridad. El nombre conserva el sustantivo funcional y el identificador mínimo necesario para cotizar —por ejemplo `SUM. VENTANA VP1`, diámetro, potencia, capacidad o modelo—. Composición, espesores, prestaciones, herrajes, equivalencias, inclusiones y demás exigencias de EETT se conservan en `resourceNotes`, `resourceSource` y el Inspector, no en una descripción extensa que produzca saltos de línea en los informes.

Un mismo código PRESTO utiliza un solo nombre maestro en todas sus relaciones. Las abreviaciones deben ser legibles y estables; no se corta una palabra ni se elimina el identificador que diferencia el recurso.

La naturaleza, el porcentaje de distribución, el costo y la trazabilidad del origen pertenecen a sus campos de cálculo o al Inspector; no se anteponen ni se agregan a la descripción. Por ejemplo, al abrir un subcontrato no se escriben textos como `60% MATERIALES`, `25% MANO DE OBRA`, `15% EQUIPOS Y MAQUINARIAS` ni `ORIGEN ...` en el nombre del recurso.

Para contenedores y recintos modulares se utiliza:

```text
CONTENEDOR + FUNCIÓN
```

Ejemplos válidos:

- `CONTENEDOR VESTUARIO`;
- `CONTENEDOR OFICINA`;
- `CONTENEDOR COMEDOR`;
- `CONTENEDOR BODEGA`;
- `CONTENEDOR SANITARIO`;
- `CONTENEDOR BAÑO MUJERES`;
- `CONTENEDOR PRIMEROS AUXILIOS`.

No son descripciones suficientes:

- `CONTENEDOR`;
- `CONTENEDORES VARIOS`;
- `INSTALACIÓN DE FAENA`;
- `VESTIDORES Y SANITARIOS`.

Recursos con funciones diferentes se registran en líneas independientes, aunque tengan el mismo proveedor o precio.

## 4. Nota explicativa en el Inspector de partida

La descripción identifica el recurso y su función. La nota del Inspector registra el supuesto que permite auditarlo:

- cantidad física;
- factor temporal o de consumo;
- capacidad o configuración;
- alcance incluido;
- exclusiones;
- fuente y fecha del precio;
- decisión o validación pendiente.

Ejemplo:

```text
Descripción: CONTENEDOR OFICINA
Unidad: UN
Cantidad: 5
Factor: 10 meses
Nota: Se arriendan 5 contenedores para oficinas de la constructora e ITO durante
10 meses. El precio corresponde al arriendo mensual por unidad. Conexiones y
habilitación se valorizan separadamente.
```

## 5. Equipos y maquinaria operativa

Los equipos y maquinarias que producen trabajo en la ejecución se expresan siempre en:

```text
HM = hora máquina
```

La cantidad de horas máquina debe ser verificable:

```text
HM = número de equipos × horas por jornada × días de utilización
```

Ejemplo:

```text
1 camión grúa × 8 horas/jornada × 5 jornadas = 40 HM
```

El Inspector debe registrar cantidad de equipos, horas por jornada, días de utilización, rendimiento, restricciones y fuente del precio por HM.

Esta regla comprende maquinaria propia y maquinaria o equipos operativos arrendados. No se deben utilizar unidades `MES-EQ`, `DÍA-EQ` ni precios globales para ocultar las horas consideradas.

## 6. Arriendos de instalaciones temporales

Los elementos arrendados que no producen trabajo mecánico —contenedores, oficinas, baños, vestidores, comedores, bodegas u otros recintos temporales— no se expresan en HM.

Se registra separadamente:

- descripción funcional;
- unidad física;
- cantidad física;
- factor temporal;
- unidad y precio del periodo de arriendo.

Ejemplo:

```text
Descripción: CONTENEDOR VESTUARIO
Unidad: UN
Cantidad: 4
Factor: 10 meses
Precio unitario: arriendo mensual de una unidad
Importe: 4 × 10 × precio mensual
```

La cantidad física no se reemplaza por `40 MES-EQ`. CodeAPU conserva `4 UN` en Cantidad y `10 meses` en Factor / Rendimiento como datos diferenciados. El Inspector explica la unidad y base del factor; el coeficiente efectivo de costo se calcula como `cantidad × factor`.

## 7. Días de ejecución por partida

Cada partida debe informar sus días estimados de ejecución en el Inspector.

Cuando existe rendimiento conocido:

```text
Días de ejecución = cantidad de la partida ÷ producción diaria adoptada
```

La producción diaria debe indicar:

- rendimiento unitario;
- composición y número de integrantes de la cuadrilla;
- horas efectivas de jornada;
- cantidad de equipos;
- número de frentes;
- restricciones relevantes.

Los días del programa y los días calculados por rendimiento se conservan por separado. Una diferencia debe explicarse mediante ajuste de cuadrilla, equipos, frentes o secuencia.

## 8. Rendimiento no disponible

Cuando los antecedentes no permitan calcular el rendimiento o la duración:

1. La IA identifica el dato faltante y no lo presenta como hecho.
2. La IA formula una consulta concreta al ejecutor.
3. El ejecutor define el rendimiento o escribe directamente los días de ejecución en el Inspector.
4. Si se definen los días, la IA calcula el rendimiento mínimo necesario.
5. La IA contrasta ese rendimiento con la cuadrilla, maquinaria, jornada, frentes y restricciones consideradas.

```text
Rendimiento necesario = cantidad de la partida ÷ días definidos
```

La IA propone, calcula y advierte. La decisión del ejecutor determina el rendimiento de estudio.

## 9. Fichas técnicas y rendimientos documentados

Cuando una ficha técnica de material, producto o sistema informe un rendimiento, la IA debe guardarlo en el Inspector con:

- fabricante y producto;
- rendimiento declarado y su unidad;
- condiciones de aplicación;
- documento, fuente, fecha o versión;
- restricciones y observaciones.

El rendimiento de ficha es una referencia técnica. No reemplaza automáticamente el rendimiento de estudio, porque este último debe considerar condiciones reales de obra, cuadrilla, experiencia, pérdidas, interferencias y decisiones del ejecutor.

## 10. Estados del rendimiento

CodeAPU debe distinguir expresamente:

- **Rendimiento técnico:** informado por fabricante, EETT, manual u otra fuente documental.
- **Rendimiento propuesto por IA:** calculado desde los antecedentes disponibles.
- **Rendimiento necesario:** producción mínima para cumplir los días definidos.
- **Rendimiento de estudio:** valor adoptado por decisión del ejecutor para valorizar el APU.

El APU se calcula con el rendimiento de estudio. El Inspector conserva los demás valores y explica sus diferencias.

## 11. Mano de obra y rendimiento de colocación

La mano de obra se expresa en HH por unidad de partida:

```text
HH/unidad = integrantes × horas de jornada ÷ producción diaria de la cuadrilla
```

La cantidad total de mano de obra es:

```text
HH totales = cantidad de la partida × HH/unidad
```

La cuadrilla, distribución CSV/subcontrato, oficio, tarifa, jornada y ventana programada se rigen por `REGLA_ANALISIS_MANO_OBRA.md`.

## 12. Precios y fuentes comerciales

Los precios comerciales deben registrar:

- proveedor o fuente;
- fecha;
- moneda;
- unidad comercial;
- conversión a la unidad del recurso;
- impuestos considerados;
- inclusiones y exclusiones;
- vigencia, cuando sea conocida.

No se inventan precios. Un valor sin cotización verificable se identifica como referencial y queda pendiente de confirmación.

## 13. Uso de partidas globales y subanálisis

La unidad `GL` se reserva para una actividad única o un paquete realmente indivisible. No debe utilizarse para agrupar recursos de distinta función o esconder cantidad, duración y precio unitario.

Un monto global relevante debe estar respaldado por:

- recursos desglosados dentro del APU; o
- un subanálisis auditable.

La habilitación, transporte, instalación, conexión y retiro se separan cuando representan alcances o decisiones económicas distintas.

### 13.1. Desglose obligatorio de subcontratos

Todo subcontrato que no disponga de un desglose documentado más preciso debe abrirse en recursos del APU conservando exactamente su costo directo total:

```text
Mano de obra = 0,25 × costo directo del subcontrato
Materiales = 0,60 × costo directo del subcontrato
Equipos y maquinarias = 0,15 × costo directo del subcontrato
Total = 1,00 × costo directo del subcontrato
```

El 25 % de mano de obra es el costo total de esa naturaleza, incluidas las leyes sociales. Cuando `O%AUX` se muestra como línea separada, la suma de los recursos directos `O` se obtiene como `0,25 ÷ 1,35` del costo del subcontrato y `O%AUX = 0,35 × Σ(O)`. Así, `Σ(O) + O%AUX` sigue siendo exactamente 25 % y el desglose no aumenta el presupuesto.

La distribución se registra en líneas de naturaleza `O`, `M` y `E`, respectivamente. El recurso integral `S` se reemplaza por estas líneas y no se suma además de ellas. Si existe un desglose contractual o una cotización verificable con proporciones más precisas, se utiliza ese detalle y se registra su fuente en el Inspector.

La regla 25 % / 60 % / 15 % es obligatoria como distribución de respaldo para generar, completar o normalizar un APU sin desglose adecuado de subcontratos. Los auxiliares visibles se absorben dentro del porcentaje de su naturaleza y nunca pueden producir dobles cargos.

## 14. Auxiliares y dobles cargos

Los auxiliares admitidos son:

```text
M%AUX = 0,05 × suma de importes de materiales
E%AUX = 0,05 × suma de importes de equipos
O%AUX = 0,35 × suma de importes de mano de obra
```

Antes de aplicarlos se verifica que no dupliquen costos incorporados directamente, por ejemplo mantenimiento, consumibles, desgaste, leyes sociales o pérdidas ya incluidas en el precio.

Las tasas no se modifican sin una regla explícita aprobada por CodeAPU.

## 15. Información ejecutiva obligatoria por partida

El Inspector debe presentar, como mínimo:

| Campo | Contenido |
|---|---|
| Alcance | Qué incluye y qué excluye la partida |
| Cantidad | Metrado presupuestado |
| Días de ejecución | Duración calculada o definida |
| Rendimiento de estudio | Producción adoptada por jornada |
| Cuadrilla | Composición, dependencia y cantidad de personas |
| Equipos | Tipo, cantidad, HM y días de utilización |
| Arriendos temporales | Cantidad física y factor temporal |
| Fuentes | EETT, planificación, ficha técnica o cotización |
| Decisión del ejecutor | Criterio finalmente adoptado |
| Riesgos y pendientes | Información que puede modificar costo o plazo |

La navegación de partidas pertenece al Inspector y no ocupa una columna permanente de la mesa APU. Debe ofrecer búsqueda por código o descripción y avance anterior/siguiente según el orden del presupuesto.

Al seleccionar un recurso, el Inspector cambia al contexto de esa relación y presenta, sin alterar la descripción maestra:

- código maestro PRESTO y código contextual CodeAPU;
- tipo, familia, dependencia, destino, subdestino y estado de definición;
- cantidad física, factor, coeficiente efectivo, precio unitario e importe;
- utilización del mismo código maestro en otros APU;
- fuente, antecedente y nota técnica o comercial.

La ficha de intercambio para PRESTO, GPLA o GELI reúne la partida, sus recursos y la información enriquecida del Inspector. La preparación o copia de la ficha no autoriza cambios económicos: la exportación o aplicación definitiva conserva las validaciones, hashes y autorizaciones establecidas por CodeAPU.

## 16. Validación antes de valorizar

Un APU se considera completo solamente cuando:

- contiene los recursos necesarios para ejecutar el alcance;
- cada recurso posee un código maestro PRESTO único o una referencia maestra importada preservada;
- cada relación posee código CodeAPU con tipo, destino, subdestino, partida y correlativo;
- la dependencia y el estado inferido/confirmado de la clasificación están registrados;
- separa recursos de funciones diferentes;
- sus cantidades y factores son verificables;
- los equipos y maquinarias operativas están expresados en HM;
- los arriendos temporales identifican cantidad física y periodo;
- informa días de ejecución y rendimiento de estudio;
- identifica fuentes, supuestos, decisiones y pendientes;
- los precios tienen respaldo o están marcados como referenciales;
- los montos globales relevantes están desglosados o respaldados por subanálisis;
- no existen recursos duplicados ni dobles cargos;
- la suma de recursos y auxiliares coincide con el precio calculado por CodeAPU.

## 17. Autoridad y auditoría

- La IA no reemplaza al ingeniero de estudio ni al ejecutor.
- La IA no convierte antecedentes insuficientes en hechos.
- La decisión del ejecutor prevalece para definir el rendimiento de estudio y debe quedar registrada en el Inspector.
- Toda propuesta identifica fuentes, supuestos, dudas y nivel de confianza.
- Todo cambio económico conserva propuesta, hash, autorización y trazabilidad según `MCP_CODEX.md`.
- Las reglas de normalización, nomenclatura, mano de obra, flujo de costos y compatibilidad BC3 continúan vigentes y complementan este documento.


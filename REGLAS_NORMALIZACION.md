# Reglas permanentes de normalización CodeAPU

Estas reglas se aplican a todos los proyectos. Ninguna depende del nombre PETRINOVIC ni de una ruta específica.

## 1. Selección de hoja

CodeAPU evalúa todas las hojas y elige la de mayor calidad estructural. La puntuación considera:

- cantidad de conceptos reconocibles;
- filas con Unidad informada;
- códigos jerárquicos;
- cantidad de columnas identificadas.

Una hoja resumen con muchas descripciones, pero sin unidades ni jerarquía, no debe desplazar al itemizado detallado.

## 2. Detección flexible de encabezados

Se inspeccionan las primeras 200 filas. Se eliminan tildes, signos y espacios al comparar encabezados, por lo que se reconocen variantes como:

- `PARTIDA`, `P A R T I D A`, `DESCRIPCIÓN`, `DESIGNACIÓN`, `DENOMINACIÓN`, `CONCEPTO`, `ACTIVIDAD`;
- `UNIDAD`, `UNI.`, `UNID.`, `UND.`, `U.M.`;
- `CANTIDAD`, `CANT.`, `METRADO`, `CUBICACIÓN`;
- `P. UNITARIO`, `UNIT.`, `PU`, `VALOR UNITARIO`;
- `TOTAL`, `PARCIAL`, `IMPORTE`, `MONTO`.

Además de tildes, signos y espacios, se toleran errores tipográficos menores en
encabezados suficientemente descriptivos, por ejemplo `DESGINACIÓN`, `CÓDGO` o
`PRECIO UNTARIO`. Esta aproximación no se aplica a abreviaturas cortas como `N`,
`PU` o `UM`, para evitar asociaciones falsas entre columnas.

## 3. Clasificación funcional

La columna Unidad es la regla maestra:

- Unidad vacía: capítulo o subcapítulo.
- Unidad informada: partida gestionable mediante APU.

La presencia de hijos no sustituye esta regla.

## 4. Códigos y jerarquía

Los separadores `/`, espacios entre bloques y puntos se normalizan como niveles:

- `AP 1/1.1.` → `AP.1.1.1`;
- `AC1  6.2.4` → `AC1.6.2.4`.

También se reconoce la jerarquía compacta letra-número cuando el capítulo padre
existe en el itemizado: `B > B1 > B1.1`, `C > C2 > C2.1` o `AP > AP1 > AP1.1`.
Un código hermano como `A10` no se interpreta como hijo de `A1`.

Las filas del tipo `SIGLA "AP" ...` pueden crear el capítulo raíz `AP`. Si ya existe un concepto real con ese código, la leyenda no se duplica.

Cuando falta un padre se crea un capítulo sintético inmediatamente antes de su primer descendiente. Los códigos repetidos se conservan mediante un identificador BC3 único; nunca se elimina silenciosamente una fila válida.

## 5. Varios proyectos dentro del mismo itemizado

Si la hoja seleccionada contiene varias obras, edificios, torres, sectores, sedes o itemizados consecutivos, CodeAPU no los mezcla bajo una sola raíz. Detecta los rótulos de separación y crea una raíz de nivel 1 por cada proyecto.

- Cada raíz conserva únicamente sus capítulos, subcapítulos y partidas.
- Los códigos que se reinician en otro proyecto reciben un identificador interno independiente, pero mantienen visible el código original.
- El orden de las raíces es el mismo orden en que aparecen en el archivo.
- El BC3 usa `ROOT##` como contenedor técnico y crea conceptos `PRJ001#`, `PRJ002#`, etc.; en la interfaz el usuario ve directamente cada proyecto como nivel 1.
- Si no existe evidencia suficiente de más de una obra, se mantiene una sola raíz para evitar separaciones falsas.

La detección usa rótulos como `ITEMIZADO ...`, `OBRA: ...`, `EDIFICIO ...`, `TORRE ...`, `SEDE ...`, `SECTOR ...` o `CONTINGENCIA 1 ...`. No depende de nombres particulares.

## 6. Filas que no son conceptos

Se excluyen:

- encabezados repetidos dentro de la misma hoja;
- filas `Subtotal`, `Sub Total` o `Total parcial`;
- cuadros resumen posteriores al itemizado;
- IVA, utilidades o totales sin código y sin Unidad;
- filas completamente vacías.

Los Gastos Generales y el Cierre Comercial se gestionan en sus módulos propios.
El inicio de ese bloque se detecta en toda la fila, aunque las celdas combinadas
o desplazadas sitúen `TOTAL COSTO DIRECTO`, Gastos Generales, utilidad o IVA en
una columna distinta de Descripción.

## 7. Orden y profundidad

Se conserva el orden normalizado de lectura. Los padres sintéticos se insertan antes del primer hijo. La interfaz permite hasta diez niveles para no recortar itemizados técnicos profundos; los subanálisis se muestran debajo de su partida.

## 8. Importación bidireccional BC3

Los archivos `.bc3` se aceptan como fuente, además de Excel y CSV. CodeAPU:

- detecta automáticamente codificación UTF-8 o Windows-1252;
- lee conceptos `~C` y descomposiciones `~D` de FIEBDC-3;
- reconoce `ROOT##` y `PRJ001#`, `PRJ002#`, etc. como raíces exportadas por CodeAPU;
- si el BC3 proviene de otra aplicación, obtiene sus raíces desde el grafo padre–hijo y crea identificadores internos `PRJnnn`;
- aplica también en BC3 la regla `Unidad vacía = capítulo` y `Unidad informada = partida/APU`;
- detiene el árbol presupuestario en cada partida y convierte su descomposición `~D` en recursos editables;
- identifica como subanálisis todo recurso que posea su propia descomposición y la reconstruye recursivamente;
- conserva códigos de naturaleza `M`, `O`, `E`, `S` y auxiliares `M%AUX`, `E%AUX`, `O%AUX`;
- interpreta el punto como separador decimal FIEBDC-3 incluso cuando existen exactamente tres decimales (`217.855` no significa `217855`);
- conserva por separado factor y rendimiento de cada registro `~D` y calcula su cantidad efectiva como `factor × rendimiento`, según la terna `código \ factor \ rendimiento` usada por Presto;
- conserva como líneas independientes los recursos repetidos dentro de un mismo análisis y suma sus incidencias;
- considera autoritativo el precio declarado en `~C` mientras el APU importado no sea editado; después de una edición usa el precio recalculado por CodeAPU;
- preserva el orden de las relaciones declarado por el archivo.

El ciclo admitido es `CodeAPU → BC3 → Presto → BC3 → CodeAPU`. El alcance actual recupera estructura y análisis mediante `~C`/`~D`; registros de medición `~M`, textos extensos, archivos adjuntos y presentación propia de Presto no forman parte del editor CodeAPU.

## 9. Diagnóstico y evolución

Las instalaciones sanitarias se normalizan por alcance: `MSA/OSA/ESA` para redes, cañerías, bombas, válvulas, nichos, soportes, accesorios e instalación; `MSEA/OSEA/ESEA` para el subcontrato independiente del estanque de agua potable. El movimiento de tierra relacionado mantiene sus familias técnicas de áridos, mano de obra y maquinaria, sin absorberse en las familias sanitarias.

Las instalaciones eléctricas se normalizan con `MEL/OEL/EEL`; esto incluye empalmes, acometidas, tableros, cableados y conductores, canalizaciones eléctricas y de corrientes débiles, puesta a tierra, ensayos, capacitación, artefactos y luminarias, postes y arranques para otras especialidades. `OEL` identifica mano de obra subcontratada. El grupo electrógeno usa el subdestino `GEN` y se separa como `MGEN/OGEN/EGEN`, mientras que sus excavaciones, rellenos y camas de arena conservan la clasificación de movimiento de tierra y las tarifas de maquinaria validadas en el capítulo 2.

El capítulo de corrientes débiles se normaliza íntegramente con `MCD/OCD/ECD`, destino `ESEL` y subdestino `CD`. El alcance comprende telecomunicaciones, cableado estructurado, puntos IP, Wi-Fi, racks, detección, audio, CCTV, intrusión, control de accesos, turnomático y equipos complementarios. `OCD` identifica una única cuadrilla especializada con dependencia `SUBCONTRATO`; no se acumula con cuadrillas San Vicente, eléctricas o de cielos. La excepción de alcance es física, no textual: las canalizaciones para corrientes débiles incluidas en el capítulo eléctrico 23 permanecen `MEL/OEL/EEL`.

El capítulo de climatización y ventilación se normaliza íntegramente con `MCL/OCL/ECL`, destino `ESCL` y subdestino `CL`, incluso cuando el recurso sea una cañería de cobre, tablero, canalización eléctrica o control que forme parte del paquete de clima. `OCL` identifica una única cuadrilla especializada con dependencia `SUBCONTRATO`; no se acumula con cuadrillas San Vicente ni de otra especialidad. Los splits, cassettes, condensadoras y demás equipos con modelos distintos se mantienen como identidades maestras separadas.

Una partida cotizada por unidad instalada se normaliza desde `precio unitario × cantidad verificable`; no se conserva el total global como precio unitario con cantidad uno. En ductos rectangulares la unidad comparable es `CLP netos/KG instalado`. La fuente debe conservar cantidad, precio unitario visible, total, fecha, proveedor e inclusiones. Si el unitario está vacío, `total ÷ cantidad` se registra como valor derivado y no se combina con unitarios explícitos mientras existan gastos globales o diferencias de alcance sin reconciliar. Cuando el precio instalado no trae desglose, su apertura `M/O/E` aplica 60 % / 25 % / 15 % sin alterar el total, y los recursos siguen las familias técnicas del capítulo (`MCL/OCL/ECL` en climatización).

Cada importación informa:

- hoja seleccionada y fila de encabezado;
- columnas detectadas;
- conceptos fuente y conceptos finales;
- padres reconstruidos;
- duplicados preservados;
- códigos remapeados para BC3.
- cantidad y nombres de proyectos raíz detectados.

Para un BC3 el diagnóstico informa codificación, conceptos `~C`, cantidad de APU/subanálisis, recursos y raíces detectadas.

Cuando aparezca un caso nuevo, debe agregarse como regla genérica y como prueba de regresión. La corrección no puede depender del nombre del archivo, proyecto, mandante o ruta local.


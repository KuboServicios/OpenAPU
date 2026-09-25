# Regla de Análisis Flujo Costos CodeAPU

## Objetivo

La vista **Análisis Flujo Costos** es un flujo de caja de estudio. Permite identificar el mes de mayor gasto y entender qué destino macro y qué tipo de recurso explican ese peak.

## Fuentes incorporadas

- `M`: materiales de Costo Directo.
- `S`: subcontratos de Costo Directo.
- `O`: mano de obra de Costo Directo y dotación declarada en Gastos Generales.
- `E`: maquinaria de Costo Directo y equipos/maquinaria declarados en Gastos Generales.

El costo directo de `M`, `S` y `E` proviene del APU reconciliado con el total de cada partida. La mano de obra usa su costo de origen para conservar la consistencia económica del presupuesto. `GG` se presenta como destino propio.

## Distribución mensual

1. El plazo corresponde a los meses definidos en Gastos Generales; si no existe, usa el plazo del proyecto y, en último término, 18 meses.
2. Cada partida reutiliza la ventana inicio/término editable de Análisis de Mano de Obra.
3. Si una partida no fue programada, CodeAPU propone una ventana según su sector: IF, OP, OG, TE, ESSA, ESEL, ESCL, ESGC, ESOE, ESPJ, ESTV, ESSV, OF o GG.
4. El costo de cada recurso se reparte uniformemente entre los meses activos de su partida.
5. Las filas de GG respetan su fase y meses declarados.
6. El peak es el mayor total mensual de las cuatro naturalezas incorporadas.

## Lectura del resultado

- El histograma vertical usa el plazo en el eje X y apila los destinos en cada mes.
- El histograma horizontal compara el costo total por destino en el eje Y y separa M, S, O y E.
- La tabla mensual es el respaldo accesible y exportable: muestra cada destino, total del mes y acumulado.
- La composición M/S/O/E permite verificar que mano de obra y maquinaria estén incorporadas.
- La naturaleza y el sector se reciben desde la codificación contextual del APU; Flujo de Costos no mantiene un catálogo alternativo.

## Alcance

Es una curva de estudio, no un flujo financiero contractual. No incorpora anticipos, desfases de compra o pago, estados de pago, retenciones, impuestos, financiamiento ni condiciones comerciales de proveedores. Para convertirla en flujo financiero deben agregarse esas reglas y un programa de obra validado.


# Hoja de ruta del validador

Dónde encaja este repositorio dentro del proyecto general
([`proyecto.md`](proyecto.md)) y qué falta para que llegue ahí.

El validador corresponde a la fase 2 del proyecto y se construye antes que el
modelo generativo a propósito: no depende de él, se puede medir solo y ya
produce resultados publicables.

## Cinco usos, no uno

El uso obvio es el bucle de reparación. Es el tercero por valor.

### 1. Saneado del dataset

Prerrequisito del entrenamiento, no mejora posterior. Si 23 de cada 30 patrones
que GarmentCode aprueba tienen defectos, las 115.000 prendas de GarmentCodeData
contienen esos mismos defectos, y cualquier modelo entrenado sobre ellas los
aprende como construcción correcta.

Pasar `validar()` sobre el corpus corrige el problema en la raíz, una sola vez,
antes de gastar una hora de GPU. Es el uso con mayor retorno y el único que hay
que hacer *antes* de la fase 3.

**Pero no filtrando por "cero errores", como decía este plan.** Medido sobre
3.450 patrones, ese filtro deja el 10,5% del corpus y hunde las prendas de
cuerpo entero del 60,3% al 31,5%: castiga el tamaño, porque los errores se
acumulan con el número de costuras mientras la tasa *por costura* es plana. El
filtro correcto descarta solo los defectos geométricos duros — conserva el 79,6%
y la composición casi intacta. El desarrollo está en
[`hallazgos-corpus.md`](hallazgos-corpus.md).

**La herramienta está construida**: `hilvan CORPUS/ --lote` recorre
un directorio de patrones, mide y saca el manifiesto de los sanos. A ~10 ms por
patrón, las 115.000 prendas son unos 20 minutos en un núcleo.

**Hecho sobre un lote**: 3.450 patrones medidos, resultados en
[`hallazgos-corpus.md`](hallazgos-corpus.md). El 20,4% tiene un defecto
geométrico duro y solo el 10,5% pasa limpio.

**Lo que sigue bloqueado es republicar el subconjunto filtrado**, no medirlo:
GarmentCodeData no declara licencia en ninguna parte. Medir y publicar
estadísticas es uso de investigación con cita; redistribuir un subconjunto es
otra cosa y hay que preguntar a los autores.

### 2. Compuerta antes de la simulación 3D

La simulación física cuesta GPU y minutos; validar cuesta milisegundos. Con una
tasa de defectos del 77%, simular sin filtrar es gastar la mayor parte del
cómputo en patrones que no se pueden coser.

Es la ganancia más inmediata y no exige tocar el modelo: `resumen(h)["validado"]`
delante de la llamada al simulador.

### 3. Bucle de reparación en inferencia

```
prompt → modelo → patrón → validar → ¿errores? → hallazgos al modelo → reintentar
```

El mismo patrón que un agente de código con el compilador. `para_modelo()` ya
emite lo que hace falta: código, severidad, referencia exacta (`panel`/`borde`/
`costura`) y valores medidos, para que el modelo corrija ese punto sin
regenerar la prenda.

**Límite según la representación.** Con la opción B (parámetros, tipo
ChatGarment) la corrección es indirecta — el modelo mueve un parámetro y espera
que el efecto geométrico sea el pedido. Con geometría directa (AIpparel) puede
mover el vértice concreto que el hallazgo señala. La opción C híbrida existe en
buena parte por esto.

### 4. Señal de entrenamiento

`resumen()` devuelve un escalar determinista, barato y denso — las tres
propiedades que una recompensa basada en simulación no tiene:

- **Rejection sampling:** generar *n*, quedarse con los válidos, reentrenar.
- **Recompensa RL:** errores ponderados por severidad, en negativo.
- **Optimización fina:** más adelante, con simulación diferenciable.

### 5. Métrica pública

Hoy no existe forma de comparar ChatGarment con AIpparel en algo que importe a
un patronista. "% de patrones manufacturables sobre un set fijo" es exactamente
eso, y este validador es reproducible, determinista y no necesita GPU.

Publicar el número para los modelos existentes es probablemente el camino más
corto a que el repositorio se use, y una carta de presentación para las
conversaciones con patronistas.

**Hecho para el primer modelo**: AIpparel, 0 de 200 patrones manufacturables
sobre 100 prendas del corpus pedidas por imagen y por texto, con el 88% de las
costuras sin cerrar contra el 33% del ground truth. Está en
[`hallazgos-aipparel.md`](hallazgos-aipparel.md), con los scripts en
[`research/`](../research/).

Lo que falta para que sea una *comparación* y no una medida suelta es el segundo
modelo. ChatGarment genera parámetros, no geometría, así que hay que pasarlos por
GarmentCode antes de validar — y entonces el número mide la pareja
modelo+GarmentCode, no el modelo.

**Esa asimetría ya no es una advertencia, es una cota.** Pasando los parámetros
verdaderos de las mismas 100 prendas por GarmentCodeRC, el sintetizador reproduce
el veredicto del patrón publicado en 99 de 100 y mueve la manufacturabilidad del
12% al 13%. Un modelo de parámetros se puntúa contra esa columna, no contra el
corpus. Está en [`hallazgos-sintetizador.md`](hallazgos-sintetizador.md).

La cadena entera —etiquetas, ChatGarment, GarmentCodeRC, validador— está montada
y probada de punta a punta sobre 3 prendas; lo que falta son unas 4 horas de GPU
para las 100 por cada modalidad.

## Qué falta construir

Ordenado por dependencias: lo de arriba no necesita nada externo.

### Cerrar el nivel 1

| Trabajo | Nota |
| --- | --- |
| ~~Continuidad en los cruces~~ | ✅ Hecho. `quiebre_en_cruce`, con `esquina_de_diseno` para las esquinas dibujadas |
| ~~Campo `finish`~~ | ✅ Hecho. `acabado_no_declarado` (aviso) y `acabado_incongruente` (error); no sube a error porque no hay disparador geométrico |
| ~~Declarar la orientación de la costura~~ | ✅ Hecho. `orient`, con `orientacion_dudosa` cuando contradice el contorno libre |
| ~~Secuencia de ensamblaje~~ | ✅ Parcial. `costuras_en_redondo` mide el coste; la accesibilidad real necesita 3D y baja al nivel 2 |

El nivel 1 está cerrado salvo la accesibilidad del ensamblaje, que necesita 3D
y baja al nivel 2. Las tres extensiones de formato — `ease`, `finish`,
`orient` — están implementadas y probadas en las dos direcciones.

Lo siguiente con más retorno no es más cobertura, sino usar lo que ya hay:
sanear GarmentCodeData (uso 1) y publicar la métrica (uso 5).

### Excepción por hallazgo

Hoy una violación se acepta moviendo el umbral global o apagando la
comprobación entera. Falta poder decir "esta esquina de 9° en este panel es
deliberada" sin desactivar el resto.

Mecánicamente es lo mismo que `ease`: una declaración localizada en el propio
patrón que el validador contrasta contra la geometría. Para prendas básicas no
hace falta; para alta costura es la pieza que convierte el linter en
herramienta de diseño.

### Calibración

Los umbrales de `Limites` son razonables pero no están contrastados contra
telas físicas. Requiere un patronista, y por eso esa conversación es el paso de
plazo más largo del proyecto entero.

Hasta entonces, los números por defecto son una hipótesis explícita, no un
hecho.

### Nivel 2

La mitad geométrica está hecha: las aberturas de la prenda montada se miden y,
con `orient` declarado y un `Cuerpo`, se juzgan. No necesita simulación ni GPU,
así que corre sobre cada muestra como los niveles anteriores.

La mitad física — drapeado, tensión, poses, accesibilidad — está planificada y
deliberadamente sin construir: [`nivel2-simulado.md`](nivel2-simulado.md).

## Fuera de alcance de este repositorio

El nivel 3 (consumo de tela, marcado, escalado de tallas) y el nivel 4 (rúbrica
de patronistas, toiles) pertenecen al proyecto, no al paquete. `excede_ancho_rollo`
es el único chequeo de producción aquí y está en el nivel 0 porque es una
comprobación geométrica de un panel suelto, no de un marcado completo.

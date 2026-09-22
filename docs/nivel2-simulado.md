# Nivel 2 simulado: plan

La mitad geométrica del nivel 2 está implementada ([`nivel2.py`](../src/hilvan/nivel2.py)):
mide las aberturas de la prenda montada y juzga si el cuerpo pasa. Este
documento define lo que falta — todo lo que necesita física — y en qué
condiciones tiene sentido construirlo.

No está implementado a propósito. Las razones están abajo y conviene leerlas
antes de empezar, porque la principal no es técnica.

## Qué cubriría

| Comprobación | Qué detecta |
| --- | --- |
| Interpenetración | La tela se atraviesa a sí misma o al cuerpo |
| Estabilidad | La simulación converge; la prenda no se cae ni explota |
| Mapas de tensión | Estiramiento por encima del límite del material: zona demasiado ajustada |
| Holgura por zona | Separación real entre tela y cuerpo en busto, cintura, cadera y sisa |
| Poses dinámicas | Sentarse, brazos arriba, caminar |
| Accesibilidad del ensamblaje | Que la aguja llegue a la costura cuando toca coserla |

Las dos últimas son las que no tienen ningún sustituto geométrico. La
accesibilidad bajó aquí desde el nivel 1, donde solo se puede medir el coste
(`costuras_en_redondo`), no la imposibilidad.

## Por qué no está hecho

**1. Rompe las cuatro propiedades del paquete.** Hoy `hilvan` tiene
dos dependencias, no necesita GarmentCode, corre en CPU en milisegundos y es
determinista. La simulación pide GPU, un motor, un avatar y parámetros de
material. Si entra sin condiciones, el uso nº2 del [roadmap](roadmap.md) —
filtrar antes de simular — deja de tener sentido, porque el filtro costaría lo
mismo que lo que filtra.

**2. Riesgo de falsa confianza.** Está en la tabla de riesgos de
[`proyecto.md`](proyecto.md) y es el argumento de peso: *parámetros de material
irreales → el nivel 2 da falsa confianza*. Un validador que dice "válido" sobre
una simulación con telas inventadas afirma algo que nadie ha comprobado. Es peor
que no tenerlo, porque un aviso que no existe no engaña a nadie.

**3. Depende del patronista, que sigue sin identificar.** Los umbrales de
tensión y holgura no se pueden sacar de la literatura: dependen del material y
del criterio de quien confecciona.

## Condición de entrada

No empezar hasta que se cumplan las tres:

- [ ] Un patronista o asesor con el que contrastar los umbrales
- [ ] Al menos un juego de telas medidas, propias o del Fabric Kit de CLO
- [ ] Acceso a GPU estable

Sin las dos primeras, lo que salga no se puede calibrar y cae en el riesgo 2.
La tercera solo condiciona la velocidad.

## Decisiones pendientes

### Motor

Sigue como pregunta abierta en el plan. Tres candidatos:

| Motor | A favor | En contra |
| --- | --- | --- |
| NVIDIA Warp | Es el que usa el pipeline de GarmentCode; el patrón ya está en su formato | Atado a CUDA |
| Blender | Libre, sin GPU obligatoria, scriptable | Más lento; el puente desde el JSON hay que escribirlo |
| CLO | El estándar de la industria, telas medidas de serie | Cerrado, de pago, difícil de automatizar |

Recomendación: **Warp para medir, CLO para validar el criterio**. Warp da el
barrido masivo y es el camino más corto porque GarmentCode ya lo usa; CLO sirve
de referencia contra la que contrastar una muestra, no de motor del pipeline.

### Dónde vive

Extra opcional en este mismo repositorio:

```bash
pip install hilvan          # niveles 0, 1 y 2 geométrico
pip install hilvan[sim]     # + nivel 2 simulado
```

Mantiene las cuatro propiedades del núcleo intactas y hace explícito que la
simulación es otra clase de comprobación. Si el acoplamiento con el motor
resulta profundo, pasa a paquete aparte que dependa de este.

### Parámetros de material

El patrón no los declara — es el quinto hueco de formato, después de `ease`,
`finish`, `orient` y el `stretch` de las aberturas. Hace falta al menos peso,
elasticidad por dirección, rigidez a flexión y grosor, por panel.

La decisión es si se declara en el patrón o se aporta aparte como el cuerpo.
Inclinación: aparte, como `Cuerpo`, porque es una propiedad de la tela elegida
y no del patrón, y el mismo patrón se corta en telas distintas.

## Qué construir, en orden

1. **Puente patrón → malla.** Triangular cada panel y coserlo según el grafo de
   costuras. Aquí la orientación de la costura pasa de conveniencia a requisito
   duro: sin `orient` no se sabe qué vértice va con cuál. Es la misma pieza que
   ya bloquea los veredictos del nivel 2 geométrico.
2. **Avatar.** Del archivo de cuerpo de GarmentCode, para que las medidas
   coincidan con las de `Cuerpo`.
3. **Simulación estática y hallazgos de convergencia.** Interpenetración,
   estabilidad, la prenda no se cae. Sin umbrales que calibrar: son binarios.
4. **Mapas de tensión y holgura.** Primeros umbrales, primera necesidad real de
   patronista.
5. **Poses dinámicas.** Lo más caro, lo último.
6. **Accesibilidad del ensamblaje.** Probablemente ni con simulación salga
   barato; evaluar si merece la pena frente a la rúbrica humana del nivel 4.

Los pasos 1 a 3 no necesitan patronista y podrían adelantarse. Del 4 en
adelante, no.

## Qué no hacer

Publicar un veredicto de nivel 2 simulado antes del paso 4. Mientras los
umbrales no estén contrastados, los resultados son medidas, no juicios, y deben
salir como `info`, igual que las aberturas sin `fits` declarado en el nivel 2
geométrico.

# =====================================================================
#  Documentación de Investigación y Planificación
#  Departamento de Informática y Computación (DIC)
# =====================================================================

Documentación completa en LaTeX del sistema de gestión departamental,
incluyendo metodología de investigación, misión y visión, requerimientos,
modelado UML y algoritmo de soluciones rápidas.

## Compilación en TexStudio

1. Abrir `docs/main.tex` en TexStudio.
2. Verificar que el compilador sea **pdfLaTeX** (`Opciones > Configurar TeXstudio > Compilación > Compilador por defecto`).
3. Presionar `F5` (Compilar y ver) o `F6` + `F7`.
4. Compilar **tres veces** para resolver el índice, las listas y las referencias.

## Compilación desde consola

### PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File docs/compilar.ps1
```

### Manual
```bash
cd docs
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

## Dependencias

**Requeridas** (todas incluidas en MiKTeX, se instalan automáticamente):

| Paquete       | Uso                                      |
|---------------|------------------------------------------|
| `babel` + `spanish` | Idioma español y tipografía         |
| `tikz` + `pgf` | Diagramas UML embebidos                |
| `pgf-umlcd`   | Notación UML                           |
| `pgfgantt`    | Cronograma de Gantt                    |
| `tcolorbox`   | Cajas de resaltado                     |
| `acronym`     | Lista de acrónimos                     |
| `booktabs`, `tabularx`, `longtable` | Tablas |
| `listings`    | Pseudocódigo                           |

**NO requeridas**: Java, Graphviz y PlantUML. Todos los diagramas están
dibujados con TikZ, por lo que el documento compila sin herramientas externas.

## Estructura

```
docs/
├── main.tex                    # Documento maestro (preámbulo + estructura)
├── compilar.ps1                # Script de compilación
├── build/                      # Archivos auxiliares de compilación
├── secciones/
│   ├── 01_introduccion.tex     # Cap. 1: problema, objetivos, hipótesis
│   ├── 02_metodologia.tex      # Cap. 2: método mixto y CRISP-DM
│   ├── 03_mision_vision.tex    # Cap. 3: misión, visión, valores, KPI
│   ├── 04_requerimientos.tex   # Cap. 4: 56 RF, 12 RNF, 12 reglas de negocio
│   ├── 05_diagramas.tex        # Cap. 5: 7 diagramas UML en TikZ
│   ├── 06_algoritmo.tex        # Cap. 6: algoritmo y analítica de datos
│   ├── 07_cronograma.tex       # Cap. 7: cronograma, riesgos, conclusiones
│   └── 08_anexos.tex           # Anexos: instrumentos y trazabilidad
└── uml/
    ├── use_case_diagram.puml   # Fuente PlantUML (opcional)
    ├── class_diagram.puml      # Fuente PlantUML (opcional)
    ├── research_flow.puml      # Fuente PlantUML (opcional)
    └── sequence_evaluation.puml # Fuente PlantUML (opcional)
```

## Contenido del documento

| Cap. | Título | Contenido destacado |
|------|--------|---------------------|
| 1 | Introducción y planteamiento del problema | 11 problemas específicos, 6 preguntas de investigación, 5 hipótesis |
| 2 | Metodología de investigación | 8 fases, muestreo, alfa de Cronbach, CRISP-DM, ética |
| 3 | Misión, visión y objetivos | 10 objetivos estratégicos, 11 KPI, mapa estratégico |
| 4 | Requerimientos | 56 RF, 12 RNF, 12 reglas de negocio, matriz de trazabilidad |
| 5 | Modelado UML | Casos de uso, clases, secuencia, actividades, estados, componentes |
| 6 | Algoritmo de soluciones rápidas | Pseudocódigo, fórmula de priorización, modelo de horarios, tablero |
| 7 | Planificación | Gantt de 24 semanas, 8 riesgos, presupuesto, conclusiones |

## Diagramas incluidos

Los diagramas están **embebidos como TikZ** en `05_diagramas.tex` y
`02_metodologia.tex`:

1. Ciclo metodológico de investigación--acción (Cap. 2)
2. Ciclo CRISP-DM adaptado (Cap. 2)
3. Mapa estratégico visión--misión--resultados (Cap. 3)
4. Diagrama de casos de uso (Cap. 5)
5. Diagrama de clases: relaciones principales (Cap. 5)
6. Diagrama de clases: detalle con atributos y métodos (Cap. 5)
7. Diagrama de secuencia: evaluación docente (Cap. 5)
8. Diagrama de actividades: quejas y sugerencias (Cap. 5)
9. Diagrama de estados: ciclo de vida de una queja (Cap. 5)
10. Diagrama de componentes y arquitectura (Cap. 5)
11. Arquitectura del motor analítico (Cap. 6)
12. Tablero de verificación (Cap. 6)
13. Cronograma de Gantt (Cap. 7)

## Regenerar los diagramas PlantUML (opcional)

Solo si se desea obtener versiones PNG/SVG a partir de las fuentes `.puml`.
Requiere Java y Graphviz:

```bash
java -jar plantuml.jar -tpng docs/uml/use_case_diagram.puml
java -jar plantuml.jar -tpng docs/uml/class_diagram.puml
java -jar plantuml.jar -tpng docs/uml/research_flow.puml
java -jar plantuml.jar -tpng docs/uml/sequence_evaluation.puml
```

## Notas técnicas

- **babel spanish**: se usa la opción `es-noshorthands` para evitar que los
  caracteres `>` y `<` se vuelvan activos y rompan la sintaxis de TikZ
  (`-{Stealth[...]}`), el pseudocódigo y las expresiones matemáticas.
- **pgf-umlcd**: reconfigura el espacio de claves `/tikz`, por lo que las
  flechas punteadas se dibujan con la sintaxis explícita `-{Stealth[...]}`
  directamente en cada `\draw`, en lugar de usar un estilo personalizado.
- **acronym**: se carga con la opción `nohyperlinks` para evitar referencias
  cruzadas indefinidas en la primera pasada.
- **Salida**: `docs/main.pdf` (aproximadamente 86 páginas).

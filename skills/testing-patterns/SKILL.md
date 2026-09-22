---
name: testing-patterns
description: Cómo escribir tests en el proyecto ProyectoASI/SGDIC (fixtures BaseDatos, login por rol, reverse). Usa al crear o editar pruebas en sgdic/tests.py para replicar el patrón existente y evitar tests mal formados.
---

# Tests del proyecto (sgdic/tests.py)

Todos los tests viven en **`sgdic/tests.py`** (una sola clase `BaseDatos` como base). No crear archivos `tests.py` nuevos por app.

## Fixture base
```python
CLAVE = "Prueba2026*"

class BaseDatos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.docente    = Usuario.objects.create_user(username="docente",    password=CLAVE, rol="DOCENTE", ...)
        cls.estudiante = Usuario.objects.create_user(username="estudiante", password=CLAVE, rol="ESTUDIANTE", semestre=6, promedio=4.2)
        cls.secretaria = Usuario.objects.create_user(username="secretaria", password=CLAVE, rol="SECRETARIA", ...)
        cls.intro = Materia.objects.create(codigo="ISC-101", nombre="Introducción", creditos=3, estado=Materia.Estado.PUBLICADA)
        cls.intro.docentes.add(cls.docente)
        cls.oferta_intro = OfertaCupo.objects.create(materia=cls.intro, periodo="2026-1", cupo_maximo=30,
                                                     dia=1, hora_inicio=time(7,0), hora_fin=time(9,0))

    def login(self, usuario):
        cliente = Client()
        cliente.login(username=usuario.username, password=CLAVE)
        return cliente
```

## Patrones de prueba
- **Reglas de negocio (RN)**: crear el objeto, llamar al método (`solicitud.procesar()`), assert sobre estado y `justificacion_estado`.
- **Vistas**: `cliente = self.login(self.estudiante)` → `cliente.get(reverse("cupos:preinscripcion"))` → `assertEqual(r.status_code, 200)`.
- **Permisos**: con un rol no permitido, esperar `PermissionDenied` (403) o `redirect`, según la vista.
- **Siempre** usar `reverse("<app>:<name>")`, nunca rutas hardcodeadas.
- Nuevas clases heredando `BaseDatos`: `class PruebasMallaCurricular(BaseDatos):` (ya existe `PruebasMallaCurricular`).

## Ejecutar
```powershell
.\.venv\Scripts\python.exe manage.py test                     # todo
.\.venv\Scripts\python.exe manage.py test sgdic.tests.PruebasMallaCurricular   # una clase
```
Objetivo: 0 fallos, 0 errores antes de commit.

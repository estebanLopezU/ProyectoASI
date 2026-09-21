# Imágenes estáticas del ASI

## Fondo del login

Coloca aquí la imagen de fondo de la pantalla de ingreso con **exactamente** este nombre:

```
static/img/login-bg.jpg
```

- Formatos equivalentes aceptados: `login-bg.jpg`, `login-bg.jpeg`, `login-bg.png`
  (si usas PNG, actualiza la extensión en `static/css/sgdic.css` → clase `.login-asi`).
- Tamaño recomendado: **1920×1080 px** o superior, orientación horizontal.
- Peso recomendado: menor a 500 KB (comprímela en https://squoosh.app si es más grande).

La clase `.login-asi` en `static/css/sgdic.css` ya tiene el `url("../img/login-bg.jpg")`
configurado junto con un degradado institucional (azul `#0d3b66` → verde `#1b998b`)
que actúa como respaldo: **la pantalla se ve bien aunque la imagen todavía no exista**.

Después de agregar la imagen ejecuta:

```bash
python manage.py collectstatic --noinput
```

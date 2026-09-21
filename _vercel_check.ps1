cd "c:\Users\esteb\OneDrive\Desktop\ProyectoASI"
& .venv\Scripts\Activate.ps1
Write-Host "=== INSTALANDO DEPENDENCIAS ==="
python -m pip install -q whitenoise gunicorn psycopg2-binary
Write-Host "=== VERSION DJANGO ==="
python -c "import django; print(django.get_version())"
Write-Host "=== VALIDANDO SETTINGS ==="
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','sgdic.settings'); import django; django.setup(); print('SETTINGS OK')"
Write-Host "=== COLLECTSTATIC ==="
python manage.py collectstatic --noinput 2>&1
Write-Host "=== CHECK ==="
python manage.py check 2>&1

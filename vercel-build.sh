#!/bin/bash
# Build script para Vercel
set -e

echo "Instalando dependencias..."
pip install -r requirements.txt

echo "Recopilando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Aplicando migraciones..."
python manage.py migrate

echo "Build completado."

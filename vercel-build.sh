#!/bin/bash
# Build script para Vercel (formato services: "buildCommand": "bash vercel-build.sh")
set -e

echo "Instalando dependencias..."
pip install -r requirements.txt

echo "Recopilando archivos estáticos..."
python manage.py collectstatic --no-input

echo "Aplicando migraciones..."
python manage.py migrate

echo "Build completado."

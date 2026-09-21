#!/bin/bash
# Script de build para Render
# https://render.com/docs/deploy-django

set -e

echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Recopilando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Aplicando migraciones..."
python manage.py migrate

echo "Build completado."

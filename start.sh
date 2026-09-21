#!/bin/bash
# Script de inicio para Render
# gunicorn sirve la aplicación Django en producción
gunicorn sgdic.wsgi:application --bind 0.0.0.0:$PORT

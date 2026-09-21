cd "c:\Users\esteb\OneDrive\Desktop\ProyectoASI"

Write-Host "=== ESTADO GIT ==="
git status -s

Write-Host "=== HACIENDO COMMIT ==="
git add -A
git -c user.name="Esteban" -c user.email="esteb@asi.local" commit -m "Setup despliegue Vercel: vercel.json, build script, WhiteNoise middleware, .gitignore, gunicorn + psycopg2 en requirements"

Write-Host "=== PUSH A GITHUB ==="
git push -u origin main 2>&1

Write-Host "=== REMOTE ==="
git remote -v

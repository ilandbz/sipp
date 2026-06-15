Lee el CLAUDE.md y .claude/skills/06_deploy_cicd.md.

CONTEXTO DEL VPS:
- Usuario PostgreSQL: sip_user
- Base de datos: sip_db
- Schema: sipp (ya existe)
- Repositorio: https://github.com/ilandbz/sipp
- Acceso: clave SSH
- IP pública configurada con subdominio

TAREA — Preparar el proyecto para deploy con CI/CD:

PARTE 1 — Crear carpeta deploy/ en la raíz del proyecto con:

1. deploy/sipp-backend.service  (archivo systemd del skill)
2. deploy/sipp-frontend.service (archivo systemd del skill)
3. deploy/nginx-sipp            (config nginx del skill)
4. deploy/install.sh            (script de instalación inicial):

#!/bin/bash
set -e
echo "=== SIPP — Instalación inicial en VPS ==="

# Dependencias del sistema
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nginx git

# Entorno virtual
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
pip install gunicorn

# Logs
sudo mkdir -p /var/log/sipp
sudo chown $USER:$USER /var/log/sipp

# Servicios systemd
sudo cp deploy/sipp-backend.service /etc/systemd/system/
sudo cp deploy/sipp-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sipp-backend sipp-frontend

# Nginx
sudo cp deploy/nginx-sipp /etc/nginx/sites-available/sipp
sudo ln -sf /etc/nginx/sites-available/sipp /etc/nginx/sites-enabled/sipp
sudo nginx -t && sudo systemctl restart nginx

# Setup BD
cd backend
python -m app.management.deploy_setup
cd ..

# Arrancar servicios
sudo systemctl start sipp-backend sipp-frontend

echo "=== Instalación completada ==="
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:8501"

PARTE 2 — Crear .github/workflows/deploy.yml
Exactamente como está en el skill 06_deploy_cicd.md.
Los secrets que usa son: VPS_HOST, VPS_USER, VPS_SSH_KEY

PARTE 3 — Actualizar backend/app/management/deploy_setup.py
Con los seeds completos del skill:
- seed_penalizaciones (6 penalizaciones SMED)
- seed_maquinas (M8 80bpm, M10 100bpm, M14 120bpm)
- seed_materiales (KRAFT, KRAFT 50GR, KRAFT 60GR, LINER, ANTIGRASA)
- seed_franquicias (niveles 1-4)
- seed_tipos_bolsa (2,4,5,6,8,10,12)
Todos con ON CONFLICT DO NOTHING (idempotente)

PARTE 4 — Actualizar .env.example con variables para VPS:
DATABASE_URL=postgresql+asyncpg://sip_user:PASSWORD@localhost:5432/sip_db
POSTGRES_SCHEMA=sipp
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False
BACKEND_URL=https://sipp-api.TUDOMINIO.com

PARTE 5 — Actualizar .gitignore:
.env
.env.production
__pycache__/
*.pyc
.venv/
*.log
data/uploads/*.csv
.DS_Store

PARTE 6 — Crear README.md en la raíz con:
# SIPP — Sistema Inteligente de Programación de Producción
## Setup local
## Deploy VPS
## CI/CD
(contenido basado en el skill 06_deploy_cicd.md)

Al terminar hacer commit de todos los archivos nuevos.
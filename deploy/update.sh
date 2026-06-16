#!/bin/bash
set -e
echo "=== SIPP — Actualizando ==="

cd /var/www/html/vygpack-sipp
source .venv/bin/activate

pip install -r backend/requirements.txt -q
pip install -r frontend/requirements.txt -q

cd backend && python -m app.management.deploy_setup && cd ..

systemctl restart sipp-backend
systemctl restart sipp-frontend

echo "✓ Actualización completada"

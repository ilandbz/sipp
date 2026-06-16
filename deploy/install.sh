#!/bin/bash
set -e
echo "=== SIPP — Instalación inicial en VPS ==="

apt update && apt install -y python3.12-venv python3-pip

cd /var/www/html/vygpack-sipp
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
pip install gunicorn passlib[bcrypt]

mkdir -p /var/log/sipp data/uploads

cp deploy/sipp-backend.service /etc/systemd/system/
cp deploy/sipp-frontend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable sipp-backend sipp-frontend

cp deploy/apache-sipp.conf /etc/apache2/sites-available/sipp.macrocompany.net.pe.conf
a2enmod proxy proxy_http proxy_wstunnel rewrite headers
a2ensite sipp.macrocompany.net.pe.conf
apache2ctl configtest && systemctl reload apache2

cd backend && python -m app.management.deploy_setup && cd ..

systemctl start sipp-backend sipp-frontend

echo "=== Instalación completada ==="

#!/bin/bash
set -e
echo "=== SIPP — Actualizando ==="

cd /var/www/html/vygpack-sipp
source .venv/bin/activate

pip install -r backend/requirements.txt -q
pip install -r frontend/requirements.txt -q

# Desinstalar librerías problemáticas si existen
pip uninstall extra-streamlit-components -y 2>/dev/null || true

cd backend && python -m app.management.deploy_setup && cd ..

# Limpiar sesiones corruptas en cada deploy
python3 -c "
import asyncio, asyncpg, os
async def clear():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL','').replace('postgresql+asyncpg','postgresql'))
    await conn.execute('DELETE FROM sipp.sesiones')
    await conn.close()
    print('Sesiones limpiadas')
asyncio.run(clear())
" 2>/dev/null || true

systemctl restart sipp-backend
systemctl restart sipp-frontend

echo "✓ Actualización completada"

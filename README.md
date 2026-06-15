# SIPP — Sistema Inteligente de Programación de Producción 🏭

**SIPP** es un sistema desarrollado para **VYGPACK** con el objetivo de secuenciar y optimizar automáticamente las órdenes de fabricación de bolsas de papel (en las máquinas M8, M10 y M14), minimizando los tiempos de *setup* mediante la aplicación de reglas **SMED** (Single-Minute Exchange of Die).

---

## 🚀 Tecnologías Principales

### Backend
* **Framework:** FastAPI (Python 3.11+)
* **ORM & BD:** SQLModel, SQLAlchemy Async, PostgreSQL 16
* **Data & Lógica:** Pandas, NumPy, Pydantic v2

### Frontend (HMI de Planta)
* **Framework:** Streamlit (Python puro)
* **Comunicación HTTP:** `httpx`

---

## ⚙️ Estructura del Proyecto

El sistema está fuertemente desacoplado, siguiendo una arquitectura cliente-servidor mediante API REST.

```text
vygpack-sipp/
├── backend/            # API REST (FastAPI) y lógica de optimización SMED
│   ├── app/            # Código fuente (routers, models, schemas, services)
│   ├── alembic/        # Migraciones de base de datos
│   └── Makefile        # Comandos de despliegue
├── frontend/           # Interfaz de Usuario y Dashboard (Streamlit)
│   └── app.py          # Punto de entrada de la UI principal
├── data/               # Archivos de datos o CSV
└── bd.sql              # Schema principal de PostgreSQL
```

---

## 🛠️ Instalación y Configuración (Desarrollo Local)

### 1. Requisitos Previos
* Python 3.11+
* PostgreSQL 16 (ejecutándose localmente)
* Crear una base de datos (por ejemplo, `sip_db` o `sipp_db`).

### 2. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/vygpack-sipp.git
cd vygpack-sipp
```

### 3. Variables de Entorno
Copia el archivo de ejemplo para configurar tus accesos a la base de datos:
```bash
cp .env.example .env
```
*Asegúrate de ajustar `DATABASE_URL` con tu usuario y contraseña de Postgres, y verificar que `POSTGRES_SCHEMA=sipp`.*

### 4. Configuración del Backend
```bash
cd backend
python -m venv venv

# Activar entorno (Windows)
venv\Scripts\activate
# Activar entorno (Linux/Mac)
# source venv/bin/activate

pip install -r requirements.txt
```

#### Inicializar la Base de Datos
Para generar la estructura de la base de datos (schema `sipp`) y cargar la información maestra inicial (máquinas, penalizaciones, materiales, franquicias):
```bash
make deploy
```
*Si estás en Windows y no usas `make`, puedes correr directamente:*
```bash
python -m app.management.deploy_setup
```

### 5. Configuración del Frontend
Abre otra terminal, ve a la carpeta raíz del proyecto y luego a `frontend`:
```bash
cd frontend
python -m venv venv
# Activar entorno de forma similar...
pip install -r requirements.txt
```

---

## ▶️ Ejecución

Para correr el proyecto localmente, necesitas inicializar ambos servicios:

**Servidor API (Backend):**
```bash
cd backend
make run-backend
# O directamente: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*La documentación interactiva de la API estará en `http://localhost:8000/docs`.*

**HMI Dashboard (Frontend):**
```bash
cd backend  # (Si usas el comando del Makefile)
make run-frontend
# O directamente desde la raíz o frontend: streamlit run app.py --server.port 8501
```
*El sistema se abrirá en tu navegador en `http://localhost:8501`.*

---

## 📈 Despliegue a Producción (VPS Ubuntu)

El sistema incluye comandos listos para facilitar su despliegue en un VPS con PostgreSQL:
1. Asegurar la creación del archivo `.env.production` basándose en el `.env.example` con los datos del servidor (por defecto, apuntando a `sip_db`).
2. Ejecutar `make deploy` para provisionar el esquema.
3. Configurar un manejador de procesos de sistema como `systemd` o `pm2` para mantener `uvicorn` y `streamlit` ejecutándose en segundo plano.

---

## 👨‍💻 Autor
Desarrollado por **Cristian Figueroa**  
*Senior Systems Architect / Software Developer*

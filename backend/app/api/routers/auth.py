import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import bcrypt

from app.core.database import get_session
from app.models.usuario import Usuario
from app.models.sesion import Sesion

router = APIRouter(prefix="/auth", tags=["Autenticación"])

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    nombre_completo: str | None = None
    rol: str

class LoginResponse(BaseModel):
    token: str
    usuario: UserResponse
    rol: str

def get_token_from_header(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization faltante"
        )
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError()
        return token
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Esquema de autenticación inválido. Debe ser Bearer."
        )

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_session)):
    # 1. Buscar usuario
    statement = select(Usuario).where(Usuario.username == payload.username, Usuario.activo == True)
    result = await db.execute(statement)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )
        
    # 2. Verificar contraseña
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )
    
    # bcrypt.checkpw requires bytes
    try:
        pwd_bytes = payload.password.encode("utf-8")
        hash_bytes = user.password_hash.encode("utf-8")
        is_valid = bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )
        
    # 3. Crear sesión
    user_id = user.id
    username = user.username
    nombre_completo = user.nombre_completo
    rol = user.rol
    
    token = str(uuid.uuid4())
    expira_en = datetime.now(timezone.utc) + timedelta(hours=8)
    
    nueva_sesion = Sesion(
        usuario_id=user_id,
        token=token,
        expira_en=expira_en
    )
    
    db.add(nueva_sesion)
    await db.commit()
    await db.refresh(nueva_sesion)
    
    user_data = UserResponse(
        id=user_id,
        username=username,
        nombre_completo=nombre_completo,
        rol=rol
    )
    
    return LoginResponse(
        token=token,
        usuario=user_data,
        rol=rol
    )

@router.get("/me", response_model=UserResponse)
async def get_me(token: str = Depends(get_token_from_header), db: AsyncSession = Depends(get_session)):
    # 1. Buscar token en sesiones
    stmt_sesion = select(Sesion).where(Sesion.token == token)
    res_sesion = await db.execute(stmt_sesion)
    sesion = res_sesion.scalars().first()
    
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada"
        )
        
    # 2. Verificar si expiró
    # Asegurar timezone-aware comparison
    ahora = datetime.now(timezone.utc)
    expira_en = sesion.expira_en
    if expira_en.tzinfo is None:
        expira_en = expira_en.replace(tzinfo=timezone.utc)
        
    if expira_en < ahora:
        # Opcional: limpiar sesión expirada
        await db.delete(sesion)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada"
        )
        
    # 3. Obtener usuario
    stmt_usuario = select(Usuario).where(Usuario.id == sesion.usuario_id)
    res_usuario = await db.execute(stmt_usuario)
    user = res_usuario.scalars().first()
    
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado"
        )
        
    return UserResponse(
        id=user.id,
        username=user.username,
        nombre_completo=user.nombre_completo,
        rol=user.rol
    )

@router.post("/logout")
async def logout(token: str = Depends(get_token_from_header), db: AsyncSession = Depends(get_session)):
    stmt_sesion = select(Sesion).where(Sesion.token == token)
    res_sesion = await db.execute(stmt_sesion)
    sesion = res_sesion.scalars().first()
    
    if sesion:
        await db.delete(sesion)
        await db.commit()
        
    return {"message": "Sesión cerrada correctamente"}

class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nuevo: str
    confirmar: str

class ActualizarPerfilRequest(BaseModel):
    nombre_completo: str

@router.put("/cambiar-password")
async def cambiar_password(
    payload: CambiarPasswordRequest,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_session)
):
    # 1. Buscar token en sesiones
    stmt_sesion = select(Sesion).where(Sesion.token == token)
    res_sesion = await db.execute(stmt_sesion)
    sesion = res_sesion.scalars().first()
    
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada"
        )
        
    # 2. Verificar si expiró
    ahora = datetime.now(timezone.utc)
    expira_en = sesion.expira_en
    if expira_en.tzinfo is None:
        expira_en = expira_en.replace(tzinfo=timezone.utc)
        
    if expira_en < ahora:
        await db.delete(sesion)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada"
        )
        
    # 3. Obtener usuario
    stmt_usuario = select(Usuario).where(Usuario.id == sesion.usuario_id)
    res_usuario = await db.execute(stmt_usuario)
    user = res_usuario.scalars().first()
    
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado"
        )
        
    # 4. Validar contraseñas
    if payload.password_nuevo != payload.confirmar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las contraseñas no coinciden"
        )
        
    if len(payload.password_nuevo) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mínimo 6 caracteres"
        )
        
    # Verificar password_actual con bcrypt
    try:
        pwd_bytes = payload.password_actual.encode("utf-8")
        hash_bytes = user.password_hash.encode("utf-8")
        is_valid = bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        is_valid = False
        
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )
        
    # 5. Actualizar contraseña
    pwd_hash = bcrypt.hashpw(payload.password_nuevo.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.password_hash = pwd_hash
    db.add(user)
    await db.commit()
    
    return {"mensaje": "Contraseña actualizada correctamente"}

@router.put("/actualizar-perfil", response_model=UserResponse)
async def actualizar_perfil(
    payload: ActualizarPerfilRequest,
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_session)
):
    # 1. Buscar token en sesiones
    stmt_sesion = select(Sesion).where(Sesion.token == token)
    res_sesion = await db.execute(stmt_sesion)
    sesion = res_sesion.scalars().first()
    
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada"
        )
        
    # 2. Verificar si expiró
    ahora = datetime.now(timezone.utc)
    expira_en = sesion.expira_en
    if expira_en.tzinfo is None:
        expira_en = expira_en.replace(tzinfo=timezone.utc)
        
    if expira_en < ahora:
        await db.delete(sesion)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada"
        )
        
    # 3. Obtener usuario
    stmt_usuario = select(Usuario).where(Usuario.id == sesion.usuario_id)
    res_usuario = await db.execute(stmt_usuario)
    user = res_usuario.scalars().first()
    
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado"
        )
        
    # 4. Actualizar nombre completo
    user.nombre_completo = payload.nombre_completo
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        nombre_completo=user.nombre_completo,
        rol=user.rol
    )


from pydantic import BaseModel
from typing import List

class OptimizarRequest(BaseModel):
    semana_id: int

class CalcularTiemposRequest(BaseModel):
    of_ids: List[int]

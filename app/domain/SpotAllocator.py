from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import numpy as np
from sklearn.neighbors import KDTree
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from deps import SessionLocal

@dataclass(frozen=True)
class FreeSpot:
    id: int
    x: float
    y: float
    sector: Optional[str]  # 'accesible' o None/otro
    level: int             # todos 1 por ahora


class SpotIndex:
    """
    Índice en memoria: mantiene KD-Trees separados para:
      - accesibles (sector='accesible')
      - generales (resto)
    También guarda las listas alineadas de IDs para resolver idx->id.
    """
    def __init__(self) -> None:
        self.ids: List[int] = []
        self.xy: Optional[np.ndarray] = None
        self.kdt: Optional[KDTree] = None


    def _build_single(self, spots: List[Tuple[int, float, float]]) -> Tuple[List[int], Optional[np.ndarray], Optional[KDTree]]:
        if not spots:
            return [], None, None
        ids = [s[0] for s in spots]
        xy = np.array([[s[1], s[2]] for s in spots], dtype=float)
        kdt = KDTree(xy, metric="euclidean")
        return ids, xy, kdt

    def build(self, free_spots: List[FreeSpot]) -> None:
        spots = [(s.code, s.x, s.y) for s in free_spots]

        self.ids, self.xy, self.kdt = self._build_single(spots)

    def nearest_ids(self, gate_xy: Tuple[float, float], k: int = 8, type: str = "GENERAL") -> List[int]:
        """
        Devuelve hasta k IDs de spots ordenados por distancia para el gate.
        - if only_accessible=True: consulta solo el árbol accesible.
        - si no hay accesibles o no alcanza k, completa con generales.
        """
        result: List[int] = []

        def query(kdt: Optional[KDTree], ids: List[int], kq: int) -> List[int]:
            if kdt is None or not ids or kq <= 0:
                return []
            kq = min(kq, len(ids))
            dist, idx = kdt.query(np.array([gate_xy]), k=kq)
            return [ids[i] for i in idx[0]]

        if type == "DISABLED":
            result.extend(query(self.kdt_accessible, self.ids_accessible, k))
            return result

        # Generar mezcla: primero generales, o podés priorizar accesibles si querés
        result.extend(query(self.kdt_general, self.ids_general, k))
        if len(result) < k:
            faltan = k - len(result)
            result.extend(query(self.kdt_accessible, self.ids_accessible, faltan))

        return result


class SpotAllocatorIndexBuilder:
    """
    Capa que lee de la DB y construye SpotIndex.
    Usá build_from_db(session) para traer los libres y armar KD-Trees.
    """

    def __init__(self, table_name: str = "spots") -> None:
        self.table_name = table_name

    async def fetch_free_spots(self, session: AsyncSession, car_type) -> List[FreeSpot]:
        filter = ""
        if car_type == "GENERAL":
            filter = "AND type = 'GENERAL'"

        # Trae SOLO libres. Si querés filtrar por level aquí, agregalo al WHERE.
        q = text(f"""
            SELECT code, x, y, type
            FROM {self.table_name}
            WHERE occupied = FALSE {filter}
        """)
        rows = (await session.execute(q)).all()

        return [
            FreeSpot(
                id=int(r[0]),
                x=float(r[1]),
                y=float(r[2]),
                sector=(r[3] if r[3] is not None else None),
                level=int(r[4]),
            )
            for r in rows
        ]

    async def build_from_db(self,car_type) -> SpotIndex:
        free_spots = await self.fetch_free_spots(SessionLocal,car_type)
        index = SpotIndex()
        index.build(free_spots)
        return index
    
class SpotAllocator:
    async def fetch_spot(self,car_type):
        index = SpotAllocatorIndexBuilder.build_from_db(car_type)[0]
        return index
    
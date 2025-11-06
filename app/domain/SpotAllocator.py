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
    spot_code: int
    x: float
    y: float
    sector: Optional[str]  # 'accesible' o None/otro

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
        spots = [(s.spot_code, s.x, s.y) for s in free_spots]

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
        
        if car_type and car_type != "GENERAL":
            q = text(f"""
                SELECT spot_code, x_coord, y_coord, spot_type
                FROM {self.table_name}
                WHERE occupied = FALSE AND spot_type = :car_type
            """)
            rows = (await session.execute(q, {"car_type": car_type})).all()
        else:
            q = text(f"""
                SELECT spot_code, x_coord, y_coord, spot_type
                FROM {self.table_name}
                WHERE occupied = FALSE
            """)
            rows = (await session.execute(q)).all()

        # rows: [(code, x, y, spot_type), ...]
        free_spots = [
            FreeSpot(
                spot_code=str(r[0]),              # code es text
                x=float(r[1]),
                y=float(r[2]),
                sector=(r[3] if r[3] is not None else None),
                # si FreeSpot tenía 'level', quítalo o ponlo en None
            )
            for r in rows
        ]
        return free_spots

    async def build_from_db(self, session: AsyncSession, car_type: Optional[str]) -> SpotIndex:
        free_spots = await self.fetch_free_spots(session, car_type)
        index = SpotIndex()
        index.build(free_spots)
        return index
    
class SpotAllocator:
    def __init__(self, builder: SpotAllocatorIndexBuilder) -> None:
        self.builder = builder

    async def find_spot(self, session: AsyncSession, car_type: Optional[str]) -> SpotIndex:
        # ¡Ojo el await!
        index = await self.builder.build_from_db(session, car_type)
        return index.ids[0]
    
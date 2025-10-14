from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.db_models import PlateAuthorization

"""
Acceso a DB para chequear si la placa está autorizada (is_plate_active).
"""

class AuthorizationRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_plate_active(self, plate: str) -> bool:
        norm = normalize_plate(plate)
        stmt = select(PlateAuthorization.active).where(PlateAuthorization.plate == norm)
        res = await self.session.execute(stmt)
        row = res.first()
        return bool(row and row[0] == 1)

def normalize_plate(p: str) -> str:
    return "".join(p.split()).upper() if p else ""

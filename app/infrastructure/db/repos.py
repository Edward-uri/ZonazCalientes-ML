from sqlmodel import Session, select
from app.infrastructure.db.models import Inferencia

class InferenciaRepo:
    def __init__(self, session: Session):
        self.session = session

    def guardar(self, inf: Inferencia) -> Inferencia:
        self.session.add(inf)
        self.session.commit()
        self.session.refresh(inf)
        return inf

    def listar(self, municipio: int | None = None, limit: int = 50, offset: int = 0) -> list[Inferencia]:
        stmt = select(Inferencia)
        if municipio is not None:
            stmt = stmt.where(Inferencia.municipio == municipio)
        stmt = stmt.order_by(Inferencia.creado_en.desc()).limit(limit).offset(offset)
        return list(self.session.exec(stmt).all())

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.profile.service import Stats, stats_for

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/stats", response_model=Stats)
def my_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return stats_for(db, user.id)

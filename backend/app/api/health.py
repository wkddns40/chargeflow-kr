from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "chargeflow-kr-api"}


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import CharterContract, User
from app.deps import get_db, require_role
from app.schemas.contract import CharterContractCreate, CharterContractResponse, CharterContractUpdate

router = APIRouter(prefix="/contracts", tags=["Charter Contracts"])

_VALID_CONTRACT_TYPES = {"SPOT", "COA", "PERIOD"}
_VALID_STATUSES = {"DRAFT", "CONFIRMED", "CANCELLED"}


def _to_response(contract: CharterContract) -> CharterContractResponse:
    """
    Section 5.2: laytime/demurrage terms are contract-specific and nullable in storage
    (so we know a term was never negotiated), but the API always returns a usable number -
    the contract's own value if set, else the configurable market-standard default.
    """
    return CharterContractResponse(
        contract_id=contract.contract_id,
        recommendation_id=contract.recommendation_id,
        contract_type=contract.contract_type,
        commodity=contract.commodity,
        cargo_qty_mt=contract.cargo_qty_mt,
        origin_port_code=contract.origin_port_code,
        destination_port_code=contract.destination_port_code,
        trade_lane_id=contract.trade_lane_id,
        vessel_class_id=contract.vessel_class_id,
        tce_rate_usd_day=contract.tce_rate_usd_day,
        total_cost_usd=contract.total_cost_usd,
        laytime_allowed_days=(
            contract.laytime_allowed_days
            if contract.laytime_allowed_days is not None
            else settings.DEFAULT_LAYTIME_ALLOWED_DAYS
        ),
        demurrage_rate_usd_per_day=(
            contract.demurrage_rate_usd_per_day
            if contract.demurrage_rate_usd_per_day is not None
            else settings.DEFAULT_DEMURRAGE_RATE_USD_PER_DAY
        ),
        entry_window_start=contract.entry_window_start,
        entry_window_end=contract.entry_window_end,
        status=contract.status,
        created_by_user_id=contract.created_by_user_id,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


@router.get("", response_model=List[CharterContractResponse])
def list_contracts(
    status_filter: Optional[str] = None,
    trade_lane_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[CharterContractResponse]:
    query = db.query(CharterContract)
    if status_filter:
        query = query.filter(CharterContract.status == status_filter.upper())
    if trade_lane_id is not None:
        query = query.filter(CharterContract.trade_lane_id == trade_lane_id)
    contracts = query.order_by(CharterContract.created_at.desc()).all()
    return [_to_response(c) for c in contracts]


@router.get("/{contract_id}", response_model=CharterContractResponse)
def get_contract(contract_id: str, db: Session = Depends(get_db)) -> CharterContractResponse:
    contract = db.query(CharterContract).filter(CharterContract.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    return _to_response(contract)


@router.post("", response_model=CharterContractResponse, status_code=201)
def create_contract(
    request: CharterContractCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_role("logistics_manager")),
) -> CharterContractResponse:
    """
    Writes (create/update/cancel) require the `logistics_manager` role once AUTH_ENABLED=True.
    With AUTH_ENABLED=False (MVP default) this is unauthenticated, matching every other
    router, so local dev and the smoke suite don't need a login step.
    """
    contract_type = request.contract_type.upper()
    if contract_type not in _VALID_CONTRACT_TYPES:
        raise HTTPException(status_code=400, detail=f"contract_type must be one of {sorted(_VALID_CONTRACT_TYPES)}")
    status_val = request.status.upper()
    if status_val not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_VALID_STATUSES)}")

    contract = CharterContract(
        recommendation_id=request.recommendation_id,
        contract_type=contract_type,
        commodity=request.commodity,
        cargo_qty_mt=request.cargo_qty_mt,
        origin_port_code=request.origin_port_code,
        destination_port_code=request.destination_port_code,
        trade_lane_id=request.trade_lane_id,
        vessel_class_id=request.vessel_class_id,
        tce_rate_usd_day=request.tce_rate_usd_day,
        total_cost_usd=request.total_cost_usd,
        laytime_allowed_days=request.laytime_allowed_days,
        demurrage_rate_usd_per_day=request.demurrage_rate_usd_per_day,
        entry_window_start=request.entry_window_start,
        entry_window_end=request.entry_window_end,
        status=status_val,
        created_by_user_id=user.user_id if user else None,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _to_response(contract)


@router.patch("/{contract_id}", response_model=CharterContractResponse)
def update_contract(
    contract_id: str,
    request: CharterContractUpdate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_role("logistics_manager")),
) -> CharterContractResponse:
    contract = db.query(CharterContract).filter(CharterContract.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    update_data = request.model_dump(exclude_unset=True)
    if "contract_type" in update_data and update_data["contract_type"]:
        update_data["contract_type"] = update_data["contract_type"].upper()
        if update_data["contract_type"] not in _VALID_CONTRACT_TYPES:
            raise HTTPException(status_code=400, detail=f"contract_type must be one of {sorted(_VALID_CONTRACT_TYPES)}")
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].upper()
        if update_data["status"] not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_VALID_STATUSES)}")

    for field, value in update_data.items():
        setattr(contract, field, value)

    db.commit()
    db.refresh(contract)
    return _to_response(contract)


@router.delete("/{contract_id}", status_code=204)
def cancel_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_role("logistics_manager")),
) -> None:
    """Soft-delete: marks the contract CANCELLED rather than removing the audit row."""
    contract = db.query(CharterContract).filter(CharterContract.contract_id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")
    contract.status = "CANCELLED"
    db.commit()
    return None

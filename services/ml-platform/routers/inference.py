from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models import PredictionRequest, PredictionResponse
from inference.predictor import ModelPredictor

router = APIRouter(prefix="/api/v1/ml", tags=["ML Inference"])


@router.post("/predict")
async def predict(body: PredictionRequest) -> PredictionResponse:
    predictor = ModelPredictor()
    try:
        result = await predictor.predict(
            features=body.features,
            model_name=body.model_name,
            model_version=body.model_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    return PredictionResponse(**result)


@router.get("/predict/health")
async def predict_health():
    return {"status": "healthy", "message": "Inference API ready"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import numpy as np

app = FastAPI()

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load trained model and scaler
model = joblib.load("random_forest_model.pkl")
scaler = joblib.load("scaler.pkl")


class VoterData(BaseModel):
    age: float
    gender: int
    household_size: float
    distance: float


@app.get("/")
def home():
    return {"message": "Voting Prediction API is running"}


@app.post("/predict")
def predict(data: VoterData):

    # Numerical features
    numerical_data = np.array([[
        data.age,
        data.household_size,
        data.distance
    ]])

    # Scale numerical features
    scaled_data = scaler.transform(numerical_data)

    # Add gender
    final_data = np.column_stack([
        scaled_data,
        [data.gender]
    ])

    # Prediction
    prediction = model.predict(final_data)[0]

    return {
        "prediction": int(prediction),
        "status": "Voted" if prediction == 1 else "Not Voted"
    }
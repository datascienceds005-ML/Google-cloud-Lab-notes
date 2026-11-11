"""
app.py
------
Streamlit web application for the AI Student Performance Prediction System.
Lets a user input student parameters and get a real-time predicted
final exam score from the trained Linear Regression model.
Run: streamlit run app.py
"""

import json

import pickle

import numpy as np
import pandas as pd
import streamlit as st
import sys
import os

# यह पाइथन को कंटेनर के अंदर 'src' फोल्डर का पाथ ढूंढने में मदद करेगा
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from data_preprocessing import EDUCATION_ORDER

MODEL_DIR = "models"

st.set_page_config(
    page_title="Student Performance Predictor",
    page_icon="🎓",
    layout="centered",
)


# ----------------------------------------------------------------------
# Cached loaders
# ----------------------------------------------------------------------
@st.cache_resource
def load_artifacts():
    with open(os.path.join(MODEL_DIR, "linear_regression_model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "feature_names.json")) as f:
        feature_names = json.load(f)
    with open(os.path.join(MODEL_DIR, "metrics.json")) as f:
        metrics = json.load(f)
    return model, scaler, feature_names, metrics


def band_for_score(score: float) -> tuple[str, str]:
    """Returns (label, color) for a predicted score."""
    if score >= 85:
        return "Excellent", "green"
    elif score >= 70:
        return "Good", "blue"
    elif score >= 50:
        return "Average", "orange"
    else:
        return "Needs Improvement", "red"


def build_feature_row(inputs: dict, feature_names: list) -> np.ndarray:
    """Turns raw user inputs (dict) into the exact ordered feature vector the model expects."""
    yes_no = {"Yes": 1, "No": 0}

    engagement_index = (
        inputs["study_hours_per_day"] * 10
        + inputs["attendance_percentage"] * 0.5
        - inputs["screen_time_hours"] * 3
    )

    row = {
        "study_hours_per_day": inputs["study_hours_per_day"],
        "attendance_percentage": inputs["attendance_percentage"],
        "previous_exam_score": inputs["previous_exam_score"],
        "sleep_hours": inputs["sleep_hours"],
        "screen_time_hours": inputs["screen_time_hours"],
        "parental_education_score": EDUCATION_ORDER[inputs["parental_education"]],
        "extracurricular_activities_encoded": yes_no[inputs["extracurricular_activities"]],
        "internet_access_encoded": yes_no[inputs["internet_access"]],
        "study_group_encoded": yes_no[inputs["study_group"]],
        "tutoring_encoded": yes_no[inputs["tutoring"]],
        "engagement_index": engagement_index,
    }
    return np.array([[row[f] for f in feature_names]])


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
st.title("🎓 AI Student Performance Predictor")
st.markdown(
    "Enter a student's study habits and background below to predict their "
    "**final exam score** using a trained Linear Regression model."
)

if not os.path.exists(os.path.join(MODEL_DIR, "linear_regression_model.pkl")):
    st.error(
        "No trained model found. Run `python3 src/train_model.py` first to "
        "generate the model artifacts in the `models/` folder."
    )
    st.stop()

model, scaler, feature_names, metrics = load_artifacts()

with st.sidebar:
    st.header("📊 Model Info")
    st.metric("R² Score", metrics["r2_score"])
    st.metric("Mean Absolute Error", metrics["mae"])
    st.metric("RMSE", metrics["rmse"])
    st.caption(f"Trained on {metrics['n_train']} students, tested on {metrics['n_test']}.")
    st.divider()
    st.markdown(
        "**About**\n\n"
        "This app wraps a Scikit-Learn Linear Regression model trained on "
        "student study-habit data. Adjust the inputs and click **Predict** "
        "to see an estimated final exam score."
    )

st.subheader("Student Parameters")

col1, col2 = st.columns(2)

with col1:
    study_hours = st.slider("Study hours per day", 0.0, 12.0, 4.5, 0.5)
    attendance = st.slider("Attendance percentage", 40.0, 100.0, 85.0, 1.0)
    previous_score = st.slider("Previous exam score", 0.0, 100.0, 65.0, 1.0)
    sleep_hours = st.slider("Sleep hours per night", 3.0, 10.0, 7.0, 0.5)
    screen_time = st.slider("Screen time (non-study) hours/day", 0.0, 10.0, 3.5, 0.5)

with col2:
    parental_education = st.selectbox(
        "Parental education level", list(EDUCATION_ORDER.keys()), index=1
    )
    extracurricular = st.radio("Extracurricular activities?", ["Yes", "No"], horizontal=True)
    internet_access = st.radio("Internet access at home?", ["Yes", "No"], horizontal=True)
    study_group = st.radio("Part of a study group?", ["Yes", "No"], horizontal=True)
    tutoring = st.radio("Receives tutoring?", ["Yes", "No"], horizontal=True)

st.divider()

if st.button("🔮 Predict Final Exam Score", type="primary", use_container_width=True):
    inputs = {
        "study_hours_per_day": study_hours,
        "attendance_percentage": attendance,
        "previous_exam_score": previous_score,
        "sleep_hours": sleep_hours,
        "screen_time_hours": screen_time,
        "parental_education": parental_education,
        "extracurricular_activities": extracurricular,
        "internet_access": internet_access,
        "study_group": study_group,
        "tutoring": tutoring,
    }

    X_row = build_feature_row(inputs, feature_names)
    X_scaled = scaler.transform(X_row)
    prediction = float(model.predict(X_scaled)[0])
    prediction = round(min(max(prediction, 0), 100), 1)

    label, color = band_for_score(prediction)

    st.markdown("### Prediction Result")
    r1, r2 = st.columns(2)
    with r1:
        st.metric("Predicted Final Exam Score", f"{prediction}/100")
    with r2:
        st.markdown(f"**Performance Band:** :{color}[{label}]")

    st.progress(prediction / 100)

    st.caption(
        "This prediction is based on a statistical model trained on historical "
        "data and should be used as a general guide, not a guaranteed outcome."
    )

st.divider()
st.caption("Built with Python, Pandas, NumPy, Scikit-Learn, and Streamlit.") 


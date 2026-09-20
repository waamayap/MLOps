"""API de predicción de precios de vivienda desplegada en Cloud Run.

Flujo: BigQuery (features + datos de entrada) -> modelo de regresión lineal
incluido en la imagen -> predicción -> BigQuery (tabla de salida).
"""

import os
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, HTTPException
from google.cloud import bigquery
from joblib import load

# --- Configuración del proyecto ---
# No se usan variables de entorno obligatorias; los valores quedan en el código
# tal como lo permite la asignación.
PROJECT_ID = "mlops17-507600"
DATASET = "wamayap"

FEATURES_TABLE = f"{PROJECT_ID}.{DATASET}.selected_features"
INPUT_TABLE = f"{PROJECT_ID}.{DATASET}.xtest"
OUTPUT_TABLE = f"{PROJECT_ID}.{DATASET}.predictions"

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "linear_regression.joblib")

app = FastAPI(title="API de Predicción - Precio de Vivienda")

# El modelo viaja dentro de la imagen y se carga una sola vez al iniciar el proceso.
model = load(MODEL_PATH)

# Cloud Run inyecta las credenciales de la cuenta de servicio configurada en el
# servicio (Application Default Credentials), por lo que no se requiere un
# archivo de llaves.
bq_client = bigquery.Client(project=PROJECT_ID)


@app.get("/")
def read_root():
    return {"message": "API de predicción activa"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


def _get_selected_features() -> list[str]:
    query = f"SELECT string_field_0 AS feature FROM `{FEATURES_TABLE}`"
    rows = bq_client.query(query).result()
    features_in_bq = {row.feature for row in rows}
    if not features_in_bq:
        raise HTTPException(status_code=500, detail="No se encontraron features en BigQuery")

    # BigQuery no garantiza el orden de las filas sin ORDER BY, así que el
    # orden de columnas que espera el modelo se toma de feature_names_in_
    # (guardado al entrenar); la tabla de BigQuery solo valida el conjunto.
    model_features = list(model.feature_names_in_)
    if set(model_features) != features_in_bq:
        raise HTTPException(
            status_code=500,
            detail="Las features de BigQuery no coinciden con las del modelo",
        )
    return model_features


@app.post("/predict")
def predict(limit: int = 10):
    """Lee `limit` filas de la tabla de entrada, predice y guarda el resultado."""
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit debe ser mayor a 0")

    features = _get_selected_features()

    columns = ", ".join(f"`{feature}`" for feature in features)
    input_query = f"SELECT {columns} FROM `{INPUT_TABLE}` LIMIT {limit}"
    input_df = bq_client.query(input_query).result().to_dataframe()

    if input_df.empty:
        raise HTTPException(status_code=404, detail="No hay datos de entrada en la tabla xtest")

    predictions = model.predict(input_df[features])

    now = datetime.now(timezone.utc)
    results_df = pd.DataFrame({
        "row_index": range(len(predictions)),
        "prediction": predictions,
        "created_at": now,
    })

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
    )
    load_job = bq_client.load_table_from_dataframe(results_df, OUTPUT_TABLE, job_config=job_config)
    load_job.result()

    return {
        "rows_processed": len(predictions),
        "predictions": predictions.tolist(),
        "output_table": OUTPUT_TABLE,
    }

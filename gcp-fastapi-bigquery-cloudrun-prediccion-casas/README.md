# API de Predicción en GCP

API con FastAPI que predice precios de vivienda con un modelo de regresión
lineal empaquetado en la imagen Docker. Lee los datos de entrada desde
BigQuery, genera las predicciones y las guarda de vuelta en BigQuery.
Se construye con Cloud Build, se publica en Artifact Registry y se ejecuta
en Cloud Run con una cuenta de servicio personalizada.

## Arquitectura

```
BigQuery (selected_features, xtest) -> FastAPI en Cloud Run -> modelo local -> BigQuery (predictions)
```

## Recursos de GCP utilizados

| Recurso | Valor |
|---|---|
| Proyecto | `mlops17-507600` |
| Dataset BigQuery | `wamayap` |
| Tabla de features | `wamayap.selected_features` |
| Tabla de entrada | `wamayap.xtest` |
| Tabla de salida | `wamayap.predictions` |
| Repositorio Artifact Registry | `ml-repo` (us-central1) |
| Cuenta de servicio Cloud Run | `cloud-run@mlops17-507600.iam.gserviceaccount.com` |

La cuenta de servicio ya cuenta con los roles `roles/bigquery.dataEditor` y
`roles/bigquery.jobUser`, necesarios para leer y escribir en BigQuery.

## Estructura del proyecto

```
gcp-fastapi-prediction/
├── app/
│   └── main.py          # API FastAPI (endpoints /, /health, /predict)
├── model/
│   └── linear_regression.joblib
├── data/                 # CSVs de referencia (no se usan en runtime)
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

## Endpoints

- `GET /` — mensaje de estado.
- `GET /health` — healthcheck para Cloud Run.
- `POST /predict?limit=10` — lee `limit` filas de `xtest`, predice con el
  modelo y agrega los resultados a `predictions`.

## Despliegue

Variables de entorno de shell usadas solo para los comandos (no son
necesarias dentro de la app, que ya trae los valores fijos en el código):

```bash
export PROJECT_ID=mlops17-507600
export REGION=us-central1
export REPO=ml-repo
export IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/api-prediccion:latest
export SERVICE=api-prediccion
export SA=cloud-run@$PROJECT_ID.iam.gserviceaccount.com
```

1. Construir la imagen con Cloud Build y subirla a Artifact Registry:

```bash
gcloud builds submit --tag $IMAGE --project $PROJECT_ID
```

2. Desplegar en Cloud Run con la cuenta de servicio personalizada:

```bash
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --project $PROJECT_ID \
  --service-account $SA \
  --allow-unauthenticated \
  --port 8080
```

3. Probar el endpoint:

```bash
SERVICE_URL=$(gcloud run services describe $SERVICE --region $REGION --project $PROJECT_ID --format='value(status.url)')
curl -X POST "$SERVICE_URL/predict?limit=5"
```

4. Verificar en BigQuery que las predicciones se guardaron:

```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`$PROJECT_ID.wamayap.predictions\` ORDER BY created_at DESC LIMIT 5"
```

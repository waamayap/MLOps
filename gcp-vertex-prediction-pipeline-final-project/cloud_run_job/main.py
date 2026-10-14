"""Cloud Run Job: lanza el pipeline de predicción en Vertex AI.

Cloud Scheduler ejecuta este Job; el Job envía el PipelineJob con la SA personalizada.
"""
import os

from google.cloud import aiplatform


def run_pipeline():
    project = os.environ["PROJECT_ID"]
    location = os.environ.get("LOCATION", "us-central1")

    aiplatform.init(project=project, location=location)

    job = aiplatform.PipelineJob(
        display_name="pipeline-prediction-propension",
        template_path=os.environ["PIPELINE_PATH"],
        enable_caching=False,
        parameter_values={
            "project": project,
            "source_table": os.environ["SOURCE_TABLE"],
            "features_table": os.environ["FEATURES_TABLE"],
            "table_output": os.environ["TABLE_OUTPUT"],
            "prediction_table": os.environ["PREDICTION_TABLE"],
            "path_model": os.environ["MODEL_PATH"],
        },
    )

    print("submit pipeline job ...")
    job.submit(service_account=os.environ["SERVICE_ACCOUNT"])
    print(f"Pipeline enviado: {job.resource_name}")


if __name__ == "__main__":
    run_pipeline()

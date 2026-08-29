# app.py - Flask Application for House Price Prediction
import os
import numpy as np
import pandas as pd
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
import joblib
from io import BytesIO

# Importar configuraciones y preprocessors
from configuraciones import config
import input.preprocessors as pp

app = Flask(__name__)
CORS(app)

# Cargar el pipeline de producción
pipeline = joblib.load('precio_casas_pipeline.joblib')


def prediccion_o_inferencia(pipeline_de_test, datos_de_test):
    """Función para realizar predicciones con el pipeline"""
    # Dropeamos Id si existe
    if 'Id' in datos_de_test.columns:
        datos_de_test.drop('Id', axis=1, inplace=True)
    
    # Cast MSSubClass as object
    datos_de_test['MSSubClass'] = datos_de_test['MSSubClass'].astype('O')
    datos_de_test = datos_de_test[config.FEATURES]

    # Verificar variables con NA que no están contempladas
    new_vars_with_na = [
        var for var in config.FEATURES
        if var not in config.CATEGORICAL_VARS_WITH_NA_FREQUENT +
        config.CATEGORICAL_VARS_WITH_NA_MISSING +
        config.NUMERICAL_VARS_WITH_NA
        and datos_de_test[var].isnull().sum() > 0
    ]
    
    datos_de_test.dropna(subset=new_vars_with_na, inplace=True)

    # Realizar predicciones
    predicciones = pipeline_de_test.predict(datos_de_test)
    predicciones_sin_escalar = np.exp(predicciones)

    return predicciones, predicciones_sin_escalar, datos_de_test


@app.route("/")
def home():
    """Página principal con formulario para subir CSV"""
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    """Procesar CSV y mostrar predicciones"""
    if 'file' not in request.files:
        return render_template("index.html", error="No se seleccionó ningún archivo")
    
    file = request.files['file']
    
    if file.filename == '':
        return render_template("index.html", error="No se seleccionó ningún archivo")
    
    if not file.filename.endswith('.csv'):
        return render_template("index.html", error="El archivo debe ser un CSV")
    
    try:
        # Leer el CSV
        df = pd.read_csv(file)
        
        # Realizar predicciones
        predicciones, predicciones_sin_escalar, datos_procesados = prediccion_o_inferencia(
            pipeline, df.copy()
        )
        
        # Preparar resultados
        df_resultado = datos_procesados.copy()
        df_resultado['Prediccion_Escalada'] = predicciones
        df_resultado['Precio_Predicho_USD'] = predicciones_sin_escalar
        
        # Estadísticas
        stats = {
            'total_registros': len(predicciones),
            'precio_promedio': f"${predicciones_sin_escalar.mean():,.2f}",
            'precio_minimo': f"${predicciones_sin_escalar.min():,.2f}",
            'precio_maximo': f"${predicciones_sin_escalar.max():,.2f}",
        }
        
        # Convertir DataFrame a HTML para mostrar
        tabla_html = df_resultado.head(20).to_html(
            classes='table table-striped table-hover',
            index=False
        )
        
        # Guardar CSV en sesión para descarga
        csv_buffer = BytesIO()
        df_resultado.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        # Guardar temporalmente el resultado
        df_resultado.to_csv('temp_results.csv', index=False)
        
        return render_template(
            "results.html",
            tabla=tabla_html,
            stats=stats,
            total_rows=len(df_resultado)
        )
        
    except Exception as e:
        return render_template("index.html", error=f"Error procesando el archivo: {str(e)}")


@app.route("/download")
def download():
    """Descargar el CSV con predicciones"""
    try:
        return send_file(
            'temp_results.csv',
            mimetype='text/csv',
            as_attachment=True,
            download_name='predicciones_casas.csv'
        )
    except Exception as e:
        return render_template("index.html", error="No hay resultados para descargar")


@app.route("/api", methods=["POST"])
def api():
    """API REST para predicciones programáticas"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    try:
        df = pd.read_csv(file)
        predicciones, predicciones_sin_escalar, _ = prediccion_o_inferencia(
            pipeline, df.copy()
        )
        
        return jsonify({
            "predicciones": predicciones_sin_escalar.tolist(),
            "total": len(predicciones_sin_escalar),
            "promedio": float(predicciones_sin_escalar.mean()),
            "minimo": float(predicciones_sin_escalar.min()),
            "maximo": float(predicciones_sin_escalar.max())
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client
import os
from dotenv import load_dotenv
import pandas as pd
import io
import re
import traceback

load_dotenv()

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Faltan variables de entorno SUPABASE")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RFC_REGEX = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"

df_cache = None
rfc_column_name = None


def cargar_csv_en_memoria():
    global df_cache, rfc_column_name

    if df_cache is None:
        print("📥 Descargando CSV desde Supabase Storage...")

        archivo = supabase.storage.from_("listas-aml") \
            .download("lista_69b_sat.csv")

        df = pd.read_csv(
            io.BytesIO(archivo),
            encoding="latin-1"
        )

        # 🔥 LIMPIAR ENCABEZADOS (BOM + espacios)
        df.columns = (
            df.columns
            .str.strip()
            .str.replace("\ufeff", "", regex=False)
        )

        print("📊 Columnas detectadas:", df.columns.tolist())

        # 🔎 Detectar columna RFC dinámicamente
        for col in df.columns:
            if col.upper() == "RFC":
                rfc_column_name = col
                break

        if not rfc_column_name:
            raise Exception("No se encontró columna RFC en el CSV")

        # Normalizar RFC
        df[rfc_column_name] = (
            df[rfc_column_name]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df_cache = df

        print("✅ CSV cargado en memoria correctamente")

    return df_cache


@app.route("/validate-rfc", methods=["POST"])
def validate_rfc():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Body vacío"}), 400

        rfc = data.get("rfc", "").strip().upper()

        if not rfc:
            return jsonify({"error": "RFC requerido"}), 400

        if not re.match(RFC_REGEX, rfc):
            return jsonify({"error": "Formato RFC inválido"}), 400

        df = cargar_csv_en_memoria()

        resultado = df[df[rfc_column_name] == rfc]

        if not resultado.empty:
            fila = resultado.iloc[0]

            return jsonify({
                "isBlacklisted": True,
                "nombre": fila.get("Nombre del Contribuyente", ""),
                "situacion": fila.get("Situacion del contribuyente", ""),
                "message": "RFC encontrado en lista negra SAT"
            })

        return jsonify({
            "isBlacklisted": False,
            "message": "RFC no encontrado en lista negra SAT"
        })

    except Exception as e:
        print("🔥 ERROR INTERNO:")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
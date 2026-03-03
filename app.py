from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client
import os
from dotenv import load_dotenv
import pandas as pd
import io
import re

load_dotenv()

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RFC_REGEX = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"

df_cache = None


def cargar_csv_en_memoria():
    global df_cache

    if df_cache is None:
        archivo = supabase.storage.from_("listas-aml") \
            .download("lista_69b_sat.csv")

        # IMPORTANTE: encoding correcto
        df_cache = pd.read_csv(
            io.BytesIO(archivo),
            encoding="latin-1"
        )

        # Normalizar columnas
        df_cache.columns = df_cache.columns.str.strip()

        # Normalizar RFC
        df_cache["RFC"] = df_cache["RFC"].astype(str).str.strip().str.upper()

    return df_cache


@app.route("/validate-rfc", methods=["POST"])
def validate_rfc():
    data = request.get_json()
    rfc = data.get("rfc", "").strip().upper()

    if not rfc:
        return jsonify({"error": "RFC requerido"}), 400

    if not re.match(RFC_REGEX, rfc):
        return jsonify({"error": "Formato RFC inválido"}), 400

    try:
        df = cargar_csv_en_memoria()

        resultado = df[df["RFC"] == rfc]

        if not resultado.empty:
            fila = resultado.iloc[0]

            return jsonify({
                "found": True,
                "nombre": fila["Nombre del Contribuyente"],
                "situacion": fila["Situacion del contribuyente"],
                "message": "RFC encontrado en lista negra SAT"
            })

        return jsonify({
            "found": False,
            "message": "RFC no encontrado en lista 69-B"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
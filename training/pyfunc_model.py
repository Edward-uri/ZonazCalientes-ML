import json
import mlflow.pyfunc

class ZonasPyfunc(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        with open(context.artifacts["zonas"], encoding="utf-8") as f:
            self.zonas = json.load(f)  # { "muni|dia_tipo|hora": [ {lat,lng,...} ] }

    def predict(self, context, model_input):
        salidas = []
        for _, row in model_input.iterrows():
            clave = f"{int(row['municipio'])}|{row['dia_tipo']}|{int(row['hora'])}"
            salidas.append(self.zonas.get(clave, []))
        return salidas

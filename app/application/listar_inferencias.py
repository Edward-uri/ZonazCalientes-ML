class ListarInferencias:
    def __init__(self, repo):
        self.repo = repo

    def ejecutar(self, municipio=None, limit=50, offset=0):
        return self.repo.listar(municipio=municipio, limit=limit, offset=offset)

from datetime import datetime
from typing import Any, Dict


class Documento:
    """
    Representa um documento processado, com campos genéricos e
    a flexibilidade para adicionar atributos específicos dinamicamente.
    """

    def __init__(self, nome_arquivo: str, tipo_documento: str = "Não Identificado", **kwargs: Any):
        """
        Inicializa a instância do Documento.

        Args:
            nome_arquivo (str): O nome original do arquivo.
            tipo_documento (str, optional): O tipo do documento (ex: "Nota Fiscal", "Contrato").
                                            Defaults to "Não Identificado".
            **kwargs: Atributos adicionais e específicos do documento (ex: numero_nf="123", valor_total=99.90).
        """
        self.nome_arquivo: str = nome_arquivo
        self.tipo_documento: str = tipo_documento
        self.data_processamento: datetime = datetime.now()
        self.conteudo_extraido: str = ""  # Para armazenar o texto bruto do OCR

        # Adiciona dinamicamente os atributos passados via kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self) -> str:
        """Representação em string do objeto para facilitar a depuração."""
        # Exclui o conteúdo extraído para uma representação mais limpa
        attrs_dict = self.to_dict()
        attrs_dict.pop('conteudo_extraido', None)
        attrs = ", ".join(f"{k}={v!r}" for k, v in attrs_dict.items())
        return f"Documento({attrs})"

    def to_dict(self) -> Dict[str, Any]:
        """Converte os atributos do objeto para um dicionário."""
        # Coleta todos os atributos públicos do objeto
        return {key: getattr(self, key) for key in self.__dict__ if not key.startswith('_')}


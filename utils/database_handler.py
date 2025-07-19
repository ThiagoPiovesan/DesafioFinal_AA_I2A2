import json
import sqlite3
from typing import Dict

from models.document_model import Documento


class DatabaseHandler:
    """
    Gerencia a conexão e as operações com o banco de dados SQLite.
    """

    def __init__(self, db_path: str = "data/documentos.db"):
        """
        Inicializa o handler e cria a tabela se ela não existir.

        Args:
            db_path (str): O caminho para o arquivo do banco de dados SQLite.
        """
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        """Cria a tabela 'documentos' se ela ainda não existir."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS documentos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome_arquivo TEXT NOT NULL,
                        tipo_documento TEXT,
                        data_processamento TEXT NOT NULL,
                        conteudo_extraido TEXT,
                        atributos_especificos TEXT
                    );
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao criar a tabela: {e}")
            raise

    def save_document(self, doc: Documento):
        """
        Salva uma instância de Documento no banco de dados.

        Args:
            doc (Documento): O objeto Documento a ser salvo.
        """
        doc_dict = doc.to_dict()

        # Separa os campos fixos dos atributos específicos
        fixed_keys = ['nome_arquivo', 'tipo_documento', 'data_processamento', 'conteudo_extraido']
        specific_attrs = {k: v for k, v in doc_dict.items() if k not in fixed_keys}

        # Converte os atributos específicos para uma string JSON
        specific_attrs_json = json.dumps(specific_attrs, ensure_ascii=False, default=str)

        sql = """
            INSERT INTO documentos (nome_arquivo, tipo_documento, data_processamento, conteudo_extraido, atributos_especificos)
            VALUES (?, ?, ?, ?, ?);
        """
        values = (doc.nome_arquivo, doc.tipo_documento, doc.data_processamento, doc.conteudo_extraido, specific_attrs_json)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
"""
Ferramenta de consulta ao banco de dados para o agente LangChain.

Permite que o agente busque e analise documentos salvos no banco SQLite.

Salve este arquivo como: utils/database_tool.py
"""

import json
import sqlite3
from typing import List, Dict, Any, Optional
from langchain.tools import Tool


class DatabaseQueryTool:
    """Ferramenta para consultar documentos no banco de dados."""
    
    def __init__(self, db_path: str = "data/documentos.db"):
        self.db_path = db_path
    
    def _executar_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executa uma query e retorna resultados como lista de dicionários."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Converter para lista de dicionários com tratamento seguro
            resultados = []
            for row in rows:
                try:
                    resultados.append(dict(row))
                except Exception as e:
                    # Se falhar, criar dict manualmente
                    result_dict = {}
                    for key in row.keys():
                        try:
                            result_dict[key] = row[key]
                        except:
                            result_dict[key] = None
                    resultados.append(result_dict)
            
            conn.close()
            return resultados
            
        except sqlite3.OperationalError as e:
            # Tabela não existe ou erro de SQL
            return []
        except Exception as e:
            return [{"erro": f"Erro ao executar query: {str(e)}"}]
    
    def listar_todos_documentos(self, input_text: str = "") -> str:
        """
        Lista todos os documentos no banco de dados.
        
        Returns:
            str: JSON com lista de documentos
        """
        query = """
            SELECT id, nome_arquivo, tipo_documento, 
                   data_processamento
            FROM documentos
            ORDER BY data_processamento DESC
        """
        
        resultados = self._executar_query(query)
        
        if not resultados:
            return "Nenhum documento encontrado no banco de dados."
        
        # Resumo dos documentos (sem conteúdo completo)
        resumo = []
        for doc in resultados:
            resumo.append({
                "id": doc.get("id"),
                "nome_arquivo": doc.get("nome_arquivo"),
                "tipo_documento": doc.get("tipo_documento"),
                "data_processamento": doc.get("data_processamento")
            })
        
        return json.dumps(resumo, indent=2, ensure_ascii=False)
    
    def buscar_por_id(self, doc_id: str) -> str:
        """
        Busca um documento específico por ID.
        
        Args:
            doc_id: ID do documento (pode ser string no formato "id: 123")
            
        Returns:
            str: JSON com dados completos do documento
        """
        # Extrair número do ID se vier no formato "id: 123"
        try:
            if ":" in doc_id:
                doc_id = doc_id.split(":")[-1].strip()
            doc_id = int(doc_id)
        except (ValueError, TypeError):
            return f"ID inválido: {doc_id}. Use um número inteiro."
        
        query = """
            SELECT * FROM documentos
            WHERE id = ?
        """
        
        resultados = self._executar_query(query, (doc_id,))
        
        if not resultados:
            return f"Documento com ID {doc_id} não encontrado."
        
        doc = resultados[0]
        
        # Tentar parsear conteudo_extraido se for JSON
        if doc.get("conteudo_extraido"):
            try:
                doc["conteudo_extraido"] = json.loads(doc["conteudo_extraido"])
            except:
                pass  # Manter como string se não for JSON
        
        return json.dumps(doc, indent=2, ensure_ascii=False)
    
    def buscar_por_tipo(self, tipo: str) -> str:
        """
        Busca documentos por tipo.
        
        Args:
            tipo: Tipo do documento (ex: "Nota Fiscal", "NFe")
            
        Returns:
            str: JSON com lista de documentos
        """
        query = """
            SELECT id, nome_arquivo, tipo_documento, data_processamento
            FROM documentos
            WHERE tipo_documento LIKE ?
            ORDER BY data_processamento DESC
        """
        
        resultados = self._executar_query(query, (f"%{tipo}%",))
        
        if not resultados:
            return f"Nenhum documento do tipo '{tipo}' encontrado."
        
        return json.dumps(resultados, indent=2, ensure_ascii=False)
    
    def buscar_por_periodo(self, data_inicio: str, data_fim: str = None) -> str:
        """
        Busca documentos por período.
        
        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD), opcional
            
        Returns:
            str: JSON com lista de documentos
        """
        if data_fim:
            query = """
                SELECT id, nome_arquivo, tipo_documento, data_processamento
                FROM documentos
                WHERE date(data_processamento) BETWEEN ? AND ?
                ORDER BY data_processamento DESC
            """
            resultados = self._executar_query(query, (data_inicio, data_fim))
        else:
            query = """
                SELECT id, nome_arquivo, tipo_documento, data_processamento
                FROM documentos
                WHERE date(data_processamento) >= ?
                ORDER BY data_processamento DESC
            """
            resultados = self._executar_query(query, (data_inicio,))
        
        if not resultados:
            return f"Nenhum documento encontrado no período especificado."
        
        return json.dumps(resultados, indent=2, ensure_ascii=False)
    
    def buscar_por_texto(self, texto_busca: str) -> str:
        """
        Busca documentos que contenham um texto específico.
        
        Args:
            texto_busca: Texto a buscar (nome, CNPJ, etc)
            
        Returns:
            str: JSON com lista de documentos
        """
        query = """
            SELECT id, nome_arquivo, tipo_documento, data_processamento, conteudo_extraido
            FROM documentos
            WHERE nome_arquivo LIKE ? 
               OR tipo_documento LIKE ?
               OR conteudo_extraido LIKE ?
            ORDER BY data_processamento DESC
        """
        
        pattern = f"%{texto_busca}%"
        resultados = self._executar_query(query, (pattern, pattern, pattern))
        
        if not resultados:
            return f"Nenhum documento encontrado com '{texto_busca}'."
        
        # Resumo (sem conteúdo completo para não sobrecarregar)
        resumo = []
        for doc in resultados:
            resumo.append({
                "id": doc["id"],
                "nome_arquivo": doc["nome_arquivo"],
                "tipo_documento": doc["tipo_documento"],
                "data_processamento": doc["data_processamento"]
            })
        
        return json.dumps(resumo, indent=2, ensure_ascii=False)
    
    def calcular_total_notas(self, input_text: str = "") -> str:
        """
        Calcula o valor total de todas as notas fiscais no banco.
        
        Returns:
            str: Informações sobre totais
        """
        # Primeiro, tentar buscar valores de diferentes estruturas JSON
        query = """
            SELECT conteudo_extraido
            FROM documentos
            WHERE conteudo_extraido IS NOT NULL
        """
        
        resultados = self._executar_query(query)
        
        if not resultados:
            return "Nenhum documento encontrado no banco de dados."
        
        total_docs = 0
        soma_valores = 0.0
        
        for row in resultados:
            try:
                conteudo = row.get("conteudo_extraido", "{}")
                if isinstance(conteudo, str):
                    dados = json.loads(conteudo)
                else:
                    dados = conteudo
                
                # Tentar diferentes caminhos para o valor
                valor = None
                
                # Caminho 1: valor_total direto
                if "valor_total" in dados:
                    valor = dados["valor_total"]
                
                # Caminho 2: valores.valor_total (XML NFe)
                elif "valores" in dados and isinstance(dados["valores"], dict):
                    valor = dados["valores"].get("valor_total")
                
                # Caminho 3: valor_nf ou vNF
                elif "valor_nf" in dados:
                    valor = dados["valor_nf"]
                
                if valor is not None:
                    try:
                        soma_valores += float(valor)
                        total_docs += 1
                    except (ValueError, TypeError):
                        pass
                        
            except (json.JSONDecodeError, Exception):
                continue
        
        if total_docs == 0:
            return "Nenhuma nota fiscal com valor encontrada no banco de dados."
        
        return f"""Estatísticas das Notas Fiscais:
- Total de documentos com valores: {total_docs}
- Soma total dos valores: R$ {soma_valores:.2f}"""
    
    def verificar_banco(self, input_text: str = "") -> str:
        """
        Verifica a estrutura e conteúdo do banco de dados.
        Útil para debug.
        
        Returns:
            str: Informações sobre o banco
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar se tabela existe
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='documentos'
            """)
            tabela_existe = cursor.fetchone() is not None
            
            if not tabela_existe:
                conn.close()
                return "A tabela 'documentos' não existe no banco de dados."
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM documentos")
            total = cursor.fetchone()[0]
            
            # Verificar colunas
            cursor.execute("PRAGMA table_info(documentos)")
            colunas = [row[1] for row in cursor.fetchall()]
            
            # Pegar exemplo de registro
            cursor.execute("SELECT * FROM documentos LIMIT 1")
            exemplo = cursor.fetchone()
            
            conn.close()
            
            info = f"""Informações do Banco de Dados:
- Tabela 'documentos': {'Existe' if tabela_existe else 'Não existe'}
- Total de registros: {total}
- Colunas: {', '.join(colunas)}
- Exemplo de registro existe: {'Sim' if exemplo else 'Não'}"""
            
            return info
            
        except Exception as e:
            return f"Erro ao verificar banco: {e}"
    
    def get_tools(self) -> List[Tool]:
        """
        Retorna lista de ferramentas LangChain para o agente.
        
        Returns:
            List[Tool]: Lista de ferramentas
        """
        return [
            Tool(
                name="listar_documentos",
                func=self.listar_todos_documentos,
                description="Lista todos os documentos salvos no banco de dados. Use quando o usuário perguntar 'quais documentos tenho' ou 'liste as notas'."
            ),
            Tool(
                name="buscar_documento_por_id",
                func=self.buscar_por_id,
                description="Busca um documento específico pelo ID. Input deve ser o número do ID. Use quando o usuário mencionar um ID específico como 'mostre o documento 5'."
            ),
            Tool(
                name="buscar_por_tipo",
                func=self.buscar_por_tipo,
                description="Busca documentos por tipo (NFe, Nota Fiscal, etc). Input deve ser o tipo do documento. Use quando perguntar 'mostre as NFes' ou 'liste notas fiscais'."
            ),
            Tool(
                name="buscar_por_texto",
                func=self.buscar_por_texto,
                description="Busca documentos que contenham um texto específico (nome de empresa, CNPJ, etc). Input é o texto a buscar. Use para 'encontre documentos da empresa X'."
            ),
            Tool(
                name="calcular_totais",
                func=self.calcular_total_notas,
                description="Calcula o valor total de todas as notas fiscais. Use quando perguntar 'qual o total das notas' ou 'some os valores'."
            ),
            Tool(
                name="verificar_banco",
                func=self.verificar_banco,
                description="Verifica a estrutura do banco de dados. Use para debug ou quando houver problemas de acesso aos dados."
            ),
        ]


# ==================== EXEMPLO DE USO ====================

"""
# No seu código principal:

from utils.database_tool import DatabaseQueryTool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate

# Criar ferramenta de banco
db_tool = DatabaseQueryTool(db_path="data/documentos.db")
tools = db_tool.get_tools()

# Criar agente
llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Você é um assistente de análise de documentos fiscais..."),
    ("human", "{input}"),
    ("assistant", "{agent_scratchpad}")
])

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Usar
response = agent_executor.invoke({
    "input": "Quais documentos eu tenho salvos?"
})
print(response['output'])
"""
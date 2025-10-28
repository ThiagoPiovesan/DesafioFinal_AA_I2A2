import os
import json
import base64
from io import BytesIO
from typing import Optional, Dict, Any

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationSummaryBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain.schema import HumanMessage, AIMessage
from PIL import Image

# Tentar importar pdf2image, se falhar usar PyPDF2
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    try:
        import PyPDF2
        import fitz  # PyMuPDF
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False


# ==================== FERRAMENTAS CUSTOMIZADAS ====================

class DocumentVisionTool:
    """Ferramenta para extrair dados de documentos usando GPT-4 Vision."""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.ultimo_documento = None  # Armazena último doc processado
    
    def _converter_para_base64(self, uploaded_file) -> str:
        """Converte PDF ou imagem para base64."""
        if uploaded_file.name.endswith('.pdf'):
            # Converter PDF para imagem (primeira página)
            pdf_bytes = uploaded_file.getvalue()
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=400)
            
            buffered = BytesIO()
            images[0].save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        else:
            # Imagem direta
            image_bytes = uploaded_file.getvalue()
            return base64.b64encode(image_bytes).decode()
    
    def extrair_dados(self, uploaded_file) -> str:
        """
        Extrai dados estruturados de uma nota fiscal usando Vision.
        
        Args:
            uploaded_file: Arquivo do Streamlit
            
        Returns:
            str: JSON com dados extraídos
        """
        try:
            image_base64 = self._converter_para_base64(uploaded_file)
            
            prompt = """
            Analise esta nota fiscal e extraia as seguintes informações em formato JSON:

            {
                "tipo_documento": "Nota Fiscal Eletrônica" ou "Nota Fiscal",
                "numero_nf": "número da nota",
                "chave_acesso": "chave de 44 dígitos se disponível",
                "data_emissao": "YYYY-MM-DD",
                "emitente": {
                    "nome": "razão social",
                    "cnpj": "00.000.000/0000-00",
                    "endereco": "endereço completo"
                },
                "destinatario": {
                    "nome": "razão social",
                    "cnpj_cpf": "documento"
                },
                "valor_total": 0.00,
                "impostos": {
                    "icms": 0.00,
                    "ipi": 0.00,
                    "pis": 0.00,
                    "cofins": 0.00
                },
                "itens": [
                    {
                        "codigo": "código do produto",
                        "descricao": "descrição",
                        "quantidade": 0,
                        "valor_unitario": 0.00,
                        "valor_total": 0.00
                    }
                ]
            }

            IMPORTANTE:
            - Retorne APENAS o JSON, sem texto adicional
            - Se algum campo não estiver visível, use null
            - Seja preciso com valores numéricos
            """
            
            # Usar o LLM com vision
            messages = [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                        }
                    ]
                )
            ]
            
            response = self.llm.invoke(messages)
            resultado = response.content
            
            # Limpar a resposta (remover markdown, texto extra)
            resultado = resultado.strip()
            
            # Tentar extrair JSON se estiver envolto em markdown
            if "```json" in resultado:
                resultado = resultado.split("```json")[1].split("```")[0].strip()
            elif "```" in resultado:
                resultado = resultado.split("```")[1].split("```")[0].strip()
            
            # Tentar parsear JSON para validar
            dados = json.loads(resultado)
            self.ultimo_documento = dados  # Armazena para referência futura
            
            return json.dumps(dados, indent=2, ensure_ascii=False)
            
        except json.JSONDecodeError:
            return f"Dados extraídos (formato não-JSON):\n{resultado}"
        except Exception as e:
            return f"Erro ao processar documento: {str(e)}"


class DocumentQueryTool:
    """Ferramenta para responder perguntas sobre documentos já processados."""
    
    def __init__(self, vision_tool: DocumentVisionTool):
        self.vision_tool = vision_tool
    
    def consultar(self, pergunta: str) -> str:
        """
        Responde perguntas sobre o último documento processado.
        
        Args:
            pergunta: Pergunta do usuário
            
        Returns:
            str: Resposta baseada no documento
        """
        if not self.vision_tool.ultimo_documento:
            return "Nenhum documento foi processado ainda. Por favor, processe um documento primeiro."
        
        contexto = json.dumps(self.vision_tool.ultimo_documento, indent=2, ensure_ascii=False)
        
        return f"""
        Baseado no documento processado, aqui estão as informações relevantes:
        
        {contexto}
        
        Para sua pergunta: "{pergunta}"
        
        Analise o contexto acima e forneça uma resposta precisa.
        """


# ==================== CRIAÇÃO DO AGENTE ====================

def create_document_agent(api_key: str, uploaded_file=None) -> AgentExecutor:
    """
    Cria um agente LangChain para processar documentos fiscais com Vision.

    Args:
        api_key (str): A chave de API da OpenAI
        uploaded_file: Arquivo opcional para processar

    Returns:
        AgentExecutor: O agente executor da LangChain
    """
    
    os.environ["OPENAI_API_KEY"] = api_key
    
    # LLM com suporte a Vision
    llm = ChatOpenAI(
        temperature=0,  # Determinístico para extração
        model="gpt-4o",  # Modelo com capacidade de Vision
        max_tokens=2000
    )
    
    # Instanciar ferramentas customizadas
    vision_tool_instance = DocumentVisionTool(llm)
    query_tool_instance = DocumentQueryTool(vision_tool_instance)
    
    # Definir ferramentas do agente
    tools = []
    
    # Ferramenta 1: Processar documento
    if uploaded_file:
        def processar_wrapper(input_text: str) -> str:
            """Wrapper para processar o arquivo carregado."""
            resultado = vision_tool_instance.extrair_dados(uploaded_file)
            # Garantir que retorna só o JSON, sem explicações
            return f"Documento processado com sucesso. Dados extraídos:\n{resultado}"
        
        tools.append(
            Tool(
                name="processar_documento",
                description="Analisa uma nota fiscal (imagem ou PDF) e extrai todos os dados estruturados: emitente, destinatário, itens, valores, impostos. Use esta ferramenta quando precisar processar um novo documento.",
                func=processar_wrapper
            )
        )
    
    # Ferramenta 2: Consultar documento
    tools.append(
        Tool(
            name="consultar_documento",
            description="Responde perguntas sobre o documento já processado. Use para responder questões como: 'Qual o valor total?', 'Quem é o emitente?', 'Quantos itens tem?', etc.",
            func=query_tool_instance.consultar
        )
    )
    
    # Memória conversacional
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        max_token_limit=1500,
        memory_key="chat_history",
        return_messages=True,
        output_key="output"  # Define explicitamente a chave de saída
    )
    
    # Prompt do agente
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        Você é um assistente especializado em análise de documentos fiscais brasileiros.
        
        Você tem acesso às seguintes ferramentas:
        {tools}
        
        Nomes das ferramentas: {tool_names}
        
        INSTRUÇÕES:
        1. Se o usuário pedir para processar/analisar um documento, use a ferramenta 'processar_documento'
        2. Se o usuário fizer perguntas sobre um documento já processado, use 'consultar_documento'
        3. Sempre seja preciso com valores monetários e datas
        4. Se não tiver certeza, peça esclarecimentos ao usuário
        
        FORMATO DE RESPOSTA (ReAct):
        
        Question: [pergunta do usuário]
        Thought: [seu raciocínio sobre o que fazer]
        Action: [nome da ferramenta]
        Action Input: [entrada para a ferramenta]
        Observation: [resultado da ferramenta]
        ... (repita Thought/Action/Action Input/Observation se necessário)
        Thought: Agora sei a resposta final
        Final Answer: [resposta clara e objetiva para o usuário]
        
        Se você já souber a resposta sem usar ferramentas, vá direto para Final Answer.
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("assistant", "{agent_scratchpad}")
    ])
    
    # Criar o agente ReAct
    agent_runnable = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    # Executor do agente
    agent_executor = AgentExecutor(
        agent=agent_runnable,
        tools=tools,
        memory=memory,
        verbose=True,  # Debug no terminal
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True
    )
    
    return agent_executor


def get_agent_response(agent_executor: AgentExecutor, user_query: str) -> Dict[str, Any]:
    """
    Executa uma consulta no agente.

    Args:
        agent_executor: O agente executor
        user_query: A pergunta do usuário

    Returns:
        dict: Dicionário com 'output' e 'intermediate_steps'
    """
    try:
        response = agent_executor.invoke({"input": user_query})
        return response
    
    except Exception as e:
        return {
            "output": f"Ocorreu um erro: {str(e)}",
            "intermediate_steps": []
        }

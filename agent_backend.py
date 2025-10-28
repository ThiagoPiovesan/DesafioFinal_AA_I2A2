import os
import pandas as pd
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_experimental.tools import PythonAstREPLTool
from langchain.memory import ConversationSummaryBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage
# from langchain import hub # Para baixar prompts testados pela comunidade

# --- Configuração Inicial (Chave de API e DataFrame de Exemplo) ---

def create_agent(api_key: str, llm_provider: str, df: pd.DataFrame):
    """
    Cria um agente LangChain para interagir com um DataFrame do pandas.

    Args:
        api_key (str): A chave de API para o provedor de LLM.
        llm_provider (str): O provedor de LLM a ser usado (atualmente apenas 'OpenAI').
        df (pd.DataFrame): O DataFrame do pandas a ser analisado.

    Returns:
        O agente executor da LangChain.
    """

    os.environ["OPENAI_API_KEY"] = api_key

    if llm_provider == "OpenAI":
        llm = ChatOpenAI(temperature=0, model="gpt-4o") # Usamos temperatura 0 para respostas mais determinísticas
    else:
        # Placeholder para outros modelos
        st.error(f"Provedor de LLM '{llm_provider}' ainda não é suportado.")
        return None

    # FERRAMENTAS: As ações que o agente pode tomar
    # Criamos a ferramenta para analisar o dataframe.
    # Passamos o df para o contexto da ferramenta para que ela possa acessá-lo.
    pandas_tool = PythonAstREPLTool(
        name="analista_de_dados_pandas",
        description="Uma ferramenta para análise de dados usando pandas. Recebe código python como entrada para ser executado em um dataframe chamado 'df'. Use esta ferramenta para responder perguntas sobre os dados, fazer cálulos, agregações e visualizações.",
        locals={"df": df}
    )
    
    # Criamos a ferramenta para gerar gráficos com matplotlib.
    matplotlib_tool = PythonAstREPLTool(
        name="gerador_de_graficos_matplotlib",
        description="Uma ferramenta para gerar gráficos usando matplotlib. Recebe código python como entrada para ser executado.",
        locals={"df": df}
    )

    # Criamos a ferramenta para gerar gráficos com numpy.
    numpy_tool = PythonAstREPLTool(
        name="gerador_de_graficos_numpy",
        description="Uma ferramenta para gerar gráficos usando numpy. Recebe código python como entrada para ser executado.",
        locals={"df": df}
    )

    tools = [pandas_tool, matplotlib_tool, numpy_tool]
    tool_names = [tool.name for tool in tools]
    
    # MEMÓRIA: Gerenciador de histórico de conversa
    # - Resume a conversa antiga para não estourar o limite de tokens.
    # - Mantém as mensagens mais recentes em buffer para contexto imediato.
    # - max_token_limit define o tamanho do buffer antes de começar a resumir.
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        max_token_limit=1500,
        memory_key="chat_history", # A chave que o prompt usará
        return_messages=True # Retorna os objetos de mensagem, não apenas strings
    )
    
    prefix = """
        Você é um agente de ciência de dados. Sua principal função é analisar o dataframe fornecido.
        Quando uma pergunta exigir a criação de um gráfico, por favor, gere o código python necessário
        e coloque-o dentro de um bloco de código ```python. NÃO use st.pyplot() ou qualquer outra
        função do streamlit, apenas o código matplotlib puro. Salve o gráfico em 'temp_chart.png'.    
        
    """
    
    # PROMPT: As instruções do agente
    # -> Agentes do tipo "ReAct" (Reasoning and Acting).
    # Dando erro:
    # prompt = hub.pull("hwchase17/react-chat")

    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history", message_type=HumanMessage),
        ("system", """ 
            Você é um agente de ciência de dados. Sua principal função é analisar o dataframe 'df' fornecido.
            
            Quando uma pergunta exigir a criação de um gráfico, por favor, gere o código python necessário usando a ferramenta disponível. NÃO use st.pyplot() ou qualquer outra função do streamlit, apenas o código matplotlib puro. Salve o gráfico em 'temp_chart.png'.

            Para responder às perguntas do usuário, você tem acesso às seguintes ferramentas:
            {tools}
            
            Siga ESTE FORMATO para responder.

            Question: A pergunta do usuário que você precisa responder.
            Thought: explique o que você vai fazer
            Action: o nome da ferramenta a ser usada [{tool_names}].
            Action Input: a entrada para a ferramenta
            Observation: resultado da ferramenta (preenchido após execução)
            ... (repita Thought/Action/Action Input/Observation quantas vezes forem necessárias)

            Se você estiver travado, volte e tente novamente. Pense passo a passo.
            
            Thought: Finalmente, agora eu sei a resposta final.
            Final Answer: resposta para o usuário.
            
            Quando você já souber a resposta final e não precisar de nenhuma ferramenta, 
            apenas escreva diretamente a resposta para o usuário, sem usar Action.
            
            """),
        ("human", "{input} \n"),
        ("system", "{agent_scratchpad}")
    ])
    
    # --- 2. Criação e Execução do Agente ---

    # CRIAÇÃO DO AGENTE
    # O "agente" em si é um 'runnable' que une o LLM e o Prompt.
    # Ele decide qual ferramenta usar, mas não a executa.

    agent_runnable = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )

    # EXECUTOR DO AGENTE
    # O AgentExecutor é o que realmente executa as ferramentas e gerencia o loop.
    # É aqui que conectamos a memória.
    agent_executor = AgentExecutor(
        agent=agent_runnable,
        prefix=prefix,
        tools=tools,
        memory=memory,
        verbose=True, # Mostra o "pensamento" do agente no terminal
        handle_parsing_errors=True, # Lida com erros de formatação da resposta do LLM
        max_iterations=10 # Previne loops infinitos
    )
    
    return agent_executor

def get_agent_response(agent_executor, user_query: str, chat_history: list):
    """
    Executa uma consulta no agente, incluindo o histórico da conversa para dar contexto.

    Args:
        agent: O agente executor da LangChain.
        user_query (str): A pergunta do usuário.
        chat_history (list): O histórico da conversa (lista de tuplas).

    Returns:
        dict: Um dicionário contendo a resposta do agente.
    """
    try:
        response = agent_executor.invoke({
                "input": user_query,
                "chat_history": chat_history
            })
        return response
    
    except Exception as e:
        # A mensagem de erro original já é bem informativa
        return {"output": f"Ocorreu um erro ao processar sua pergunta: {e}"}
    

# === Código Antigo Operações Manuais ===
# import os
# import pandas as pd
# import streamlit as st
# import matplotlib.pyplot as plt
# from langchain_openai import OpenAI
# from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

# def create_agent(api_key: str, llm_provider: str, df: pd.DataFrame):
#     """
#     Cria um agente LangChain para interagir com um DataFrame do pandas.

#     Args:
#         api_key (str): A chave de API para o provedor de LLM.
#         llm_provider (str): O provedor de LLM a ser usado (atualmente apenas 'OpenAI').
#         df (pd.DataFrame): O DataFrame do pandas a ser analisado.

#     Returns:
#         O agente executor da LangChain.
#     """
#     os.environ["OPENAI_API_KEY"] = api_key

#     if llm_provider == "OpenAI":
#         llm = OpenAI(temperature=0) # Usamos temperatura 0 para respostas mais determinísticas
#     else:
#         # Placeholder para outros modelos
#         st.error(f"Provedor de LLM '{llm_provider}' ainda não é suportado.")
#         return None

#     # O prefixo instrui o agente a gerar o código para os gráficos
#     prefix = """
#     Você é um agente de ciência de dados. Sua principal função é analisar o dataframe fornecido.
#     Quando uma pergunta exigir a criação de um gráfico, por favor, gere o código python necessário
#     e coloque-o dentro de um bloco de código ```python. NÃO use st.pyplot() ou qualquer outra
#     função do streamlit, apenas o código matplotlib puro. Salve o gráfico em 'temp_chart.png'.
#     """

#     agent = create_pandas_dataframe_agent(
#         llm,
#         df,
#         prefix=prefix,
#         verbose=True, # verbose=True ajuda a ver o "raciocínio" do agente no terminal
#         handle_parsing_errors=True, # Lida com possíveis erros de parsing da resposta do LLM
#         allow_dangerous_code=True # Permite a execução de código gerado pelo LLM
#     )
#     return agent

# def get_agent_response(agent, user_query: str, chat_history: list):
#     """
#     Executa uma consulta no agente, incluindo o histórico da conversa para dar contexto.

#     Args:
#         agent: O agente executor da LangChain.
#         user_query (str): A pergunta do usuário.
#         chat_history (list): O histórico da conversa (lista de tuplas).

#     Returns:
#         dict: Um dicionário contendo a resposta do agente.
#     """
#     # Formata o histórico e a nova pergunta em uma única entrada
#     formatted_history = "\n".join([f"{sender}: {message}" for sender, message in chat_history])
    
#     # Constrói a entrada final que será enviada ao agente
#     # O histórico anterior dá contexto para a nova pergunta
#     final_input = f"""
#     Você é um agente de ciência de dados. Analise o dataframe para responder às perguntas.
    
#     Histórico da conversa anterior:
#     {formatted_history}

#     Baseado na conversa anterior e no dataframe, responda à nova pergunta do usuário: '{user_query}'.

#     Com base no histórico e na nova pergunta, forneça sua análise e resposta.
#     Lembre-se: se um gráfico for necessário, gere o código matplotlib para criá-lo
#     e salvá-lo como 'temp_chart.png'.
#     """

#     try:
#         # A entrada para o .invoke() deve ser o mais direta possível
#         response = agent.invoke({"input": final_input})
#         return response
#     except Exception as e:
#         # A mensagem de erro original já é bem informativa
#         return {"output": f"Ocorreu um erro ao processar sua pergunta: {e}"}
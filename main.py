import io
import os
import json
import zipfile
import pandas as pd
import streamlit as st
from types import SimpleNamespace

# Importações das nossas classes
from models.document_model import Documento
from utils.database_handler import DatabaseHandler

# --- Configuração da Página ---
st.set_page_config(
    page_title="Sistema de Processamento de Documentos",
    page_icon="📄",
    layout="wide"
)

# --- Cache Resources ---
@st.cache_resource
def load_db_handler():
    """Garante que o diretório de dados exista e carrega o DatabaseHandler."""
    db_dir = "data"
    os.makedirs(db_dir, exist_ok=True)
    return DatabaseHandler(db_path=os.path.join(db_dir, "documentos.db"))

# --- Funções Auxiliares ---

def read_dataframe(uploaded_file):
    """Lê arquivo CSV ou XLSX e retorna um DataFrame com detecção robusta de encoding."""
    try:
        if uploaded_file.name.endswith('.csv'):
            # Lista de encodings comuns no Brasil
            encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252', 'windows-1252']
            
            df = None
            encoding_usado = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(
                        uploaded_file, 
                        encoding=encoding,
                        on_bad_lines='skip',
                        engine='python',
                        sep=None  # Detecta delimitador automaticamente
                    )
                    encoding_usado = encoding
                    break  # Se funcionou, para o loop
                except (UnicodeDecodeError, Exception):
                    continue
            
            if df is None:
                # Última tentativa: forçar latin1 (nunca falha mas pode gerar caracteres estranhos)
                uploaded_file.seek(0)
                df = pd.read_csv(
                    uploaded_file,
                    encoding='latin1',
                    on_bad_lines='skip',
                    engine='python'
                )
                encoding_usado = 'latin1 (forçado)'
            
            st.info(f"📝 Arquivo lido com encoding: **{encoding_usado}**")
            
        else:  # xlsx
            df = pd.read_excel(uploaded_file)
        
        # Limpeza de dados
        df = df.dropna(axis=1, how='all')  # Remove colunas vazias
        df = df.dropna(axis=0, how='all')  # Remove linhas vazias
        
        # Limpar espaços em branco dos nomes das colunas
        df.columns = df.columns.str.strip()
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao ler arquivo: {e}")
        st.info("💡 **Dicas:**\n- Verifique se o arquivo não está corrompido\n- Tente abrir no Excel e salvar novamente como CSV UTF-8")
        return None

def buscar_nf_externa(chave_acesso, api_key=None):
    """
    Busca informações da NF em plataforma externa usando a chave de acesso.
    
    Args:
        chave_acesso: Chave de acesso da NF-e (44 dígitos)
        api_key: Chave da API para autenticação (se necessário)
    
    Returns:
        dict: Dados da NF ou None se falhar
    """
    # TODO: Implementar integração com API externa
    # Exemplos de APIs: SEFAZ, Receita Federal, ou serviços terceiros
    
    st.warning("⚠️ Função de busca externa ainda não implementada")
    
    # Exemplo de estrutura de retorno:
    return {
        'chave_acesso': chave_acesso,
        'numero_nf': 'EXEMPLO',
        'emitente_cnpj': '00.000.000/0000-00',
        'emitente_nome': 'Empresa Exemplo',
        'valor_total': 1000.00,
        'data_emissao': '2025-01-15',
        'status': 'Autorizada'
    }

def processar_csv_para_db(df, db_handler):
    """Salva dados do CSV diretamente no banco."""
    sucesso = 0
    erros = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in df.iterrows():
        try:
            # Adapte os campos conforme sua estrutura
            doc = Documento(
                nome_arquivo=row.get('nome_arquivo', f'documento_{idx}'),
                tipo_documento=row.get('tipo_documento', 'Nota Fiscal'),
                conteudo_extraido=row.get('conteudo_extraido', ''),
                # Adicione outros campos conforme necessário
            )
            
            # Adicionar campos extras se existirem
            if 'chave_acesso' in row:
                doc.chave_acesso = row['chave_acesso']
            if 'valor_total' in row:
                doc.valor_total = row['valor_total']
            
            db_handler.save_document(doc)
            sucesso += 1
        except Exception as e:
            erros += 1
            st.warning(f"Erro ao salvar linha {idx}: {e}")
        
        progress_bar.progress((idx + 1) / len(df))
        status_text.text(f"Processando: {idx + 1}/{len(df)}")
    
    progress_bar.empty()
    status_text.empty()
    
    return sucesso, erros

def processar_csv_com_busca_externa(df, db_handler, api_key=None):
    """Busca informações externas e salva no banco."""
    if 'chave_acesso' not in df.columns:
        st.error("❌ A coluna 'chave_acesso' não foi encontrada no arquivo!")
        return 0, 0
    
    sucesso = 0
    erros = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in df.iterrows():
        try:
            chave = row['chave_acesso']
            status_text.text(f"Buscando informações para chave: {chave[:10]}...")
            
            # Buscar dados externos
            dados_externos = buscar_nf_externa(chave, api_key)
            
            if dados_externos:
                # Criar documento com dados enriquecidos
                doc = Documento(
                    nome_arquivo=f"NF_{dados_externos.get('numero_nf', idx)}",
                    tipo_documento='Nota Fiscal Eletrônica',
                    conteudo_extraido=str(dados_externos)
                )
                
                # Adicionar campos específicos
                for key, value in dados_externos.items():
                    setattr(doc, key, value)
                
                db_handler.save_document(doc)
                sucesso += 1
            else:
                erros += 1
                
        except Exception as e:
            erros += 1
            st.warning(f"Erro ao processar chave {row.get('chave_acesso', 'N/A')}: {e}")
        
        progress_bar.progress((idx + 1) / len(df))
    
    progress_bar.empty()
    status_text.empty()
    
    return sucesso, erros

# --- Interface Principal ---
st.title("📄 Sistema de Processamento de Documentos")

# --- Painel de Estatísticas do Banco ---
try:
    import sqlite3
    conn = sqlite3.connect("data/documentos.db")
    cursor = conn.cursor()
    
    # Contar documentos
    cursor.execute("SELECT COUNT(*) FROM documentos")
    total_docs = cursor.fetchone()[0]
    
    # Contar por tipo
    cursor.execute("SELECT tipo_documento, COUNT(*) FROM documentos GROUP BY tipo_documento")
    tipos = cursor.fetchall()
    
    conn.close()
    
    if total_docs > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 Total de Documentos", total_docs)
        with col2:
            if tipos:
                tipo_principal = tipos[0][0] if tipos[0][0] else "N/A"
                st.metric("📋 Tipo Principal", tipo_principal)
        with col3:
            st.metric("🗂️ Tipos Diferentes", len(tipos))
        
        with st.expander("📊 Ver detalhes por tipo"):
            for tipo, count in tipos:
                st.write(f"- **{tipo or 'Sem tipo'}**: {count} documento(s)")
        
        st.write("---")
except Exception as e:
    pass  # Ignora se o banco ainda não existe

# --- Barra Lateral ---
st.sidebar.header("⚙️ Configurações")
openai_api_key = st.sidebar.text_input(
    "Chave da API OpenAI",
    type="password",
    help="Necessária para extrair informações detalhadas dos documentos."
)

api_externa_key = st.sidebar.text_input(
    "Chave da API Externa (SEFAZ/Outro)",
    type="password",
    help="Para buscar informações de NF-e em plataformas externas."
)

# Carregar Database Handler
try:
    db_handler = load_db_handler()
except Exception as e:
    st.error(f"Falha ao inicializar o banco de dados: {e}")
    st.stop()

# --- Tabs para diferentes modos ---
tab1, tab2 = st.tabs(["📤 Upload de Arquivos", "💬 Chat com IA"])

with tab1:
    st.write("Faça upload de documentos (PDF, XML, DOCX, Imagem, ZIP) ou planilhas (CSV, XLSX).")
    
    uploaded_file = st.file_uploader(
        "Escolha um arquivo",
        type=['pdf', 'xml', 'docx', 'png', 'jpg', 'jpeg', 'zip', 'csv', 'xlsx']
    )
    
    if uploaded_file is not None:
        st.success(f"✅ Arquivo '{uploaded_file.name}' carregado!")
        
        # Detectar tipo de arquivo
        is_csv_xlsx = uploaded_file.name.endswith(('.csv', '.xlsx'))
        is_zip = uploaded_file.name.endswith('.zip')
        is_xml = uploaded_file.name.endswith('.xml')
        
        # --- PROCESSAMENTO CSV/XLSX ---
        if is_csv_xlsx:
            st.subheader("📊 Processamento de Planilha")
            
            df = read_dataframe(uploaded_file)
            
            if df is not None:
                st.write("**Preview dos Dados:**")
                st.dataframe(df.head(10), use_container_width=True)
                
                st.write(f"**Total de registros:** {len(df)}")
                st.write(f"**Colunas:** {', '.join(df.columns.tolist())}")
                
                # Opções de processamento
                st.write("---")
                st.subheader("🔧 Escolha como processar:")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("💾 Salvar Dados Diretos no BD", use_container_width=True):
                        with st.spinner("Salvando dados no banco..."):
                            sucesso, erros = processar_csv_para_db(df, db_handler)
                        
                        if erros == 0:
                            st.success(f"✅ {sucesso} registros salvos com sucesso!")
                        else:
                            st.warning(f"⚠️ {sucesso} salvos, {erros} com erro.")
                
                with col2:
                    if st.button("🔍 Buscar Informações Externas", use_container_width=True):
                        if 'chave_acesso' not in df.columns:
                            st.error("❌ Coluna 'chave_acesso' não encontrada!")
                        else:
                            with st.spinner("Buscando informações externas..."):
                                sucesso, erros = processar_csv_com_busca_externa(
                                    df, db_handler, api_externa_key
                                )
                            
                            if erros == 0:
                                st.success(f"✅ {sucesso} NF-e processadas com sucesso!")
                            else:
                                st.warning(f"⚠️ {sucesso} processadas, {erros} com erro.")
        
        # --- PROCESSAMENTO ZIP ---
        elif is_zip:
            st.subheader("📦 Processamento de Arquivo ZIP")
            
            st.info("O sistema irá extrair e processar automaticamente todos os arquivos suportados dentro do ZIP.")
            
            # Opções de processamento
            with st.expander("⚙️ Opções de Processamento"):
                col1, col2 = st.columns(2)
                with col1:
                    processar_xml = st.checkbox("Processar XML", value=True)
                    processar_pdf = st.checkbox("Processar PDF (Vision)", value=True, 
                                               disabled=not openai_api_key,
                                               help="Requer chave OpenAI")
                with col2:
                    processar_imagens = st.checkbox("Processar Imagens (Vision)", value=True,
                                                   disabled=not openai_api_key,
                                                   help="Requer chave OpenAI")
                    salvar_automatico = st.checkbox("Salvar automaticamente no banco", value=True)
                
                if not openai_api_key:
                    st.warning("⚠️ Configure a chave OpenAI para processar PDF e Imagens")
            
            # Mostrar prévia do conteúdo
            try:
                zip_buffer = io.BytesIO(uploaded_file.getvalue())
                with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                    file_list = [f for f in zip_ref.namelist() 
                                if not f.endswith('/') and not f.startswith('__MACOSX')]
                    
                    st.write(f"**Arquivos encontrados:** {len(file_list)}")
                    
                    # Contar por tipo
                    tipos_encontrados = {}
                    for fname in file_list:
                        ext = fname.split('.')[-1].lower()
                        tipos_encontrados[ext] = tipos_encontrados.get(ext, 0) + 1
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📋 XML", tipos_encontrados.get('xml', 0))
                    with col2:
                        st.metric("📄 PDF", tipos_encontrados.get('pdf', 0))
                    with col3:
                        st.metric("🖼️ Imagens", 
                                 tipos_encontrados.get('png', 0) + 
                                 tipos_encontrados.get('jpg', 0) + 
                                 tipos_encontrados.get('jpeg', 0))
                    with col4:
                        st.metric("📊 Outros", sum(tipos_encontrados.values()) - 
                                 tipos_encontrados.get('xml', 0) - 
                                 tipos_encontrados.get('pdf', 0) - 
                                 tipos_encontrados.get('png', 0) - 
                                 tipos_encontrados.get('jpg', 0) - 
                                 tipos_encontrados.get('jpeg', 0))
                    
                    with st.expander("📋 Ver lista de arquivos"):
                        for fname in file_list:
                            st.write(f"- {fname}")
                            
            except Exception as e:
                st.error(f"Erro ao ler ZIP: {e}")
            
            # Botão para processar
            if st.button("🚀 Processar Todos os Arquivos do ZIP", use_container_width=True):
                
                # Contadores
                processados = 0
                com_sucesso = 0
                com_erro = 0
                nao_suportados = 0
                
                resultados_detalhados = []
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    zip_buffer = io.BytesIO(uploaded_file.getvalue())
                    with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                        file_list = [f for f in zip_ref.namelist() 
                                    if not f.endswith('/') and not f.startswith('__MACOSX')]
                        
                        total_files = len(file_list)
                        
                        for idx, file_name in enumerate(file_list):
                            processados += 1
                            status_text.text(f"Processando {processados}/{total_files}: {file_name}")
                            progress_bar.progress(processados / total_files)
                            
                            # Extrair arquivo
                            with zip_ref.open(file_name) as file_in_zip:
                                file_bytes = file_in_zip.read()
                                
                                # Criar objeto mock do arquivo
                                class MockUploadedFile:
                                    def __init__(self, name, content):
                                        self.name = name
                                        self._content = content
                                    
                                    def getvalue(self):
                                        return self._content
                                    
                                    def read(self):
                                        return self._content
                                
                                mock_file = MockUploadedFile(
                                    name=os.path.basename(file_name),
                                    content=file_bytes
                                )
                                
                                # Processar baseado no tipo
                                ext = file_name.split('.')[-1].lower()
                                resultado = {
                                    "arquivo": file_name,
                                    "tipo": ext,
                                    "status": "Desconhecido",
                                    "mensagem": ""
                                }
                                
                                try:
                                    # XML
                                    if ext == 'xml':
                                        from utils.xml_processor import XMLNFeProcessor
                                        xml_processor = XMLNFeProcessor()
                                        dados = xml_processor.processar_xml(mock_file)
                                        
                                        if "erro" not in dados:
                                            # Salvar no banco
                                            doc = Documento(
                                                nome_arquivo=mock_file.name,
                                                tipo_documento=dados.get('tipo_documento', 'NFe'),
                                                conteudo_extraido=json.dumps(dados, ensure_ascii=False)
                                            )
                                            db_handler.save_document(doc)
                                            
                                            com_sucesso += 1
                                            resultado["status"] = "✅ Sucesso"
                                            resultado["mensagem"] = f"NFe processada - Valor: R$ {dados.get('valores', {}).get('valor_total', 'N/A')}"
                                        else:
                                            com_erro += 1
                                            resultado["status"] = "❌ Erro"
                                            resultado["mensagem"] = dados.get("erro", "Erro desconhecido")
                                    
                                    # PDF ou Imagem (Vision)
                                    elif ext in ['pdf', 'png', 'jpg', 'jpeg'] and openai_api_key:
                                        from utils.document_agent import DocumentVisionTool
                                        from langchain_openai import ChatOpenAI
                                        
                                        llm = ChatOpenAI(temperature=0, model="gpt-4o", max_tokens=2000, api_key=openai_api_key)
                                        vision_tool = DocumentVisionTool(llm)
                                        
                                        dados_json = vision_tool.extrair_dados(mock_file)
                                        
                                        # Salvar no banco
                                        doc = Documento(
                                            nome_arquivo=mock_file.name,
                                            tipo_documento="Documento",
                                            conteudo_extraido=dados_json
                                        )
                                        db_handler.save_document(doc)
                                        
                                        com_sucesso += 1
                                        resultado["status"] = "✅ Sucesso"
                                        resultado["mensagem"] = "Processado com Vision"
                                    
                                    elif ext in ['pdf', 'png', 'jpg', 'jpeg'] and not openai_api_key:
                                        nao_suportados += 1
                                        resultado["status"] = "⚠️ Pulado"
                                        resultado["mensagem"] = "Requer chave OpenAI para processar"
                                    
                                    else:
                                        nao_suportados += 1
                                        resultado["status"] = "⚠️ Não suportado"
                                        resultado["mensagem"] = f"Tipo de arquivo não suportado: {ext}"
                                
                                except Exception as e:
                                    com_erro += 1
                                    resultado["status"] = "❌ Erro"
                                    resultado["mensagem"] = str(e)
                                
                                resultados_detalhados.append(resultado)
                
                except Exception as e:
                    st.error(f"Erro ao processar ZIP: {e}")
                
                # Limpar progress
                progress_bar.empty()
                status_text.empty()
                
                # Mostrar resultados
                st.write("---")
                st.subheader("📊 Resumo do Processamento")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📝 Total Processados", processados)
                with col2:
                    st.metric("✅ Sucesso", com_sucesso, delta=None, delta_color="normal")
                with col3:
                    st.metric("❌ Erros", com_erro, delta=None, delta_color="inverse")
                with col4:
                    st.metric("⚠️ Não Suportados", nao_suportados)
                
                # Tabela de resultados
                if resultados_detalhados:
                    st.write("**Detalhes por arquivo:**")
                    df_resultados = pd.DataFrame(resultados_detalhados)
                    st.dataframe(df_resultados, use_container_width=True)
                    
                    # Opção de download do relatório
                    csv = df_resultados.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Relatório CSV",
                        data=csv,
                        file_name=f"relatorio_processamento_{uploaded_file.name}.csv",
                        mime="text/csv"
                    )
                
                if com_sucesso > 0:
                    st.success(f"🎉 {com_sucesso} documento(s) processado(s) e salvo(s) no banco com sucesso!")
                
                if com_erro > 0:
                    st.warning(f"⚠️ {com_erro} arquivo(s) com erro durante o processamento.")
                
                if nao_suportados > 0:
                    st.info(f"ℹ️ {nao_suportados} arquivo(s) não suportado(s) ou pulado(s).")
        
        # --- PROCESSAMENTO XML ---
        elif is_xml:
            st.subheader("📋 Processamento de XML (NFe)")
            
            from utils.xml_processor import XMLNFeProcessor
            
            xml_processor = XMLNFeProcessor()
            
            if st.button("🔍 Processar XML", use_container_width=True):
                with st.spinner("Processando XML da NFe..."):
                    dados = xml_processor.processar_xml(uploaded_file)
                    dados_json = xml_processor.to_json(dados)
                    
                    st.session_state.dados_xml = dados_json
                    st.session_state.processado_xml = True
                
                st.success("✅ XML processado com sucesso!")
                
                # Exibir dados
                with st.expander("📋 Ver Dados Extraídos", expanded=True):
                    st.json(dados)
                
                # Salvar no banco
                try:
                    doc = Documento(
                        nome_arquivo=uploaded_file.name,
                        tipo_documento=dados.get('tipo_documento', 'NFe'),
                        conteudo_extraido=dados_json
                    )
                    
                    # Adicionar campos específicos
                    campos_salvos = []
                    for key, value in dados.items():
                        if key not in ['tipo_documento', 'conteudo_extraido', 'nome_arquivo']:
                            try:
                                if isinstance(value, (dict, list)):
                                    setattr(doc, key, json.dumps(value, ensure_ascii=False))
                                else:
                                    setattr(doc, key, str(value))
                                campos_salvos.append(key)
                            except:
                                pass
                    
                    db_handler.save_document(doc)
                    st.success(f"💾 NFe salva no banco! ({len(campos_salvos)} campos)")
                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
            
            # Chat sobre XML
            if st.session_state.get('processado_xml'):
                st.write("---")
                st.subheader("💬 Faça Perguntas sobre a NFe")
                
                user_question = st.text_input(
                    "Digite sua pergunta:",
                    placeholder="Ex: Qual o valor total da nota?",
                    key="xml_question"
                )
                
                if user_question and openai_api_key:
                    with st.spinner("Pensando..."):
                        from langchain_openai import ChatOpenAI
                        from langchain.schema import HumanMessage, SystemMessage
                        
                        llm = ChatOpenAI(temperature=0.3, model="gpt-4o", api_key=openai_api_key)
                        
                        messages = [
                            SystemMessage(content=f"""
                            Você é um assistente especializado em Notas Fiscais Eletrônicas.
                            
                            Dados da NFe:
                            {st.session_state.dados_xml}
                            
                            Responda às perguntas de forma clara e objetiva.
                            """),
                            HumanMessage(content=user_question)
                        ]
                        
                        response = llm.invoke(messages)
                        resposta = response.content
                    
                    st.write("**🤖 Resposta:**")
                    st.info(resposta)
        
        # --- PROCESSAMENTO DOCUMENTOS INDIVIDUAIS (PDF/IMAGEM) ---
        else:
            st.subheader("📄 Processamento de Documento com IA")
            
            if not openai_api_key:
                st.warning("⚠️ Configure a chave da API OpenAI na barra lateral para processar documentos.")
            else:
                # Processar documento com Vision diretamente (sem agente complexo)
                
                # Botão para processar
                if st.button("🔍 Processar Documento com IA", use_container_width=True):
                    with st.spinner("Analisando documento..."):
                        # Chamar diretamente a ferramenta Vision (mais simples e confiável)
                        from utils.document_agent import DocumentVisionTool
                        from langchain_openai import ChatOpenAI
                        
                        llm = ChatOpenAI(temperature=0, model="gpt-4o", max_tokens=2000, api_key=openai_api_key)
                        vision_tool = DocumentVisionTool(llm)
                        
                        resultado = vision_tool.extrair_dados(uploaded_file)
                        st.session_state.dados_doc = resultado
                        st.session_state.ultimo_doc_dados = resultado  # Para chat posterior
                        st.session_state.processado = True
                    
                    st.success("✅ Documento processado!")
                    
                    # Debug: mostrar resposta crua
                    with st.expander("🔍 Debug - Resposta Completa do Agente"):
                        st.write("**Tipo:**", type(st.session_state.dados_doc))
                        st.code(st.session_state.dados_doc)
                    
                    # Exibir dados extraídos
                    with st.expander("📋 Ver Dados Extraídos", expanded=True):
                        # Tentar identificar se tem JSON dentro da resposta
                        try:
                            import re
                            # Procurar por JSON na resposta
                            json_match = re.search(r'\{.*\}', st.session_state.dados_doc, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                st.code(json_str, language='json')
                            else:
                                st.code(st.session_state.dados_doc, language='json')
                        except:
                            st.code(st.session_state.dados_doc, language='json')
                    
                    # Salvar no banco
                    try:
                        import json
                        import re
                        
                        # Tentar extrair JSON da resposta
                        dados_str = st.session_state.dados_doc
                        
                        # Tentar parsear direto
                        try:
                            dados_dict = json.loads(dados_str)
                        except json.JSONDecodeError:
                            # Tentar encontrar JSON na string
                            json_match = re.search(r'\{.*\}', dados_str, re.DOTALL)
                            if json_match:
                                dados_dict = json.loads(json_match.group())
                            else:
                                # Se não encontrar, salvar como texto
                                raise ValueError("JSON não encontrado na resposta")
                        
                        doc = Documento(
                            nome_arquivo=uploaded_file.name,
                            tipo_documento=dados_dict.get('tipo_documento', 'Documento'),
                            conteudo_extraido=json.dumps(dados_dict, ensure_ascii=False, indent=2)
                        )
                        
                        # Adicionar campos extras se for dict válido
                        campos_salvos = []
                        for key, value in dados_dict.items():
                            if key not in ['tipo_documento', 'conteudo_extraido', 'nome_arquivo']:
                                try:
                                    # Converter valores complexos para string
                                    if isinstance(value, (dict, list)):
                                        setattr(doc, key, json.dumps(value, ensure_ascii=False))
                                    else:
                                        setattr(doc, key, str(value))
                                    campos_salvos.append(key)
                                except:
                                    pass
                        
                        db_handler.save_document(doc)
                        st.success(f"💾 Dados salvos no banco! ({len(campos_salvos)} campos extras)")
                        
                        if campos_salvos:
                            with st.expander("Ver campos salvos"):
                                st.write(campos_salvos)
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar no banco: {e}")
                        st.write("**Dados que tentamos salvar:**")
                        st.code(st.session_state.dados_doc)
                        
                        # Salvar pelo menos o texto bruto
                        try:
                            doc = Documento(
                                nome_arquivo=uploaded_file.name,
                                tipo_documento='Documento',
                                conteudo_extraido=st.session_state.dados_doc
                            )
                            db_handler.save_document(doc)
                            st.info("💾 Salvou pelo menos o texto bruto no banco.")
                        except Exception as e2:
                            st.error(f"Falha total ao salvar: {e2}")
                
                # Chat sobre o documento
                if st.session_state.get('processado'):
                    st.write("---")
                    st.subheader("💬 Faça Perguntas sobre o Documento")
                    
                    user_question = st.text_input(
                        "Digite sua pergunta:",
                        placeholder="Ex: Qual o valor total da nota?"
                    )
                    
                    if user_question:
                        with st.spinner("Pensando..."):
                            # Usar LLM diretamente com contexto
                            from langchain_openai import ChatOpenAI
                            from langchain.schema import HumanMessage, SystemMessage
                            
                            llm = ChatOpenAI(temperature=0.3, model="gpt-4o", api_key=openai_api_key)
                            
                            messages = [
                                SystemMessage(content=f"""
                                Você é um assistente especializado em análise de documentos fiscais.
                                
                                Aqui estão os dados do documento atual:
                                {st.session_state.dados_doc}
                                
                                Responda às perguntas do usuário baseado nestes dados de forma clara e objetiva.
                                """),
                                HumanMessage(content=user_question)
                            ]
                            
                            response = llm.invoke(messages)
                            resposta = response.content
                        
                        st.write("**🤖 Resposta:**")
                        st.info(resposta)

with tab2:
    st.subheader("💬 Converse com a IA sobre seus Documentos")
    
    if not openai_api_key:
        st.warning("⚠️ Configure a chave da API OpenAI na barra lateral para usar o chat.")
    else:
        import os
        os.environ["OPENAI_API_KEY"] = openai_api_key
        
        from langchain_openai import ChatOpenAI
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain.memory import ConversationBufferMemory
        from utils.database_tool import DatabaseQueryTool
        
        # Inicializar agente (apenas uma vez)
        if 'chat_agent_executor' not in st.session_state:
            with st.spinner("🤖 Inicializando assistente com acesso ao banco..."):
                # Criar ferramentas de banco de dados
                db_tool = DatabaseQueryTool(db_path="data/documentos.db")
                tools = db_tool.get_tools()
                
                # LLM
                llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=openai_api_key)
                
                # Prompt do agente
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """
                    Você é um assistente especializado em análise de documentos fiscais brasileiros.
                    
                    Você tem acesso a um banco de dados com documentos salvos (Notas Fiscais, NFes, etc).
                    
                    Use as ferramentas disponíveis para:
                    - Listar documentos
                    - Buscar documentos específicos
                    - Calcular totais
                    - Analisar dados
                    
                    Ferramentas disponíveis:
                    {tools}
                    
                    Nomes das ferramentas: {tool_names}
                    
                    FORMATO DE RESPOSTA:
                    
                    Question: [pergunta do usuário]
                    Thought: [seu raciocínio]
                    Action: [nome da ferramenta]
                    Action Input: [entrada para ferramenta]
                    Observation: [resultado]
                    ... (repita se necessário)
                    Thought: Agora sei a resposta
                    Final Answer: [resposta clara para o usuário]
                    
                    IMPORTANTE:
                    - Sempre use as ferramentas para buscar dados reais do banco
                    - Seja preciso com valores monetários
                    - Se não encontrar algo, diga claramente
                    - Formate valores em reais: R$ X,XX
                    """),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                    ("assistant", "{agent_scratchpad}")
                ])
                
                # Memória
                memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
                
                # Criar agente
                agent = create_react_agent(llm, tools, prompt)
                
                st.session_state.chat_agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    memory=memory,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=5
                )
        
        st.info("✅ Assistente pronto! Pergunte sobre os documentos salvos no banco.")
        
        # Sugestões de perguntas
        with st.expander("💡 Exemplos de perguntas"):
            st.markdown("""
            - "Quais documentos eu tenho salvos?"
            - "Mostre o documento 5"
            - "Liste todas as NFes"
            - "Qual o valor total de todas as notas?"
            - "Encontre documentos da empresa XYZ"
            - "Mostre as notas de janeiro de 2025"
            """)
        
        # Histórico de chat
        if 'chat_messages' not in st.session_state:
            st.session_state.chat_messages = []
        
        # Exibir mensagens anteriores
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Input do usuário
        if prompt := st.chat_input("Digite sua pergunta sobre os documentos..."):
            # Adicionar mensagem do usuário
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            # Gerar resposta com agente
            with st.chat_message("assistant"):
                with st.spinner("🔍 Consultando banco de dados..."):
                    try:
                        response = st.session_state.chat_agent_executor.invoke({
                            "input": prompt
                        })
                        resposta = response.get('output', 'Não consegui gerar uma resposta.')
                    except KeyError as e:
                        resposta = f"Erro de chave: {e}. Verifique se os dados do banco estão no formato correto."
                        st.error("💡 Dica: Pode ser que a estrutura dos dados no banco esteja inconsistente.")
                    except Exception as e:
                        resposta = f"Erro ao processar: {e}"
                        st.error("💡 Dica: Tente reformular sua pergunta de forma mais específica.")
                        
                        # Debug info
                        with st.expander("🔍 Informações de debug"):
                            st.write("**Erro completo:**")
                            st.code(str(e))
                            st.write("**Tipo de erro:**", type(e).__name__)
                
                st.write(resposta)
            
            # Adicionar resposta ao histórico
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": resposta
            })
        
        # Botão para limpar histórico
        if st.button("🗑️ Limpar Conversa"):
            st.session_state.chat_messages = []
            st.session_state.chat_agent_executor.memory.clear()
            st.rerun()
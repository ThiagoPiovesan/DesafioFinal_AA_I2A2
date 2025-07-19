import io
import os
import zipfile
from types import SimpleNamespace

import streamlit as st

# Importações das nossas classes
from models.document_model import Documento
from utils.ocr_processor import OcrProcessor
from utils.database_handler import DatabaseHandler
from utils.llm_extractor import LlmExtractor

# --- Configuração da Página e Cache ---

st.set_page_config(
    page_title="Sistema de Processamento de Documentos",
    page_icon="📄",
    layout="wide"
)

# Cache do processador OCR para evitar recarregá-lo a cada interação
@st.cache_resource
def load_ocr_processor():
    """Carrega a instância do OcrProcessor."""
    return OcrProcessor()

@st.cache_resource
def load_db_handler():
    """Garante que o diretório de dados exista e carrega o DatabaseHandler."""
    db_dir = "data"
    # Garante que o diretório para o BD exista
    os.makedirs(db_dir, exist_ok=True)
    return DatabaseHandler(db_path=os.path.join(db_dir, "documentos.db"))

@st.cache_resource
def load_llm_extractor(api_key):
    """Carrega a instância do LlmExtractor se a chave da API for fornecida."""
    if api_key:
        return LlmExtractor(api_key=api_key)
    return None

# --- Interface Principal ---

st.title("Sistema de Processamento de Documentos")

# --- Barra Lateral para Configuração ---
st.sidebar.header("Configurações")
openai_api_key = st.sidebar.text_input(
    "Chave da API OpenAI",
    type="password",
    help="Necessária para extrair informações detalhadas dos documentos."
)

st.write("Faça o upload de um ou mais documentos (PDF, XML, DOCX, Imagem) ou um arquivo ZIP.")

# Carrega os handlers
try:
    ocr_processor = load_ocr_processor()
    db_handler = load_db_handler()
    llm_extractor = load_llm_extractor(openai_api_key)
except Exception as e:
    st.error(f"Falha ao inicializar os serviços. Verifique as dependências. Erro: {e}")
    st.stop()  # Interrompe a execução se o OCR não puder ser carregado

# Componente de upload de arquivo
uploaded_file = st.file_uploader(
    "Escolha um arquivo",
    type=['pdf', 'xml', 'docx', 'png', 'jpg', 'jpeg', 'zip']
)

# --- Lógica de Processamento ---

if uploaded_file is not None:
    st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")

    # Função auxiliar para processar um único arquivo e exibir os resultados
    def process_and_display(file_obj):
        with st.spinner(f"Processando '{file_obj.name}'..."):
            try:
                # 1. Extrair texto com o OCR Processor
                extracted_text = ocr_processor.process_file(file_obj)

                # 2. Usar LLM para extrair detalhes (se a chave da API foi fornecida)
                if llm_extractor:
                    st.info("Analisando conteúdo com IA para extrair detalhes...")
                    extracted_details = llm_extractor.extract_details(extracted_text)
                    doc_type = extracted_details.pop('tipo_documento', 'Não Identificado')
                    # Os detalhes restantes serão os atributos específicos
                    doc = Documento(
                        nome_arquivo=file_obj.name,
                        tipo_documento=doc_type,
                        **extracted_details
                    )
                else:
                    # Cria a instância sem os detalhes do LLM
                    doc = Documento(nome_arquivo=file_obj.name)

                doc.conteudo_extraido = extracted_text

                # 3. Salvar no banco de dados
                db_handler.save_document(doc)

                # 4. Exibir resultados
                st.write("---")
                st.success(f"Documento '{doc.nome_arquivo}' salvo no banco de dados!")
                st.subheader(f"Resultados para: {doc.nome_arquivo}")
                st.write(f"**Objeto Documento Criado:**")
                st.json(doc.to_dict())

                with st.expander("Ver Conteúdo Extraído"):
                    st.text(doc.conteudo_extraido)

            except NotImplementedError as e:
                st.warning(f"Aviso para '{file_obj.name}': {e}")
            except Exception as e:
                st.error(f"Falha ao processar '{file_obj.name}': {e}")

    if not openai_api_key:
        st.warning("A chave da API da OpenAI não foi fornecida. A extração detalhada de informações (como tipo de documento, CNPJ, etc.) será desativada.")

    # Lógica para lidar com ZIP ou arquivos únicos
    is_zip = uploaded_file.type == "application/zip" or uploaded_file.name.endswith('.zip')

    if st.button(f"Processar {'Arquivo ZIP' if is_zip else 'Documento'}"):
        if is_zip:
            try:
                zip_buffer = io.BytesIO(uploaded_file.getvalue())
                with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                    for file_name in zip_ref.namelist():
                        # Ignorar diretórios e arquivos ocultos do macOS
                        if file_name.endswith('/') or file_name.startswith('__MACOSX'):
                            continue
                        
                        with zip_ref.open(file_name) as file_in_zip:
                            # Cria um objeto simples que simula o UploadedFile do Streamlit
                            mock_file = SimpleNamespace(
                                name=os.path.basename(file_name),
                                getvalue=file_in_zip.read
                            )
                            process_and_display(mock_file)
            except Exception as e:
                st.error(f"Ocorreu um erro ao ler o arquivo ZIP: {e}")
        else:
            # Processa o arquivo único
            process_and_display(uploaded_file)
import io
import os
import xml.etree.ElementTree as ET

import docx  # python-docx
import numpy as np
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes
from PIL import Image


class OcrProcessor:
    """
    Classe para processar diferentes tipos de arquivos (PDF, Imagens, XML, DOCX)
    e extrair seu conteúdo textual.
    """

    def __init__(self):
        """
        Inicializa o motor PaddleOCR.
        O modelo de linguagem será baixado na primeira execução.
        """
        print("Inicializando o motor OCR (PaddleOCR)... Isso pode levar um momento.")
        # Configurado para português e para corrigir a orientação do texto.
        self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='pt', show_log=False)
        print("Motor OCR pronto.")

    def _process_image_content(self, image_content: bytes) -> str:
        """Função auxiliar para executar OCR em bytes de imagem."""
        try:
            image = Image.open(io.BytesIO(image_content))
            image_np = np.array(image)

            result = self.ocr_engine.ocr(image_np, cls=True)
            
            text_lines = []
            if result and result[0] is not None:
                for line_info in result:
                    for line in line_info:
                        # A estrutura do resultado é [box, (texto, confiança)]
                        text_lines.append(line[1][0])
            return "\n".join(text_lines)
        except Exception as e:
            return f"Erro ao processar imagem: {e}"

    def _process_pdf(self, file_bytes: bytes) -> str:
        """Converte PDF para imagens e extrai texto usando OCR."""
        print("Processando PDF...")
        full_text = []
        try:
            images = convert_from_bytes(file_bytes)
            for i, image in enumerate(images):
                print(f"  Lendo página {i+1}/{len(images)} do PDF...")
                with io.BytesIO() as output:
                    image.save(output, format="PNG")
                    image_bytes = output.getvalue()
                
                page_text = self._process_image_content(image_bytes)
                full_text.append(page_text)
            
            return "\n\n--- Fim da Página ---\n\n".join(full_text)
        except Exception as e:
            if "Poppler" in str(e):
                raise RuntimeError(
                    "Dependência 'Poppler' não encontrada. "
                    "Por favor, instale o Poppler e adicione-o ao PATH do seu sistema. "
                    f"Detalhe do erro: {e}"
                )
            raise e

    def _process_xml(self, file_bytes: bytes) -> str:
        """Extrai conteúdo de texto de um arquivo XML."""
        print("Processando XML...")
        try:
            xml_string = file_bytes.decode('utf-8')
            root = ET.fromstring(xml_string)
            text_content = [elem.text for elem in root.iter() if elem.text and elem.text.strip()]
            return "\n".join(text_content)
        except ET.ParseError as e:
            raise ValueError(f"Erro ao analisar o arquivo XML: {e}")

    def _process_docx(self, file_bytes: bytes) -> str:
        """Extrai texto de um arquivo .docx."""
        print("Processando DOCX...")
        try:
            doc_stream = io.BytesIO(file_bytes)
            document = docx.Document(doc_stream)
            return "\n".join([p.text for p in document.paragraphs if p.text])
        except Exception as e:
            raise ValueError(f"Erro ao ler o arquivo .docx: {e}")

    def process_file(self, uploaded_file) -> str:
        """Identifica o tipo de arquivo e o processa para extrair o texto."""
        file_bytes = uploaded_file.getvalue()
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        if file_extension == '.pdf':
            return self._process_pdf(file_bytes)
        elif file_extension == '.xml':
            return self._process_xml(file_bytes)
        elif file_extension == '.docx':
            return self._process_docx(file_bytes)
        elif file_extension in ['.png', '.jpg', '.jpeg']:
            return self._process_image_content(file_bytes)
        elif file_extension == '.doc':
            raise NotImplementedError("Formato .doc não é suportado. Por favor, converta para .docx ou .pdf.")
        else:
            raise ValueError(f"Tipo de arquivo não suportado: {file_extension}")
import json

from openai import OpenAI


class LlmExtractor:
    """
    Usa um LLM (GPT) para extrair informações estruturadas de um texto.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("A chave da API da OpenAI é necessária para usar o extrator LLM.")
        self.client = OpenAI(api_key=api_key)

    def _build_prompt(self, text: str) -> str:
        """Constrói o prompt para o LLM, instruindo-o a extrair dados em JSON."""
        # Limita o texto para evitar exceder o limite de tokens da API
        max_chars = 12000  # Limite seguro para modelos como gpt-3.5-turbo
        truncated_text = text[:max_chars]

        prompt = f"""
        Analise o texto do documento abaixo e extraia as seguintes informações em formato JSON:
        1. "tipo_documento": Classifique o documento (ex: "Nota Fiscal", "Contrato de Aluguel", "Fatura de Cartão", "CNH", "Orçamento").
        2. "numero_nf": Se for uma nota fiscal, o número dela.
        3. "cnpj_emitente": O CNPJ do emissor do documento, se aplicável.
        4. "nome_emitente": O nome do emissor do documento, se aplicável.
        5. "cnpj_destinatario": O CNPJ do destinatário, se aplicável.
        6. "nome_destinatario": O nome do destinatário, se aplicável.
        7. "data_emissao": A data de emissão do documento (formato AAAA-MM-DD).
        8. "valor_total": O valor total, se for um documento financeiro (formato numérico).

        Se uma informação não for encontrada, omita a chave correspondente do JSON.
        Responda APENAS com o objeto JSON, sem nenhum texto, explicação ou formatação adicional.

        Texto do documento:
        ---
        {truncated_text}
        ---
        """
        return prompt

    def extract_details(self, text: str) -> dict:
        """
        Envia o texto para o LLM e retorna os detalhes extraídos como um dicionário.
        """
        if not text or not text.strip():
            return {"tipo_documento": "Vazio ou ilegível"}

        prompt = self._build_prompt(text)

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-1106",  # Modelo otimizado para seguir instruções e retornar JSON
                messages=[
                    {"role": "system", "content": "Você é um assistente especialista em extração de dados de documentos e responde em formato JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,  # Baixa temperatura para respostas mais determinísticas
            )
            json_response = response.choices[0].message.content
            return json.loads(json_response)
        except Exception as e:
            print(f"Erro ao chamar a API da OpenAI: {e}")
            raise RuntimeError(f"Falha na comunicação com a API da OpenAI: {e}")
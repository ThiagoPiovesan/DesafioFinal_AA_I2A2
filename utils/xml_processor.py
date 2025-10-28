"""
Processador de XML para Notas Fiscais Eletrônicas (NFe).

Suporta:
- NFe com namespace (padrão SEFAZ)
- NFe sem namespace
- Extração completa de dados estruturados

Salve este arquivo como: utils/xml_processor.py
"""

import xml.etree.ElementTree as ET
import json
from typing import Dict, Any, Optional


class XMLNFeProcessor:
    """Processa arquivos XML de Nota Fiscal Eletrônica (NFe)."""
    
    def __init__(self):
        # Namespaces comuns em NFe
        self.namespaces = {
            'nfe': 'http://www.portalfiscal.inf.br/nfe'
        }
    
    def processar_xml(self, uploaded_file) -> Dict[str, Any]:
        """
        Extrai dados estruturados de um XML de NFe.
        
        Args:
            uploaded_file: Arquivo XML do Streamlit
            
        Returns:
            dict: Dados estruturados da NFe
        """
        try:
            # Ler conteúdo do XML
            xml_content = uploaded_file.getvalue().decode('utf-8')
            root = ET.fromstring(xml_content)
            
            # Detectar se tem namespace
            if 'nfe' in xml_content or 'NFe' in xml_content:
                return self._extrair_nfe_com_namespace(root)
            else:
                return self._extrair_nfe_sem_namespace(root)
                
        except ET.ParseError as e:
            return {
                "erro": f"XML inválido: {e}",
                "tipo_documento": "XML Inválido"
            }
        except Exception as e:
            return {
                "erro": f"Erro ao processar: {e}",
                "tipo_documento": "Erro"
            }
    
    def _extrair_nfe_com_namespace(self, root) -> Dict[str, Any]:
        """Extrai dados de NFe com namespace."""
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Buscar elementos principais
        inf_nfe = root.find('.//nfe:infNFe', ns)
        ide = root.find('.//nfe:ide', ns)
        emit = root.find('.//nfe:emit', ns)
        dest = root.find('.//nfe:dest', ns)
        total = root.find('.//nfe:total/nfe:ICMSTot', ns)
        
        dados = {
            "tipo_documento": "Nota Fiscal Eletrônica (NFe)",
            "chave_acesso": inf_nfe.get('Id', '').replace('NFe', '') if inf_nfe is not None else None,
            "numero_nf": self._get_text(ide, 'nfe:nNF', ns),
            "serie": self._get_text(ide, 'nfe:serie', ns),
            "data_emissao": self._get_text(ide, 'nfe:dhEmi', ns) or self._get_text(ide, 'nfe:dEmi', ns),
            "modelo": self._get_text(ide, 'nfe:mod', ns),
            "natureza_operacao": self._get_text(ide, 'nfe:natOp', ns),
        }
        
        # Emitente
        if emit is not None:
            dados["emitente"] = {
                "nome": self._get_text(emit, 'nfe:xNome', ns),
                "nome_fantasia": self._get_text(emit, 'nfe:xFant', ns),
                "cnpj": self._get_text(emit, 'nfe:CNPJ', ns),
                "ie": self._get_text(emit, 'nfe:IE', ns),
                "endereco": self._extrair_endereco(emit.find('nfe:enderEmit', ns), ns)
            }
        
        # Destinatário
        if dest is not None:
            dados["destinatario"] = {
                "nome": self._get_text(dest, 'nfe:xNome', ns),
                "cnpj_cpf": self._get_text(dest, 'nfe:CNPJ', ns) or self._get_text(dest, 'nfe:CPF', ns),
                "ie": self._get_text(dest, 'nfe:IE', ns),
                "endereco": self._extrair_endereco(dest.find('nfe:enderDest', ns), ns)
            }
        
        # Totais
        if total is not None:
            dados["valores"] = {
                "valor_total": self._get_float(total, 'nfe:vNF', ns),
                "valor_produtos": self._get_float(total, 'nfe:vProd', ns),
                "valor_frete": self._get_float(total, 'nfe:vFrete', ns),
                "valor_desconto": self._get_float(total, 'nfe:vDesc', ns),
            }
            
            dados["impostos"] = {
                "icms": self._get_float(total, 'nfe:vICMS', ns),
                "ipi": self._get_float(total, 'nfe:vIPI', ns),
                "pis": self._get_float(total, 'nfe:vPIS', ns),
                "cofins": self._get_float(total, 'nfe:vCOFINS', ns),
            }
        
        # Itens
        dados["itens"] = self._extrair_itens(root, ns)
        
        return dados
    
    def _extrair_nfe_sem_namespace(self, root) -> Dict[str, Any]:
        """Extrai dados de NFe sem namespace."""
        # Buscar elementos principais
        inf_nfe = root.find('.//infNFe')
        ide = root.find('.//ide')
        emit = root.find('.//emit')
        dest = root.find('.//dest')
        total = root.find('.//total/ICMSTot')
        
        dados = {
            "tipo_documento": "Nota Fiscal Eletrônica (NFe)",
            "chave_acesso": inf_nfe.get('Id', '').replace('NFe', '') if inf_nfe is not None else None,
            "numero_nf": self._get_text_simple(ide, 'nNF'),
            "serie": self._get_text_simple(ide, 'serie'),
            "data_emissao": self._get_text_simple(ide, 'dhEmi') or self._get_text_simple(ide, 'dEmi'),
            "modelo": self._get_text_simple(ide, 'mod'),
            "natureza_operacao": self._get_text_simple(ide, 'natOp'),
        }
        
        # Emitente
        if emit is not None:
            dados["emitente"] = {
                "nome": self._get_text_simple(emit, 'xNome'),
                "nome_fantasia": self._get_text_simple(emit, 'xFant'),
                "cnpj": self._get_text_simple(emit, 'CNPJ'),
                "ie": self._get_text_simple(emit, 'IE'),
                "endereco": self._extrair_endereco_simples(emit.find('enderEmit'))
            }
        
        # Destinatário
        if dest is not None:
            dados["destinatario"] = {
                "nome": self._get_text_simple(dest, 'xNome'),
                "cnpj_cpf": self._get_text_simple(dest, 'CNPJ') or self._get_text_simple(dest, 'CPF'),
                "ie": self._get_text_simple(dest, 'IE'),
                "endereco": self._extrair_endereco_simples(dest.find('enderDest'))
            }
        
        # Totais
        if total is not None:
            dados["valores"] = {
                "valor_total": self._get_float_simple(total, 'vNF'),
                "valor_produtos": self._get_float_simple(total, 'vProd'),
                "valor_frete": self._get_float_simple(total, 'vFrete'),
                "valor_desconto": self._get_float_simple(total, 'vDesc'),
            }
            
            dados["impostos"] = {
                "icms": self._get_float_simple(total, 'vICMS'),
                "ipi": self._get_float_simple(total, 'vIPI'),
                "pis": self._get_float_simple(total, 'vPIS'),
                "cofins": self._get_float_simple(total, 'vCOFINS'),
            }
        
        # Itens
        dados["itens"] = self._extrair_itens_simples(root)
        
        return dados
    
    def _extrair_endereco(self, endereco, ns) -> Optional[Dict[str, str]]:
        """Extrai dados de endereço com namespace."""
        if endereco is None:
            return None
        
        return {
            "logradouro": self._get_text(endereco, 'nfe:xLgr', ns),
            "numero": self._get_text(endereco, 'nfe:nro', ns),
            "complemento": self._get_text(endereco, 'nfe:xCpl', ns),
            "bairro": self._get_text(endereco, 'nfe:xBairro', ns),
            "municipio": self._get_text(endereco, 'nfe:xMun', ns),
            "uf": self._get_text(endereco, 'nfe:UF', ns),
            "cep": self._get_text(endereco, 'nfe:CEP', ns),
        }
    
    def _extrair_endereco_simples(self, endereco) -> Optional[Dict[str, str]]:
        """Extrai dados de endereço sem namespace."""
        if endereco is None:
            return None
        
        return {
            "logradouro": self._get_text_simple(endereco, 'xLgr'),
            "numero": self._get_text_simple(endereco, 'nro'),
            "complemento": self._get_text_simple(endereco, 'xCpl'),
            "bairro": self._get_text_simple(endereco, 'xBairro'),
            "municipio": self._get_text_simple(endereco, 'xMun'),
            "uf": self._get_text_simple(endereco, 'UF'),
            "cep": self._get_text_simple(endereco, 'CEP'),
        }
    
    def _extrair_itens(self, root, ns) -> list:
        """Extrai itens da NFe com namespace."""
        itens = []
        for det in root.findall('.//nfe:det', ns):
            prod = det.find('nfe:prod', ns)
            if prod is not None:
                item = {
                    "numero": det.get('nItem'),
                    "codigo": self._get_text(prod, 'nfe:cProd', ns),
                    "ean": self._get_text(prod, 'nfe:cEAN', ns),
                    "descricao": self._get_text(prod, 'nfe:xProd', ns),
                    "ncm": self._get_text(prod, 'nfe:NCM', ns),
                    "cfop": self._get_text(prod, 'nfe:CFOP', ns),
                    "unidade": self._get_text(prod, 'nfe:uCom', ns),
                    "quantidade": self._get_float(prod, 'nfe:qCom', ns),
                    "valor_unitario": self._get_float(prod, 'nfe:vUnCom', ns),
                    "valor_total": self._get_float(prod, 'nfe:vProd', ns),
                }
                itens.append(item)
        return itens
    
    def _extrair_itens_simples(self, root) -> list:
        """Extrai itens da NFe sem namespace."""
        itens = []
        for det in root.findall('.//det'):
            prod = det.find('prod')
            if prod is not None:
                item = {
                    "numero": det.get('nItem'),
                    "codigo": self._get_text_simple(prod, 'cProd'),
                    "ean": self._get_text_simple(prod, 'cEAN'),
                    "descricao": self._get_text_simple(prod, 'xProd'),
                    "ncm": self._get_text_simple(prod, 'NCM'),
                    "cfop": self._get_text_simple(prod, 'CFOP'),
                    "unidade": self._get_text_simple(prod, 'uCom'),
                    "quantidade": self._get_float_simple(prod, 'qCom'),
                    "valor_unitario": self._get_float_simple(prod, 'vUnCom'),
                    "valor_total": self._get_float_simple(prod, 'vProd'),
                }
                itens.append(item)
        return itens
    
    def _get_text(self, parent, tag, ns) -> Optional[str]:
        """Obtém texto de um elemento com namespace."""
        if parent is None:
            return None
        elem = parent.find(tag, ns)
        return elem.text if elem is not None else None
    
    def _get_text_simple(self, parent, tag) -> Optional[str]:
        """Obtém texto de um elemento sem namespace."""
        if parent is None:
            return None
        elem = parent.find(tag)
        return elem.text if elem is not None else None
    
    def _get_float(self, parent, tag, ns) -> Optional[float]:
        """Obtém valor float de um elemento com namespace."""
        text = self._get_text(parent, tag, ns)
        try:
            return float(text) if text else None
        except (ValueError, TypeError):
            return None
    
    def _get_float_simple(self, parent, tag) -> Optional[float]:
        """Obtém valor float de um elemento sem namespace."""
        text = self._get_text_simple(parent, tag)
        try:
            return float(text) if text else None
        except (ValueError, TypeError):
            return None
    
    def to_json(self, dados: Dict[str, Any]) -> str:
        """Converte dados para JSON formatado."""
        return json.dumps(dados, indent=2, ensure_ascii=False)
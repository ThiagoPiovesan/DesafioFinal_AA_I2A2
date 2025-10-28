# 🧪 Guia de Testes - Sistema de Processamento de Documentos

## 🎯 Funcionalidades Implementadas

### ✅ 1. Processamento de Arquivos

| Tipo | Status | Descrição |
|------|--------|-----------|
| **PDF** | ✅ | Extração com GPT-4 Vision |
| **Imagem** | ✅ | Extração com GPT-4 Vision |
| **XML (NFe)** | ✅ | Parser nativo (gratuito) |
| **CSV/XLSX** | ✅ | Processamento com Pandas |
| **ZIP** | ⚠️ | Estrutura pronta (implementação básica) |

### ✅ 2. Agente com Consulta ao Banco

O agente agora tem **5 ferramentas** para consultar o banco:

1. **listar_documentos** - Lista todos os documentos
2. **buscar_documento_por_id** - Busca por ID específico
3. **buscar_por_tipo** - Filtra por tipo (NFe, Nota Fiscal, etc)
4. **buscar_por_texto** - Busca texto em qualquer campo
5. **calcular_totais** - Soma valores de todas as notas

## 🧪 Cenários de Teste

### Teste 1: Upload e Processamento

#### 1.1 XML de NFe
```
1. Faça upload de um arquivo .xml de NFe
2. Clique em "Processar XML"
3. Verifique os dados extraídos
4. Confirme que foi salvo no banco
```

**Resultado Esperado:**
- ✅ Dados estruturados exibidos
- ✅ Emitente, destinatário, itens extraídos
- ✅ Valores e impostos corretos
- ✅ Salvo no banco instantaneamente

#### 1.2 PDF de Nota Fiscal
```
1. Faça upload de um PDF de nota fiscal
2. Configure a chave OpenAI
3. Clique em "Processar Documento com IA"
4. Aguarde processamento (3-5 segundos)
```

**Resultado Esperado:**
- ✅ Imagem convertida e analisada
- ✅ JSON estruturado retornado
- ✅ Salvo no banco
- ✅ Chat disponível

### Teste 2: Chat com Agente

#### 2.1 Listar Documentos
Na **Tab "Chat com IA"**, pergunte:

```
"Quais documentos eu tenho salvos?"
```

**Resultado Esperado:**
```
Thought: Vou usar a ferramenta listar_documentos
Action: listar_documentos
Observation: [lista de documentos]
Final Answer: Você tem X documentos salvos:
1. documento1.xml - NFe
2. documento2.pdf - Nota Fiscal
...
```

#### 2.2 Buscar Documento Específico
```
"Mostre o documento 1"
ou
"Mostre detalhes do documento com ID 1"
```

**Resultado Esperado:**
- ✅ Agente usa ferramenta `buscar_documento_por_id`
- ✅ Retorna dados completos do documento
- ✅ Formata valores em reais

#### 2.3 Calcular Totais
```
"Qual o valor total de todas as notas?"
```

**Resultado Esperado:**
- ✅ Agente usa `calcular_totais`
- ✅ Retorna soma de todos os valores
- ✅ Mostra quantidade de documentos

#### 2.4 Buscar por Tipo
```
"Liste todas as NFes"
ou
"Mostre as notas fiscais eletrônicas"
```

**Resultado Esperado:**
- ✅ Filtra apenas documentos do tipo NFe
- ✅ Lista com IDs e datas

#### 2.5 Buscar por Texto
```
"Encontre documentos da empresa ABC"
ou
"Busque pelo CNPJ 12.345.678/0001-90"
```

**Resultado Esperado:**
- ✅ Busca em todos os campos
- ✅ Retorna documentos relevantes

### Teste 3: Conversação Contextual

Teste uma conversa completa:

```
Usuário: "Quais documentos eu tenho?"
Agente: [lista documentos]

Usuário: "Mostre o documento 1"
Agente: [detalhes do documento 1]

Usuário: "Qual o valor dessa nota?"
Agente: [extrai valor do documento 1]

Usuário: "Qual o total de todas as notas?"
Agente: [calcula e retorna total]
```

**Resultado Esperado:**
- ✅ Memória mantém contexto
- ✅ Agente referencia documentos anteriores
- ✅ Respostas coerentes

## 🐛 Problemas Comuns e Soluções

### Problema: "No module named 'utils.database_tool'"
**Solução:** Certifique-se de que o arquivo `database_tool.py` está em `utils/`

### Problema: "Unable to get page count" (PDF)
**Solução:** 
```bash
pip install PyMuPDF
```

### Problema: Agente não usa ferramentas
**Solução:** 
- Verifique se o banco tem documentos
- Reformule a pergunta de forma mais direta
- Exemplo: "liste documentos" ao invés de "o que tem no banco?"

### Problema: Erro ao calcular totais
**Solução:** 
- Verifique se os documentos têm campo `valor_total` no JSON
- XML de NFe deve ter valores em `$.valores.valor_total`

## 📊 Estrutura do Banco de Dados

Após salvar documentos, a tabela `documentos` terá:

```sql
CREATE TABLE documentos (
    id INTEGER PRIMARY KEY,
    nome_arquivo TEXT,
    tipo_documento TEXT,
    conteudo_extraido TEXT,  -- JSON com dados estruturados
    data_criacao TIMESTAMP,
    -- Outros campos dinâmicos...
);
```

## 💡 Dicas para Melhores Resultados

### Para PDF/Imagens:
- ✅ Use imagens com boa resolução (300 DPI)
- ✅ Evite imagens muito escuras ou borradas
- ✅ PDFs digitais funcionam melhor que escaneados

### Para XML:
- ✅ Certifique-se de que é um XML válido de NFe
- ✅ Funciona com e sem namespace
- ✅ Processamento é instantâneo e gratuito

### Para Chat com Agente:
- ✅ Seja específico nas perguntas
- ✅ Use IDs quando souber
- ✅ Pergunte uma coisa por vez
- ✅ Aguarde o agente terminar o raciocínio

## 🚀 Próximos Passos Sugeridos

1. **Busca Semântica** - Usar embeddings para buscar documentos similares
2. **Análise de Tendências** - Gráficos de valores ao longo do tempo
3. **Exportação** - Gerar relatórios em Excel/PDF
4. **Validações** - Verificar inconsistências nas notas
5. **Integração API SEFAZ** - Validar chaves de acesso online

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs no console (terminal onde rodou `streamlit run`)
2. O agente mostra seu raciocínio com `verbose=True`
3. Teste ferramentas individualmente primeiro
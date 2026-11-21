# 🔌 MCP: minhas anotações de estudo

Anotações pessoais, em português, sobre o **Model Context Protocol (MCP)**, feitas enquanto eu estudava o curso [MCP: Build Rich-Context AI Apps with Anthropic](https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/) (DeepLearning.AI).

Cada nota tem **fluxograma** e **exemplo**, e separa o que é **obrigatório** pelo protocolo do que é só **convenção** ou **específico do exemplo**.

> ⚠️ Este repositório **não** reproduz o material do curso. São resumos com as minhas palavras, diagramas próprios e código reescrito/corrigido. Para o conteúdo completo, faça o curso oficial.

## 🗺️ Visão geral

```mermaid
flowchart LR
    H["Host<br/>(app de IA)"] --> C1["Cliente MCP"] --> S1["Servidor MCP<br/>(tools, resources, prompts)"]
    H --> C2["Cliente MCP"] --> S2["Outro servidor"]
    S1 --> D1[(APIs, arquivos,<br/>bancos de dados)]
```

O MCP padroniza como aplicações de IA se conectam a ferramentas e dados: você escreve um servidor uma vez e ele funciona em qualquer host compatível (Claude Desktop, IDEs, seu próprio chatbot).

## 📚 Notas

| # | Nota | O que cobre |
|---|---|---|
| 01 | [Fundamentos](notas/01-fundamentos.md) | Host, cliente, servidor, primitivas, JSON-RPC, ciclo de vida |
| 02 | [Transportes](notas/02-transportes.md) | stdio, Streamable HTTP, JSON × SSE, o SSE antigo |
| 03 | [Tool use (antes do MCP)](notas/03-tool-use.md) | O loop do agente e as 3 regras da API |
| 04 | [Criando um servidor](notas/04-servidor.md) | FastMCP, schema automático, MCP Inspector |
| 05 | [Criando um cliente](notas/05-cliente.md) | `stdio_client`, `ClientSession`, conversão de schema |
| 06 | [Vários servidores](notas/06-varios-servidores.md) | `server_config.json`, `tool_to_session`, `AsyncExitStack` |
| 07 | [Resources e prompts](notas/07-resources-e-prompts.md) | Quem aciona cada primitiva |
| 08 | [Claude Desktop](notas/08-claude-desktop.md) | Configuração e problemas comuns |
| 09 | [Servidores remotos e deploy](notas/09-servidores-remotos.md) | Streamable HTTP, Docker, produção |
| 10 | [Além do básico](notas/10-alem-do-basico.md) | OAuth, roots, sampling, registry, spec 2026-07-28 |

Extras:
- 🐛 [Pegadinhas que encontrei](notas/pegadinhas.md)
- 🔄 [SDK Python v1 × v2](notas/sdk-v1-vs-v2.md)

## 💻 Código

Versões revisadas do servidor e do chatbot, com as correções descritas nas notas.

| Arquivo | O que é |
|---|---|
| [`codigo/research_server.py`](codigo/research_server.py) | Servidor MCP com 2 tools, 2 resources e 1 prompt (stdio ou HTTP) |
| [`codigo/mcp_chatbot.py`](codigo/mcp_chatbot.py) | Chatbot que se conecta a vários servidores (stdio e HTTP) |
| [`codigo/server_config.json`](codigo/server_config.json) | Configuração dos servidores |

### Como rodar

```bash
cd codigo
uv init --bare
uv add "mcp>=1.10,<2" arxiv anthropic python-dotenv
cp .env.example .env        # coloque sua ANTHROPIC_API_KEY

# testar o servidor sozinho
npx @modelcontextprotocol/inspector uv run research_server.py

# rodar o chatbot (conecta nos servidores do server_config.json)
uv run mcp_chatbot.py
```

No chatbot:

| Comando | O que faz |
|---|---|
| texto normal | Pergunta ao Claude, que usa as tools quando precisar |
| `@folders` | Lista os temas salvos (resource) |
| `@ai_interpretability resuma os artigos` | Lê o resource e envia como contexto da pergunta |
| `/prompts` | Lista os prompts disponíveis |
| `/prompt generate_search_prompt topic=history num_papers=2` | Executa um prompt |

Para rodar o servidor como **remoto** (Streamable HTTP em `http://localhost:8000/mcp`):

```bash
MCP_TRANSPORT=http uv run research_server.py
```

> O código usa o **SDK v1** (`mcp<2`), o mesmo do curso. Veja [SDK v1 × v2](notas/sdk-v1-vs-v2.md) para migrar. O `fetch` e o `filesystem` do `server_config.json` precisam de `uvx` e `npx` (Node.js) instalados.

## 🔗 Referências

- [Curso: MCP: Build Rich-Context AI Apps with Anthropic](https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/)
- [Curso: Model Context Protocol: Advanced Topics (Anthropic Academy)](https://anthropic.skilljar.com/model-context-protocol-advanced-topics)
- [Documentação oficial do MCP](https://modelcontextprotocol.io)
- [SDK Python](https://github.com/modelcontextprotocol/python-sdk) · [Guia de migração v1 → v2](https://py.sdk.modelcontextprotocol.io/migration/)
- [Servidores de referência](https://github.com/modelcontextprotocol/servers)
- [MCP Registry](https://registry.modelcontextprotocol.io)

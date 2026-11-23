# MCP: anotações de estudo

Anotações pessoais em português sobre o Model Context Protocol, feitas a partir dos cursos da DeepLearning.AI e da Anthropic Academy, com código de exemplo reescrito e testado.

## Arquitetura
```
notas/*.md  (teoria: fluxograma + exemplo + obrigatório/convenção)

codigo/
  mcp_chatbot.py ──stdio──> research_server.py (FastMCP)
     │  Anthropic Messages API           ├── tools:     search_papers(topic, max_results), extract_info(paper_id)
     │  (ANTHROPIC_MODEL, .env)          ├── resources: papers://folders, papers://{topic}
     └── chat_loop: @recurso, /prompt    └── prompt:    generate_search_prompt(topic, num_papers)
                                         └── dados: JSON por tópico (arXiv)
```
- `codigo/research_server.py`: servidor MCP com o SDK v1 (`FastMCP`). Há um comentário sobre o equivalente no SDK v2 (`notas/sdk-v1-vs-v2.md`).
- `codigo/mcp_chatbot.py`: cliente MCP com vários servidores, loop de tool use com o Claude e leitura de resources e prompts.
- `codigo/tests/`: `test_server_funcoes` (lógica), `test_server_protocolo` (MCP em memória), `test_stdio` (processo real), `test_chatbot` (Anthropic mockado, sem rede). Fixtures em `conftest.py`.
- Notas de 01 a 11: fundamentos, transportes, tool use, servidor, cliente, vários servidores, resources e prompts, Claude Desktop, servidores remotos, além do básico, testes. Mais `pegadinhas.md` e `sdk-v1-vs-v2.md`.

## Comandos (PowerShell)
```powershell
cd codigo        # o pyproject.toml fica aqui, não na raiz
uv sync
uv run pytest -v
uvx ruff check .
uv run mcp_chatbot.py            # precisa de ANTHROPIC_API_KEY no .env (não versionado)
```

## CI e deploy
- `.github/workflows/testes.yml`:
  - bloqueia `.env` versionado e roda **gitleaks** (vazamento de chaves);
  - roda ruff;
  - roda pytest em matriz de versões Python com `uv`, `working-directory: codigo`.
- `dependabot.yml` atualiza as dependências.
- Não há deploy: é repositório de estudo.

## Regras
- Toda nota tem **fluxograma** (mermaid) e **exemplo**, e separa **obrigatório pelo protocolo**, **convenção** e **específico do exemplo**.
- **Não reproduza o material dos cursos.** Use resumo com as palavras da Flora, diagramas próprios e código reescrito.
- Nova nota entra na tabela do `README.md`, com numeração sequencial.
- Testes do chatbot **nunca** chamam a API real: use mocks.
- Antes de afirmar algo da especificação MCP ou do SDK, consulte a doc atual (context7 ou o site oficial). O SDK muda rápido entre v1 e v2.
- Agente: `ia-engineer`. Para explicar temas novos, use `/estudo`.

# 🐛 Pegadinhas que encontrei

| # | Onde | Problema | Correção |
|---|---|---|---|
| 1 | Servidor stdio | `print()` vai para o stdout, que é o canal do protocolo | `print(..., file=sys.stderr)` ou `logging` |
| 2 | Servidor | `PAPER_DIR = "papers"` depende da pasta de onde o processo foi iniciado | Caminho absoluto a partir de `__file__`, ou `uv --directory` |
| 3 | Servidor | `os.listdir(PAPER_DIR)` quebra se a pasta ainda não existe | Checar `os.path.isdir` antes |
| 4 | Loop do chatbot | Um `append` por `tool_use`, com os `tool_result` em mensagens separadas | Todos os resultados numa única mensagem `user` |
| 5 | Loop do chatbot | Só para quando `len(response.content) == 1`; com 2 blocos de texto, entra em loop infinito | Parar quando não houver `tool_use` |
| 6 | Chatbot | `messages` recriada a cada pergunta: não há memória | Manter `messages` fora da função, se quiser memória |
| 7 | Vários servidores | Tools com o mesmo nome se sobrescrevem e a API rejeita | Prefixo por servidor |
| 8 | Vários servidores | `filesystem` com `"."` enxerga o `.env` | Dar só uma subpasta |
| 9 | Vários servidores | `uvx` ignora o pin de versão do seu projeto | `uvx --with "mcp<2" mcp-server-fetch` |
| 10 | Resources | Conteúdo só impresso: o LLM não vê | Anexar ao contexto |
| 11 | Cliente HTTP | `streamablehttp_client` devolve **3** valores | `read, write, _ = ...` |
| 12 | URL remota | `/mcp/` com barra pode gerar redirecionamento | Usar `/mcp` |
| 13 | Deploy | FastMCP escuta em `127.0.0.1` por padrão | `host="0.0.0.0"` e porta do `PORT` |
| 14 | Claude Desktop | `spawn uv ENOENT` | Caminho completo do executável |
| 15 | SDK | Código do curso quebra com `pip install mcp` (instala a v2) | Fixar `mcp>=1.2,<2` ou migrar |

## O loop corrigido

```python
async def process_query(self, query):
    messages = [{"role": "user", "content": query}]
    while True:
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            tools=self.available_tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "text":
                print(block.text)
            elif block.type == "tool_use":
                session = self.tool_to_session[block.name]
                result = await session.call_tool(block.name, arguments=block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": [{"type": "text", "text": c.text}
                                for c in result.content if c.type == "text"],
                    "is_error": result.isError,
                })

        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})
```

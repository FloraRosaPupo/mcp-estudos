# 03 · Tool use (antes do MCP)

> **Nesta nota:** como um LLM usa ferramentas pela API do Claude, o "loop do agente", as 3 regras que a API exige e o que muda quando as tools passam a vir de um servidor MCP.

Antes do MCP, vale entender o **tool use** puro. O MCP não substitui o tool use: ele só muda **de onde as tools vêm** e **quem as executa**. O loop continua igual.

## 1. As peças

Para o Claude usar uma ferramenta, você envia, junto com a pergunta, uma lista de tools no formato:

```python
tools = [{
    "name": "search_papers",
    "description": "Search for papers on arXiv based on a topic and store their information.",
    "input_schema": {                         # JSON Schema dos argumentos
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "The topic to search for"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["topic"],
    },
}]
```

O Claude **não executa nada**. Quando acha que precisa de uma tool, ele responde com um bloco `tool_use` dizendo qual tool e com quais argumentos. Quem executa é o **seu código**, que depois devolve o resultado num bloco `tool_result`.

```json
// Resposta do Claude
{"stop_reason": "tool_use",
 "content": [
   {"type": "text", "text": "Vou buscar os artigos."},
   {"type": "tool_use", "id": "toolu_01A", "name": "search_papers",
    "input": {"topic": "LLM interpretability", "max_results": 2}}]}

// O que seu código devolve
{"role": "user",
 "content": [{"type": "tool_result", "tool_use_id": "toolu_01A",
              "content": "2401.12345v1, 2402.67890v2"}]}
```

## 2. O loop do agente

```mermaid
flowchart TD
    A[Usuário pergunta] --> B["messages = [pergunta]"]
    B --> C["client.messages.create(tools=..., messages=...)"]
    C --> D{"A resposta tem tool_use?"}
    D -- não --> E[Mostra o texto e termina]
    D -- sim --> F[Executa cada tool pedida]
    F --> G["messages += assistant (resposta inteira)<br/>messages += user (todos os tool_result)"]
    G --> C
```

O loop continua até o Claude responder **só com texto**. A cada volta, a lista `messages` cresce, e é assim que o Claude "lembra" o que já fez dentro da mesma pergunta.

### Exemplo, volta a volta

Pergunta: *"Busque 2 artigos sobre LLM interpretability e me diga o título do primeiro."*

| Volta | O Claude responde | Seu código faz | `messages` depois |
|---|---|---|---|
| 1 | `tool_use search_papers(topic, 2)` | Executa, recebe 2 IDs | user, assistant, user |
| 2 | `tool_use extract_info("2401.12345v1")` | Executa, recebe o JSON do artigo | + assistant, user |
| 3 | Texto: "O primeiro se chama…" | Mostra e sai do loop | + assistant |

## 3. As 3 regras obrigatórias

Quebrar qualquer uma faz a API devolver erro:

```python
# Regra 1: devolver a resposta do Claude INTEIRA ao histórico (texto + todos os tool_use)
messages.append({"role": "assistant", "content": response.content})

# Regra 2: cada tool_result aponta para o tool_use correspondente pelo id
{"type": "tool_result", "tool_use_id": block.id, "content": resultado}

# Regra 3: todos os tool_results da rodada vão juntos, numa ÚNICA mensagem "user"
messages.append({"role": "user", "content": tool_results})
```

Exemplo de quebra da regra 3: o Claude pede duas tools na mesma resposta (*"busque artigos sobre IA e sobre física"*), e o código manda os dois resultados em mensagens separadas. A API recusa, dizendo que faltou o `tool_result` de um dos `tool_use`.

## 4. O loop correto, completo

```python
def process_query(query):
    messages = [{"role": "user", "content": query}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2048,
            tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})   # regra 1

        tool_results = []
        for block in response.content:
            if block.type == "text":
                print(block.text)
            elif block.type == "tool_use":
                resultado = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,                                    # regra 2
                    "content": resultado,
                })

        if not tool_results:            # só texto: terminou
            break
        messages.append({"role": "user", "content": tool_results})            # regra 3
```

Uma alternativa equivalente para saber se terminou é checar `response.stop_reason == "tool_use"`.

## 5. Erros de tool

Se a tool falhar (API fora do ar, ID inexistente), **não interrompa o loop**: devolva o erro como resultado, com `is_error`, para o Claude decidir o que fazer (tentar de novo, avisar o usuário, usar outra tool):

```python
{"type": "tool_result", "tool_use_id": block.id,
 "content": "arXiv indisponível no momento", "is_error": True}
```

## 6. Obrigatório × convenção

| Parte | Nível |
|---|---|
| Schema da tool (`name`, `description`, `input_schema`) | Formato obrigatório; o conteúdo é seu |
| As 3 regras acima | Obrigatório |
| Dicionário `nome → função` para executar | Convenção (no MCP vira `session.call_tool`) |
| `stop_reason == "tool_use"` × checar os blocos | Equivalentes |
| `max_tokens` | Obrigatório; o valor é livre |

## 7. Memória entre perguntas

No exemplo acima, `messages` é recriada a cada pergunta, então o chatbot **não lembra** da pergunta anterior. Se o usuário pedir "resuma o primeiro artigo" depois de "busque 2 artigos", o Claude não sabe qual é "o primeiro". Para ter memória, mantenha `messages` fora da função (e cuide do tamanho do contexto).

## 8. O que muda com MCP

| Sem MCP | Com MCP |
|---|---|
| Funções no mesmo arquivo do chatbot | Funções num servidor separado |
| Schema escrito à mão | Gerado automaticamente (type hints + docstring) |
| Lista de tools fixa no código | Descoberta com `list_tools()` |
| `execute_tool(nome, args)` | `session.call_tool(nome, arguments=args)` |
| Só este chatbot usa as tools | Qualquer host compatível usa o mesmo servidor |

O loop em si **não muda**.

## Para fixar

1. O Claude executa as tools?
2. O Claude pediu 3 tools numa resposta. Quantas mensagens `user` com `tool_result` você deve enviar?
3. Por que devolver o erro de uma tool ao Claude em vez de lançar uma exceção?

<details><summary>Respostas</summary>

1. Não. Ele só pede (bloco `tool_use`); quem executa é o seu código.
2. Uma, com os 3 `tool_result` dentro.
3. Para o Claude poder reagir: tentar de novo, mudar de abordagem ou explicar ao usuário o que aconteceu.

</details>

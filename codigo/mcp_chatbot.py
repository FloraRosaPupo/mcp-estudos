"""
Chatbot MCP que se conecta a vários servidores (stdio e Streamable HTTP).

Comandos:
  texto normal            → pergunta ao Claude, que usa as tools quando precisar
  @<uri> [pergunta]       → lê um resource (ex.: @papers://folders). Atalho: @ai_interpretability
                            equivale a @papers://ai_interpretability. Com pergunta, o conteúdo
                            vai como contexto para o Claude.
  /prompts                → lista os prompts disponíveis
  /prompt <nome> k=v ...  → busca o prompt no servidor e envia ao Claude
  quit                    → sai

Configuração dos servidores: server_config.json
Requer: uv add "mcp>=1.10,<2" anthropic python-dotenv
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_config.json")


class MCPChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.available_tools: list[dict] = []          # vai para o Claude
        self.tool_to_session: dict[str, ClientSession] = {}
        self.resource_to_session: dict[str, ClientSession] = {}
        self.template_schemes: list[tuple[str, ClientSession]] = []  # ("papers", sessão)
        self.prompts: dict[str, dict] = {}             # nome → {session, description, args}

    # ─────────────────────── Conexão ───────────────────────

    async def connect_to_server(self, name: str, config: dict) -> None:
        try:
            if "url" in config:  # servidor remoto
                read, write, _ = await self.exit_stack.enter_async_context(
                    streamablehttp_client(config["url"], headers=config.get("headers")))
            else:                # servidor local
                read, write = await self.exit_stack.enter_async_context(
                    stdio_client(StdioServerParameters(**config)))

            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = (await session.list_tools()).tools
            for tool in tools:
                if tool.name in self.tool_to_session:
                    print(f"  [aviso] Tool repetida ignorada: {tool.name} ({name})")
                    continue
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,   # MCP (camelCase) → API do Claude
                })

            # Resources e prompts são opcionais: nem todo servidor oferece
            try:
                for r in (await session.list_resources()).resources:
                    self.resource_to_session[str(r.uri)] = session
                for t in (await session.list_resource_templates()).resourceTemplates:
                    scheme = t.uriTemplate.split("://")[0]
                    self.template_schemes.append((scheme, session))
            except Exception:
                pass
            try:
                for p in (await session.list_prompts()).prompts:
                    self.prompts[p.name] = {
                        "session": session,
                        "description": p.description or "",
                        "args": [a.name for a in (p.arguments or [])],
                    }
            except Exception:
                pass

            print(f"[ok] {name}: {[t.name for t in tools]}")
        except Exception as e:
            print(f"[erro] Falha ao conectar em {name}: {e}")

    async def connect_to_servers(self) -> None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            servers = json.load(f).get("mcpServers", {})
        for name, config in servers.items():
            await self.connect_to_server(name, config)

    # ──────────────────────── Claude ────────────────────────

    async def process_query(self, query: str) -> None:
        messages = [{"role": "user", "content": query}]
        while True:
            response = self.anthropic.messages.create(
                model=MODEL, max_tokens=2048,
                tools=self.available_tools, messages=messages)

            # Regra 1: a resposta inteira volta ao histórico
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "text":
                    print(block.text)
                elif block.type == "tool_use":
                    print(f"-> {block.name}({block.input})")
                    session = self.tool_to_session[block.name]
                    result = await session.call_tool(block.name, arguments=block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,                      # Regra 2
                        "content": [{"type": "text", "text": c.text}
                                    for c in result.content if c.type == "text"],
                        "is_error": result.isError,
                    })

            if not tool_results:   # só texto: terminou
                break
            # Regra 3: todos os resultados numa única mensagem "user"
            messages.append({"role": "user", "content": tool_results})

    # ─────────────────── Resources e prompts ───────────────────

    async def read_resource(self, uri: str) -> str | None:
        if "://" not in uri:
            uri = f"papers://{uri}"
        session = self.resource_to_session.get(uri)
        if session is None:
            scheme = uri.split("://")[0]
            session = next((s for sc, s in self.template_schemes if sc == scheme), None)
        if session is None:
            print(f"Resource não encontrado: {uri}")
            return None
        result = await session.read_resource(uri)
        return "\n".join(c.text for c in result.contents if hasattr(c, "text"))

    def list_prompts(self) -> None:
        if not self.prompts:
            print("Nenhum prompt disponível.")
        for name, p in self.prompts.items():
            print(f"- {name}({', '.join(p['args'])}): {p['description']}")

    async def run_prompt(self, name: str, args: dict[str, str]) -> None:
        prompt = self.prompts.get(name)
        if prompt is None:
            print(f"Prompt não encontrado: {name}. Use /prompts.")
            return
        result = await prompt["session"].get_prompt(name, arguments=args)
        text = "\n".join(
            m.content.text for m in result.messages if getattr(m.content, "type", "") == "text")
        await self.process_query(text)

    # ───────────────────────── Loop ─────────────────────────

    async def chat_loop(self) -> None:
        print("\nChatbot MCP iniciado! Digite 'quit' para sair.")
        while True:
            query = input("\nVocê: ").strip()
            if not query:
                continue
            if query.lower() == "quit":
                break
            try:
                if query.startswith("@"):
                    uri, _, question = query[1:].partition(" ")
                    content = await self.read_resource(uri)
                    if content is None:
                        continue
                    if question:   # usa o resource como contexto
                        await self.process_query(f"{content}\n\n---\n\n{question}")
                    else:
                        print(content)
                elif query == "/prompts":
                    self.list_prompts()
                elif query.startswith("/prompt "):
                    name, *pairs = query.split()[1:]
                    args = dict(p.split("=", 1) for p in pairs if "=" in p)
                    await self.run_prompt(name, args)
                else:
                    await self.process_query(query)
            except Exception as e:
                print(f"Erro: {e}")

    async def cleanup(self) -> None:
        await self.exit_stack.aclose()


async def main() -> None:
    bot = MCPChatBot()
    try:
        await bot.connect_to_servers()
        await bot.chat_loop()
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

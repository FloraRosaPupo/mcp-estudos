"""
Teste de integração: inicia o servidor de verdade como subprocesso e conversa via stdio,
exatamente como o Claude Desktop ou o chatbot fazem.

Se alguém colocar um print() no stdout do servidor, este é o teste que pega.
"""

import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.anyio

SERVIDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "research_server.py")


async def test_servidor_responde_via_stdio():
    params = StdioServerParameters(command=sys.executable, args=[SERVIDOR])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as sessao:
            init = await sessao.initialize()
            tools = [t.name for t in (await sessao.list_tools()).tools]
            prompt = await sessao.get_prompt("generate_search_prompt", {"topic": "llm"})

    assert init.serverInfo.name == "research"
    assert sorted(tools) == ["extract_info", "search_papers"]
    assert "'llm'" in prompt.messages[0].content.text

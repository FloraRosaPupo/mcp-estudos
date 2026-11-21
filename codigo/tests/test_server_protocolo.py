"""
Testes de protocolo: um cliente MCP de verdade conversa com o servidor em memória.

É o mesmo caminho que o Inspector, o Claude Desktop ou o chatbot usam
(tools/list, tools/call, resources/read, prompts/get...), só que sem subprocesso.
"""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

import research_server as rs

pytestmark = pytest.mark.anyio


async def test_tools_list_gera_schema_a_partir_da_funcao():
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        tools = {t.name: t for t in (await cliente.list_tools()).tools}

    assert set(tools) == {"search_papers", "extract_info"}

    schema = tools["search_papers"].inputSchema
    assert schema["properties"]["topic"]["type"] == "string"
    assert schema["properties"]["max_results"]["type"] == "integer"
    assert schema["properties"]["max_results"]["default"] == 5
    assert schema["required"] == ["topic"]          # tem valor padrão → opcional

    # A docstring vira a descrição que o LLM lê
    assert tools["search_papers"].description.strip().startswith("Search for papers on arXiv")


async def test_tools_call_search_papers(papers_dir, fake_arxiv):
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        resultado = await cliente.call_tool(
            "search_papers", {"topic": "LLM", "max_results": 2})

    assert resultado.isError is False
    textos = [c.text for c in resultado.content if c.type == "text"]
    assert "2601.00001v1" in " ".join(textos)
    assert "2601.00002v1" in " ".join(textos)


async def test_tools_call_extract_info(papers_salvos):
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        resultado = await cliente.call_tool("extract_info", {"paper_id": papers_salvos[0]})

    info = json.loads(resultado.content[0].text)
    assert info["authors"] == ["Ana Silva", "Bruno Lima"]


async def test_tools_call_com_argumento_faltando_devolve_erro():
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        resultado = await cliente.call_tool("search_papers", {})   # falta "topic"

    assert resultado.isError is True


async def test_resources_estatico_e_template():
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        estaticos = [str(r.uri) for r in (await cliente.list_resources()).resources]
        templates = [t.uriTemplate for t in (await cliente.list_resource_templates()).resourceTemplates]

    assert estaticos == ["papers://folders"]          # URI fixa → resources/list
    assert templates == ["papers://{topic}"]          # URI com {} → resources/templates/list


async def test_resources_read(papers_salvos):
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        pastas = await cliente.read_resource("papers://folders")
        tema = await cliente.read_resource("papers://llm_interpretability")

    assert "- llm_interpretability" in pastas.contents[0].text
    assert "Total: 2" in tema.contents[0].text


async def test_prompts_list_e_get():
    async with create_connected_server_and_client_session(rs.mcp) as cliente:
        prompts = (await cliente.list_prompts()).prompts
        # Argumentos de prompt sempre trafegam como texto
        resultado = await cliente.get_prompt(
            "generate_search_prompt", {"topic": "history", "num_papers": "2"})

    assert [p.name for p in prompts] == ["generate_search_prompt"]
    assert [a.name for a in prompts[0].arguments] == ["topic", "num_papers"]
    assert "find 2 papers about 'history'" in resultado.messages[0].content.text

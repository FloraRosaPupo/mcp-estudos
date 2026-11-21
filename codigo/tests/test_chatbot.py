"""
Testes do chatbot (host + cliente MCP).

O Claude é simulado com respostas prontas, então os testes verificam a lógica do loop
sem gastar tokens nem precisar de chave de API. As sessões MCP também são simuladas,
para isolar o chatbot do servidor.
"""

import sys
from types import SimpleNamespace as NS

import pytest

from mcp_chatbot import MCPChatBot
from test_stdio import SERVIDOR

pytestmark = pytest.mark.anyio


# ───────────────────── dublês (fakes) ─────────────────────

def texto(t):
    return NS(type="text", text=t)


def tool_use(id_, nome, args):
    return NS(type="tool_use", id=id_, name=nome, input=args)


class FakeClaude:
    """Devolve as respostas da lista, em ordem, e guarda uma cópia de cada chamada."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        return NS(content=self.respostas.pop(0))


class FakeSessao:
    """Imita uma ClientSession: registra as chamadas e devolve um resultado fixo."""

    def __init__(self, resposta="ok", erro=False):
        self.resposta, self.erro, self.chamadas = resposta, erro, []

    async def call_tool(self, nome, arguments):
        self.chamadas.append((nome, arguments))
        return NS(content=[texto(f"{self.resposta}:{arguments}")], isError=self.erro)

    async def read_resource(self, uri):
        return NS(contents=[NS(text=f"conteúdo de {uri}")])

    async def get_prompt(self, nome, arguments):
        return NS(messages=[NS(content=texto(f"prompt {nome} {arguments}"))])


@pytest.fixture
def bot():
    b = MCPChatBot()
    b.available_tools = [{"name": "search_papers", "description": "", "input_schema": {}}]
    return b


# ───────────────────── loop do process_query ─────────────────────

async def test_resposta_so_texto_chama_o_claude_uma_vez(bot, capsys):
    bot.anthropic = FakeClaude([texto("Olá!")])
    await bot.process_query("oi")

    assert len(bot.anthropic.chamadas) == 1
    assert "Olá!" in capsys.readouterr().out


async def test_envia_as_tools_para_o_claude(bot):
    bot.anthropic = FakeClaude([texto("ok")])
    await bot.process_query("oi")
    assert bot.anthropic.chamadas[0]["tools"] == bot.available_tools


async def test_executa_tool_e_devolve_resultado(bot):
    sessao = FakeSessao("ids")
    bot.tool_to_session = {"search_papers": sessao}
    bot.anthropic = FakeClaude(
        [tool_use("t1", "search_papers", {"topic": "llm"})],
        [texto("Encontrei 2 artigos.")],
    )
    await bot.process_query("busque artigos")

    assert sessao.chamadas == [("search_papers", {"topic": "llm"})]
    segunda = bot.anthropic.chamadas[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    resultado = segunda[2]["content"][0]
    assert resultado["type"] == "tool_result"
    assert resultado["tool_use_id"] == "t1"                  # regra 2: mesmo id
    assert resultado["content"] == [{"type": "text", "text": "ids:{'topic': 'llm'}"}]


async def test_tools_em_paralelo_vao_numa_unica_mensagem(bot):
    """Regra 3: todos os tool_result da rodada vão juntos numa mensagem 'user'."""
    bot.tool_to_session = {"search_papers": FakeSessao()}
    bot.anthropic = FakeClaude(
        [texto("Vou buscar os dois."),
         tool_use("t1", "search_papers", {"topic": "ia"}),
         tool_use("t2", "search_papers", {"topic": "física"})],
        [texto("Pronto.")],
    )
    await bot.process_query("busque ia e física")

    segunda = bot.anthropic.chamadas[1]["messages"]
    assert len(segunda) == 3
    assert [r["tool_use_id"] for r in segunda[2]["content"]] == ["t1", "t2"]
    # regra 1: a resposta inteira (texto + 2 tool_use) volta ao histórico
    assert len(segunda[1]["content"]) == 3


async def test_varios_blocos_de_texto_nao_causam_loop_infinito(bot):
    bot.anthropic = FakeClaude([texto("Parte 1."), texto("Parte 2.")])
    await bot.process_query("oi")
    assert len(bot.anthropic.chamadas) == 1


async def test_encadeia_varias_rodadas_de_tools(bot):
    bot.tool_to_session = {"search_papers": FakeSessao(), "extract_info": FakeSessao()}
    bot.anthropic = FakeClaude(
        [tool_use("t1", "search_papers", {"topic": "llm"})],
        [tool_use("t2", "extract_info", {"paper_id": "2601.00001v1"})],
        [texto("O título é ...")],
    )
    await bot.process_query("título do primeiro artigo")
    assert len(bot.anthropic.chamadas) == 3


async def test_erro_da_tool_e_repassado_ao_claude(bot):
    bot.tool_to_session = {"search_papers": FakeSessao(erro=True)}
    bot.anthropic = FakeClaude(
        [tool_use("t1", "search_papers", {})],
        [texto("Deu erro, vou tentar de novo depois.")],
    )
    await bot.process_query("busque")
    resultado = bot.anthropic.chamadas[1]["messages"][2]["content"][0]
    assert resultado["is_error"] is True


async def test_tool_e_roteada_para_a_sessao_certa(bot):
    research, fetch = FakeSessao("research"), FakeSessao("fetch")
    bot.tool_to_session = {"search_papers": research, "fetch": fetch}
    bot.anthropic = FakeClaude(
        [tool_use("t1", "fetch", {"url": "https://deeplearning.ai"})],
        [texto("ok")],
    )
    await bot.process_query("leia o site")
    assert fetch.chamadas and not research.chamadas


# ───────────────────── resources e prompts ─────────────────────

async def test_atalho_de_resource_vira_uri_papers(bot):
    bot.template_schemes = [("papers", FakeSessao())]
    assert await bot.read_resource("llm") == "conteúdo de papers://llm"


async def test_resource_estatico_tem_prioridade(bot):
    bot.resource_to_session = {"papers://folders": FakeSessao()}
    assert await bot.read_resource("folders") == "conteúdo de papers://folders"


async def test_resource_desconhecido_devolve_none(bot, capsys):
    assert await bot.read_resource("outro://x") is None
    assert "não encontrado" in capsys.readouterr().out


async def test_prompt_vira_pergunta_para_o_claude(bot):
    bot.prompts = {"generate_search_prompt": {
        "session": FakeSessao(), "description": "", "args": ["topic"]}}
    bot.anthropic = FakeClaude([texto("ok")])
    await bot.run_prompt("generate_search_prompt", {"topic": "history"})

    enviada = bot.anthropic.chamadas[0]["messages"][0]["content"]
    assert enviada == "prompt generate_search_prompt {'topic': 'history'}"


# ───────────────────── conexão real (stdio) ─────────────────────

async def test_conecta_no_servidor_real_e_ignora_tools_repetidas(capsys):
    bot = MCPChatBot()
    config = {"command": sys.executable, "args": [SERVIDOR]}
    try:
        await bot.connect_to_server("research", config)
        await bot.connect_to_server("research-copia", config)
    finally:
        await bot.cleanup()

    nomes = [t["name"] for t in bot.available_tools]
    assert sorted(nomes) == ["extract_info", "search_papers"]     # sem duplicatas
    assert all("input_schema" in t for t in bot.available_tools)  # formato da API do Claude
    assert "papers://folders" in bot.resource_to_session
    assert "generate_search_prompt" in bot.prompts
    assert "Tool repetida ignorada" in capsys.readouterr().out

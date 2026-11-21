"""
Configuração compartilhada dos testes.

- Coloca a pasta `codigo/` no sys.path para importar o servidor e o chatbot.
- Usa uma pasta temporária para os artigos (nada é gravado no projeto).
- Simula o arXiv: os testes não dependem de internet.
"""

import datetime
import os
import sys
from types import SimpleNamespace

import pytest

CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODIGO)
os.environ.setdefault("ANTHROPIC_API_KEY", "chave-falsa-para-testes")

import research_server  # noqa: E402


@pytest.fixture
def anyio_backend():
    """Os testes assíncronos rodam com asyncio (o SDK do MCP usa anyio)."""
    return "asyncio"


class FakePaper:
    """Imita o objeto que a biblioteca arxiv devolve."""

    def __init__(self, n: int, topic: str = "llm"):
        self._id = f"2601.0000{n}v1"
        self.title = f"Paper {n} sobre {topic}"
        self.authors = [SimpleNamespace(name="Ana Silva"), SimpleNamespace(name="Bruno Lima")]
        self.summary = f"Resumo do paper {n}. " * 50
        self.pdf_url = f"https://arxiv.org/pdf/{self._id}"
        self.published = datetime.datetime(2026, 1, n)

    def get_short_id(self) -> str:
        return self._id


@pytest.fixture
def papers_dir(tmp_path, monkeypatch):
    """Redireciona a pasta de artigos para uma pasta temporária vazia."""
    pasta = tmp_path / "papers"
    monkeypatch.setattr(research_server, "PAPER_DIR", str(pasta))
    return pasta


@pytest.fixture
def fake_arxiv(monkeypatch):
    """Faz o arxiv.Client().results() devolver artigos falsos e registra as buscas."""
    buscas = []

    def fake_results(self, search):
        buscas.append({"query": search.query, "max_results": search.max_results})
        return [FakePaper(i, search.query) for i in range(1, search.max_results + 1)]

    monkeypatch.setattr(research_server.arxiv.Client, "results", fake_results)
    return buscas


@pytest.fixture
def papers_salvos(papers_dir, fake_arxiv):
    """Pasta de artigos já com um tema salvo (llm_interpretability, 2 artigos)."""
    ids = research_server.search_papers("LLM interpretability", max_results=2)
    return ids

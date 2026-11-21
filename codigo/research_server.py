"""
Servidor MCP de pesquisa de artigos (arXiv).

Expõe:
  - Tools:     search_papers, extract_info
  - Resources: papers://folders, papers://{topic}
  - Prompt:    generate_search_prompt

Transporte:
  - stdio (padrão):        uv run research_server.py
  - Streamable HTTP:       MCP_TRANSPORT=http uv run research_server.py
                           (escuta em 0.0.0.0, porta da variável PORT ou 8000, endpoint /mcp)

Requer o SDK v1: uv add "mcp>=1.10,<2" arxiv
"""

import json
import os
import sys
from typing import List

import arxiv
from mcp.server.fastmcp import FastMCP  # SDK v2: from mcp.server import MCPServer

# Caminho absoluto: funciona de qualquer pasta de onde o processo for iniciado
PAPER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers")

mcp = FastMCP(
    "research",
    host="0.0.0.0",                          # só usado no modo HTTP
    port=int(os.environ.get("PORT", 8000)),  # só usado no modo HTTP
    stateless_http=True,                     # facilita rodar várias instâncias
)


def log(msg: str) -> None:
    """Logs vão para o stderr: no stdio, o stdout é o canal do protocolo."""
    print(msg, file=sys.stderr)


def topic_dir(topic: str) -> str:
    return os.path.join(PAPER_DIR, topic.lower().replace(" ", "_"))


def load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ───────────────────────── Tools ─────────────────────────

@mcp.tool()
def search_papers(topic: str, max_results: int = 5) -> List[str]:
    """
    Search for papers on arXiv based on a topic and store their information.

    Args:
        topic: The topic to search for
        max_results: Maximum number of results to retrieve (default: 5)

    Returns:
        List of paper IDs found in the search
    """
    results = arxiv.Client().results(arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    ))

    path = topic_dir(topic)
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, "papers_info.json")
    papers_info = load_json(file_path)

    paper_ids = []
    for paper in results:
        paper_id = paper.get_short_id()
        paper_ids.append(paper_id)
        papers_info[paper_id] = {
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "summary": paper.summary,
            "pdf_url": paper.pdf_url,
            "published": str(paper.published.date()),
        }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(papers_info, f, indent=2, ensure_ascii=False)

    log(f"Resultados salvos em: {file_path}")
    return paper_ids


@mcp.tool()
def extract_info(paper_id: str) -> str:
    """
    Search for information about a specific paper across all topic directories.

    Args:
        paper_id: The ID of the paper to look for

    Returns:
        JSON string with paper information if found, error message if not found
    """
    if not os.path.isdir(PAPER_DIR):
        return "No papers saved yet. Use search_papers first."

    for item in os.listdir(PAPER_DIR):
        papers_info = load_json(os.path.join(PAPER_DIR, item, "papers_info.json"))
        if paper_id in papers_info:
            return json.dumps(papers_info[paper_id], indent=2, ensure_ascii=False)

    return f"There's no saved information related to paper {paper_id}."


# ─────────────────────── Resources ───────────────────────

@mcp.resource("papers://folders")
def get_available_folders() -> str:
    """List all topic folders that have saved papers."""
    folders = []
    if os.path.isdir(PAPER_DIR):
        folders = sorted(
            d for d in os.listdir(PAPER_DIR)
            if os.path.isfile(os.path.join(PAPER_DIR, d, "papers_info.json"))
        )

    if not folders:
        return "# Available topics\n\nNo topics found. Use search_papers first.\n"

    lines = ["# Available topics", ""] + [f"- {f}" for f in folders]
    lines += ["", "Use @<topic> to read the papers of a topic."]
    return "\n".join(lines) + "\n"


@mcp.resource("papers://{topic}")
def get_topic_papers(topic: str) -> str:
    """Get the saved papers for a specific topic, formatted as markdown."""
    papers = load_json(os.path.join(topic_dir(topic), "papers_info.json"))
    if not papers:
        return f"# No papers found for topic: {topic}\n\nUse search_papers first.\n"

    parts = [f"# Papers on {topic.replace('_', ' ').title()}", "", f"Total: {len(papers)}", ""]
    for paper_id, info in papers.items():
        parts += [
            f"## {info['title']}",
            f"- **ID**: {paper_id}",
            f"- **Authors**: {', '.join(info['authors'])}",
            f"- **Published**: {info['published']}",
            f"- **PDF**: {info['pdf_url']}",
            "",
            info["summary"][:500] + "...",
            "",
            "---",
            "",
        ]
    return "\n".join(parts)


# ──────────────────────── Prompts ────────────────────────

@mcp.prompt()
def generate_search_prompt(topic: str, num_papers: int = 5) -> str:
    """Generate a prompt to find and discuss academic papers on a topic."""
    return (
        f"Use the search_papers tool to find {num_papers} papers about '{topic}'. "
        "Then, for each paper, use extract_info and summarize: title, authors, date, "
        "main contribution and method. Finish with an overview of the research "
        f"landscape in '{topic}': common themes, open questions and the most relevant papers. "
        "Use headings and bullet points."
    )


if __name__ == "__main__":
    if os.environ.get("MCP_TRANSPORT", "stdio").lower() == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")

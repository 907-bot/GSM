import typer
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional
from datetime import datetime

app = typer.Typer(
    name="gsm",
    help="Global Scientific Memory OS - Command Line Interface",
)
console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(
        Panel(
            "[bold green]Global Scientific Memory OS[/bold green]\n"
            "Version: 0.1.0\n"
            "Status: Active",
            title="GSM-OS",
        )
    )


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
):
    """Start the API server."""
    import uvicorn
    
    console.print(f"[bold blue]Starting GSM-OS API server on {host}:{port}[/bold blue]")
    
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=4,
    )


@app.command()
def worker(
    concurrency: int = 4,
    loglevel: str = "info",
):
    """Start a Celery worker."""
    import subprocess
    
    console.print(f"[bold blue]Starting Celery worker with {concurrency} concurrency[/bold blue]")
    
    subprocess.run([
        "celery",
        "-A", "src.workers.celery_app",
        "worker",
        "-l", loglevel,
        "-c", str(concurrency),
    ])


@app.command()
def beat(loglevel: str = "info"):
    """Start Celery beat scheduler."""
    import subprocess
    
    console.print("[bold blue]Starting Celery beat scheduler[/bold blue]")
    
    subprocess.run([
        "celery",
        "-A", "src.workers.celery_app",
        "beat",
        "-l", loglevel,
    ])


@app.command()
def search(
    query: str,
    domain: Optional[str] = None,
    limit: int = 10,
):
    """Search for papers."""
    from ..agents import get_all_agents
    
    console.print(f"[bold yellow]Searching for: {query}[/bold yellow]")
    
    agents = get_all_agents()
    all_papers = []
    
    for agent in agents:
        if domain and agent.domain != domain:
            continue
        
        try:
            papers = asyncio.run(
                agent.search_papers(query, limit=limit // len(agents))
            )
            all_papers.extend(papers)
        except Exception as e:
            console.print(f"[red]Error searching {agent.domain}: {e}[/red]")
    
    # Display results
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Title", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Authors", style="magenta")
    
    for paper in all_papers[:limit]:
        table.add_row(
            paper.get("title", "")[:50],
            paper.get("source", ""),
            ", ".join(paper.get("authors", [])[:2]),
        )
    
    console.print(table)


@app.command()
def stats():
    """Show system statistics."""
    from ..memory import EpisodicMemory, SemanticMemory
    
    console.print("[bold blue]Fetching system statistics...[/bold blue]")
    
    try:
        semantic = SemanticMemory()
        stats = asyncio.run(semantic.get_statistics())
        
        table = Table(title="System Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Concepts", str(stats.get("concepts", 0)))
        table.add_row("Papers", str(stats.get("papers", 0)))
        table.add_row("Relationships", str(stats.get("relationships", 0)))
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching statistics: {e}[/red]")


@app.command()
def replay(time_window: int = 7, sample_size: int = 100):
    """Run the scientific replay system."""
    from ..engines import ReplayEngine
    
    console.print("[bold yellow]Running replay system...[/bold yellow]")
    
    engine = ReplayEngine()
    result = asyncio.run(
        engine.replay_memories(time_window, sample_size)
    )
    
    console.print(Panel(str(result), title="Replay Result"))


@app.command()
def dream(duration: int = 30):
    """Run the digital dreaming cycle."""
    from ..engines import ReplayEngine
    
    console.print("[bold yellow]Running dream cycle...[/bold yellow]")
    
    engine = ReplayEngine()
    result = asyncio.run(engine.dream(duration))
    
    console.print(Panel(str(result), title="Dream Result"))


@app.command()
def graph(concept: str, depth: int = 2):
    """Visualize concept graph."""
    from ..engines import GraphDiscoveryEngine
    
    console.print(f"[bold yellow]Visualizing graph for: {concept}[/bold yellow]")
    
    engine = GraphDiscoveryEngine()
    data = asyncio.run(engine.visualize_subgraph(concept, depth))
    
    console.print(Panel(str(data), title="Graph Data"))


if __name__ == "__main__":
    app()

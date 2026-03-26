"""Rich terminal output for AICP."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live

console = Console(stderr=True)
output = Console()  # stdout for actual responses


def print_response(text: str) -> None:
    """Print an AI response with markdown rendering."""
    md = Markdown(text)
    output.print(md)


def print_error(msg: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/] {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/] {msg}")


def print_status(label: str, detail: str, ok: bool) -> None:
    """Print a status line for --check output."""
    icon = "[bold green]OK[/]" if ok else "[bold red]FAIL[/]"
    console.print(f"  [{icon}] {label}: {detail}")


def print_check_header() -> None:
    """Print the --check header."""
    console.print(Panel.fit("[bold]AICP System Check[/]", border_style="blue"))


def print_history_entry(
    status: str, timestamp: str, mode: str, backend: str,
    duration: float, prompt: str, record_id: str,
) -> None:
    """Print a single history entry."""
    color = "green" if status == "OK" else "red"
    prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
    console.print(
        f"  [{color}]{status:3s}[/] {timestamp}  "
        f"[cyan]{mode:5s}[/]  [magenta]{backend:6s}[/]  "
        f"{duration:5.1f}s  {prompt_preview}"
    )
    console.print(f"        [dim]ID: {record_id}[/]")


@contextmanager
def spinner(message: str = "Thinking...") -> Generator[None, None, None]:
    """Show a spinner while waiting for a response."""
    with Live(Spinner("dots", text=message), console=console, transient=True):
        yield

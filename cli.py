"""TokenLens CLI — Rich terminal reports for LLM cost attribution."""
import click
from rich.console import Console
from rich.table import Table
from tokenlens import TokenLens

console = Console()


@click.group()
@click.option("--db", default="tokenlens.db", help="SQLite database path")
@click.option("--budget", default=None, type=float, help="Monthly budget USD")
@click.pass_context
def cli(ctx, db, budget):
    """TokenLens — LLM API Cost Attribution & Optimization CLI."""
    ctx.obj = TokenLens(db_path=db, budget_usd=budget)


@cli.command()
@click.option("--by", "group",
              type=click.Choice(["feature", "model", "user_id", "endpoint"]),
              default="feature", help="Grouping dimension")
@click.pass_obj
def report(lens, group):
    """Show cost breakdown by dimension."""
    data = lens.cost_by(group)
    if not data:
        console.print("[yellow]No data yet. Integrate the SDK first![/yellow]")
        return
    table = Table(title=f"\U0001f4b0 Cost by {group}")
    table.add_column(group.replace("_", " ").title(), style="cyan")
    table.add_column("Cost ($)", justify="right", style="green")
    table.add_column("Tokens", justify="right")
    table.add_column("Calls", justify="right")
    for d in data:
        table.add_row(
            d["name"], f"${d['cost_usd']:.4f}",
            f"{d['tokens']:,}", str(d["calls"]),
        )
    console.print(table)
    total = sum(d["cost_usd"] for d in data)
    console.print(f"\n[bold]Total spend: ${total:.4f}[/bold]")


@cli.command()
@click.option("--threshold", default=2000, help="Input token bloat threshold")
@click.pass_obj
def analyze(lens, threshold):
    """Detect prompt bloat and suggest model downgrades."""
    bloat = lens.detect_bloat(threshold)
    if bloat:
        bt = Table(title="\U0001f388 Prompt Bloat Detected")
        bt.add_column("Feature", style="red")
        bt.add_column("Model")
        bt.add_column("Avg Input", justify="right")
        bt.add_column("Max Input", justify="right")
        bt.add_column("Calls", justify="right")
        for b in bloat:
            bt.add_row(b["feature"], b["model"], f"{b['avg_input']:.0f}",
                       f"{b['max_input']:.0f}", str(b["calls"]))
        console.print(bt)
    suggestions = lens.suggest_downgrades()
    if suggestions:
        st = Table(title="\u2b07\ufe0f Model Downgrade Suggestions")
        st.add_column("Current", style="red")
        st.add_column("Suggested", style="green")
        st.add_column("Current $", justify="right")
        st.add_column("Projected $", justify="right")
        st.add_column("Saving $", justify="right", style="bold green")
        for s in suggestions:
            st.add_row(
                s["current_model"], s["suggested_model"],
                f"${s['current_cost']:.4f}", f"${s['projected_cost']:.4f}",
                f"${s['monthly_saving']:.4f}",
            )
        console.print(st)
    if not bloat and not suggestions:
        console.print("[green]\u2705 No optimizations found — usage looks efficient![/green]")


@cli.command()
@click.pass_obj
def summary(lens):
    """Show current month spending summary."""
    total = lens.month_total()
    console.print(f"[bold]\U0001f4ca Current Month: ${total:.4f}[/bold]")
    if lens.budget_usd:
        pct = (total / lens.budget_usd) * 100
        color = "green" if pct < 80 else ("yellow" if pct < 100 else "red")
        console.print(
            f"[{color}]Budget: ${lens.budget_usd:.2f} | Used: {pct:.1f}%[/{color}]"
        )


if __name__ == "__main__":
    cli()

import typer
from rich import print as rprint
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services.auth_service import hash_password

app = typer.Typer(help="User management")

engine = create_engine(settings.app_db_url_sync)


@app.command()
def seed(
    username: str = typer.Option(..., help="Admin username"),
    email: str = typer.Option("admin@localhost", help="Admin email"),
    password: str = typer.Option(..., help="Admin password"),
):
    """Create initial admin user."""
    from app.database import Base
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        existing = s.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            rprint(f"[yellow]User '{username}' already exists (id={existing.id}, role={existing.role})[/yellow]")
            return

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin",
        )
        s.add(user)
        s.commit()
        rprint(f"[green]Admin user '{username}' created (id={user.id})[/green]")


@app.command("list")
def list_users():
    """List all users."""
    with Session(engine) as s:
        users = s.execute(select(User).order_by(User.id)).scalars().all()
        for u in users:
            status = "[green]active[/green]" if u.is_active else "[red]inactive[/red]"
            rprint(f"  {u.id:>3}  {u.username:<20} {u.role:<10} {u.email:<30} {status}")

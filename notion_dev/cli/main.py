# notion_dev/cli/main.py - Mise à jour pour affichage groupé
import click
import logging
import logging.handlers
import requests
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from ..core.config import Config
from ..core.notion_client import NotionClient
from ..core.asana_client import AsanaClient
from ..core.context_builder import ContextBuilder
from collections import defaultdict
from datetime import datetime

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(config: Config):
    """Configure logging with rotation"""
    log_file = Path.home() / ".notion-dev" / config.logging.file
    log_file.parent.mkdir(exist_ok=True)
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Create rotating file handler (max 10MB, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Console handler for errors only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    
    # Configure root logger
    root_logger.setLevel(getattr(logging, config.logging.level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


@click.group()
@click.version_option(package_name='notion-dev', prog_name='notion-dev')
@click.option('--config', default=None, help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """NotionDev - Intégration Notion ↔ Asana ↔ Git pour développeurs"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config

    # Commands that don't require existing config
    no_config_commands = ['login', 'status']

    # Check if current command needs config
    if ctx.invoked_subcommand in no_config_commands:
        ctx.obj['config'] = None
        return

    try:
        ctx.obj['config'] = Config.load(config)

        # Setup logging with rotation
        setup_logging(ctx.obj['config'])

        # Validation de la config
        if not ctx.obj['config'].validate():
            console.print("[red]❌ Invalid configuration. Check your config.yml file[/red]")
            console.print("[yellow]Run 'notion-dev login' to configure authentication[/yellow]")
            raise click.Abort()

    except FileNotFoundError:
        console.print("[red]❌ Configuration file not found[/red]")
        console.print("[yellow]Run 'notion-dev login' to create your configuration[/yellow]")
        raise click.Abort()


@cli.command()
@click.option('--notion-token', envvar='NOTION_TOKEN', help='Notion integration token')
@click.option('--notion-modules-db', envvar='NOTION_MODULES_DB', help='Notion Modules database ID')
@click.option('--notion-features-db', envvar='NOTION_FEATURES_DB', help='Notion Features database ID')
@click.option('--asana-token', envvar='ASANA_TOKEN', help='Asana personal access token')
@click.option('--asana-workspace', envvar='ASANA_WORKSPACE', help='Asana workspace GID')
@click.option('--asana-user', envvar='ASANA_USER', help='Asana user GID')
@click.option('--asana-portfolio', envvar='ASANA_PORTFOLIO', help='Asana portfolio GID (optional)')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token (optional, for cloning repos)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts (non-interactive mode)')
@click.pass_context
def login(ctx, notion_token, notion_modules_db, notion_features_db,
          asana_token, asana_workspace, asana_user, asana_portfolio, github_token, yes):
    """Configure authentication for Notion and Asana.

    Run interactively to be guided through the setup, or provide all options
    for non-interactive use (CI/CD, scripts).

    Examples:
        notion-dev login                    # Interactive mode
        notion-dev login --yes \\
            --notion-token secret_xxx \\
            --notion-modules-db xxx \\
            --notion-features-db xxx \\
            --asana-token xxx \\
            --asana-workspace xxx \\
            --asana-user xxx \\
            --github-token ghp_xxx         # Non-interactive mode with GitHub
    """
    import yaml
    import os

    config_dir = Path.home() / ".notion-dev"
    config_file = config_dir / "config.yml"

    console.print(Panel.fit(
        "[bold blue]NotionDev Configuration Setup[/bold blue]\n"
        "This will configure your Notion and Asana authentication.",
        title="Login"
    ))

    # Check if config already exists
    if config_file.exists() and not yes:
        if not Confirm.ask(f"Configuration file already exists at {config_file}. Overwrite?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Collect Notion configuration
    console.print("\n[bold cyan]== Notion Configuration ==[/bold cyan]")
    console.print("Get your integration token at: https://www.notion.so/my-integrations")

    if not notion_token:
        if yes:
            console.print("[red]Error: --notion-token is required in non-interactive mode[/red]")
            raise click.Abort()
        notion_token = Prompt.ask("Notion Integration Token", password=True)

    if not notion_modules_db:
        if yes:
            console.print("[red]Error: --notion-modules-db is required in non-interactive mode[/red]")
            raise click.Abort()
        console.print("[dim]Find the database ID in the URL: notion.so/xxx?v=... (the xxx part)[/dim]")
        notion_modules_db = Prompt.ask("Modules Database ID")

    if not notion_features_db:
        if yes:
            console.print("[red]Error: --notion-features-db is required in non-interactive mode[/red]")
            raise click.Abort()
        notion_features_db = Prompt.ask("Features Database ID")

    # Validate Notion connection
    console.print("\n[dim]Testing Notion connection...[/dim]")
    notion_client = NotionClient(notion_token, notion_modules_db, notion_features_db)
    notion_result = notion_client.test_connection()

    if notion_result["success"]:
        console.print(f"[green]✓ Notion connected as: {notion_result['user']}[/green]")
        console.print(f"[green]✓ Modules DB: {notion_result['modules_db']}[/green]")
        console.print(f"[green]✓ Features DB: {notion_result['features_db']}[/green]")
    else:
        console.print("[red]✗ Notion connection failed:[/red]")
        for error in notion_result["errors"]:
            console.print(f"[red]  - {error}[/red]")
        if not yes:
            if not Confirm.ask("Continue anyway?", default=False):
                raise click.Abort()

    # Collect Asana configuration
    console.print("\n[bold cyan]== Asana Configuration ==[/bold cyan]")
    console.print("Get your personal access token at: https://app.asana.com/0/my-apps")

    if not asana_token:
        if yes:
            console.print("[red]Error: --asana-token is required in non-interactive mode[/red]")
            raise click.Abort()
        asana_token = Prompt.ask("Asana Personal Access Token", password=True)

    # If workspace/user not provided, try to auto-detect
    if not asana_workspace or not asana_user:
        console.print("\n[dim]Detecting Asana workspace and user...[/dim]")
        try:
            temp_client = AsanaClient(asana_token, "temp", "temp")
            response = temp_client._make_request("GET", "users/me")
            user_data = response.get('data', {})
            detected_user = user_data.get('gid')
            detected_user_name = user_data.get('name')

            workspaces = user_data.get('workspaces', [])
            if workspaces:
                if len(workspaces) == 1:
                    detected_workspace = workspaces[0]['gid']
                    detected_workspace_name = workspaces[0]['name']
                    console.print(f"[green]✓ Found user: {detected_user_name} ({detected_user})[/green]")
                    console.print(f"[green]✓ Found workspace: {detected_workspace_name} ({detected_workspace})[/green]")
                else:
                    console.print(f"[green]✓ Found user: {detected_user_name} ({detected_user})[/green]")
                    console.print("\n[yellow]Multiple workspaces found:[/yellow]")
                    for i, ws in enumerate(workspaces, 1):
                        console.print(f"  {i}. {ws['name']} ({ws['gid']})")
                    if not yes:
                        choice = Prompt.ask("Select workspace number", default="1")
                        detected_workspace = workspaces[int(choice) - 1]['gid']
                        detected_workspace_name = workspaces[int(choice) - 1]['name']
                    else:
                        detected_workspace = workspaces[0]['gid']
                        detected_workspace_name = workspaces[0]['name']

                if not asana_workspace:
                    asana_workspace = detected_workspace
                if not asana_user:
                    asana_user = detected_user
        except Exception as e:
            console.print(f"[yellow]Could not auto-detect: {e}[/yellow]")

    if not asana_workspace:
        if yes:
            console.print("[red]Error: --asana-workspace is required in non-interactive mode[/red]")
            raise click.Abort()
        asana_workspace = Prompt.ask("Asana Workspace GID")

    if not asana_user:
        if yes:
            console.print("[red]Error: --asana-user is required in non-interactive mode[/red]")
            raise click.Abort()
        asana_user = Prompt.ask("Asana User GID")

    if not asana_portfolio and not yes:
        console.print("\n[dim]Portfolio filtering is optional. Leave empty to see all tasks.[/dim]")
        asana_portfolio = Prompt.ask("Asana Portfolio GID (optional)", default="")
        if not asana_portfolio:
            asana_portfolio = None

    # Collect GitHub configuration (optional)
    console.print("\n[bold cyan]== GitHub Configuration (Optional) ==[/bold cyan]")
    console.print("Get your personal access token at: https://github.com/settings/tokens")
    console.print("[dim]GitHub token is optional - only needed for cloning private repositories[/dim]")

    if not github_token and not yes:
        github_token = Prompt.ask("GitHub Personal Access Token (optional)", password=True, default="")
        if not github_token:
            github_token = None

    # Validate GitHub connection if token provided
    if github_token:
        console.print("\n[dim]Testing GitHub connection...[/dim]")
        try:
            github_response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {github_token}"}
            )
            if github_response.status_code == 200:
                github_user = github_response.json().get("login", "Unknown")
                console.print(f"[green]✓ GitHub connected as: {github_user}[/green]")
            else:
                console.print(f"[yellow]⚠ GitHub authentication failed (status {github_response.status_code})[/yellow]")
                if not yes:
                    if not Confirm.ask("Continue without GitHub?", default=True):
                        raise click.Abort()
                    github_token = None
        except Exception as e:
            console.print(f"[yellow]⚠ Could not verify GitHub token: {e}[/yellow]")
            if not yes:
                if not Confirm.ask("Continue without GitHub?", default=True):
                    raise click.Abort()
                github_token = None

    # Validate Asana connection
    console.print("\n[dim]Testing Asana connection...[/dim]")
    asana_client = AsanaClient(asana_token, asana_workspace, asana_user, asana_portfolio)
    asana_result = asana_client.test_connection()

    if asana_result["success"]:
        console.print(f"[green]✓ Asana connected as: {asana_result['user']}[/green]")
        console.print(f"[green]✓ Workspace: {asana_result['workspace']}[/green]")
        if asana_result["portfolio"]:
            console.print(f"[green]✓ Portfolio: {asana_result['portfolio']}[/green]")
    else:
        console.print("[red]✗ Asana connection failed:[/red]")
        for error in asana_result["errors"]:
            console.print(f"[red]  - {error}[/red]")
        if not yes:
            if not Confirm.ask("Continue anyway?", default=False):
                raise click.Abort()

    # Build config
    config_data = {
        'notion': {
            'token': notion_token,
            'database_modules_id': notion_modules_db,
            'database_features_id': notion_features_db
        },
        'asana': {
            'access_token': asana_token,
            'workspace_gid': asana_workspace,
            'user_gid': asana_user
        },
        'ai': {
            'context_max_length': 32000,
            'include_code_examples': True
        },
        'git': {
            'default_branch': 'main',
            'header_comment_style': 'auto'
        },
        'logging': {
            'level': 'INFO',
            'file': 'notion-dev.log'
        }
    }

    if asana_portfolio:
        config_data['asana']['portfolio_gid'] = asana_portfolio

    if github_token:
        config_data['github'] = {
            'token': github_token,
            'clone_dir': '/tmp/notiondev',
            'shallow_clone': True
        }

    # Save config
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    # Set restrictive permissions (owner read/write only)
    os.chmod(config_file, 0o600)

    console.print(f"\n[green]✓ Configuration saved to {config_file}[/green]")
    console.print("[dim]File permissions set to 600 (owner read/write only)[/dim]")
    console.print("\n[bold green]Setup complete! You can now use notion-dev commands.[/bold green]")


@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def status(ctx, output_json):
    """Check connection status for Notion and Asana.

    Validates that your authentication tokens are working and that
    you have access to the configured databases/workspaces.
    """
    config_path = ctx.obj.get('config_path')
    config_file = Path(config_path) if config_path else Path.home() / ".notion-dev" / "config.yml"

    if not config_file.exists():
        if output_json:
            console.print(json.dumps({"error": "Configuration file not found", "hint": "Run 'notion-dev login' first"}))
        else:
            console.print("[red]❌ Configuration file not found[/red]")
            console.print("[yellow]Run 'notion-dev login' to create your configuration[/yellow]")
        return

    try:
        config = Config.load(config_path)
    except Exception as e:
        if output_json:
            console.print(json.dumps({"error": f"Failed to load config: {e}"}))
        else:
            console.print(f"[red]❌ Failed to load configuration: {e}[/red]")
        return

    results = {
        "config_file": str(config_file),
        "notion": None,
        "asana": None,
        "github": None
    }

    # Test Notion
    if not output_json:
        console.print("\n[bold cyan]== Notion Status ==[/bold cyan]")
    try:
        notion_client = NotionClient(
            config.notion.token,
            config.notion.database_modules_id,
            config.notion.database_features_id
        )
        notion_result = notion_client.test_connection()
        results["notion"] = notion_result

        if not output_json:
            if notion_result["success"]:
                console.print(f"[green]✓ Connected as: {notion_result['user']}[/green]")
                console.print(f"[green]✓ Modules DB: {notion_result['modules_db']}[/green]")
                console.print(f"[green]✓ Features DB: {notion_result['features_db']}[/green]")
            else:
                console.print("[red]✗ Connection failed:[/red]")
                for error in notion_result["errors"]:
                    console.print(f"[red]  - {error}[/red]")
    except Exception as e:
        results["notion"] = {"success": False, "errors": [str(e)]}
        if not output_json:
            console.print(f"[red]✗ Error: {e}[/red]")

    # Test Asana
    if not output_json:
        console.print("\n[bold cyan]== Asana Status ==[/bold cyan]")
    try:
        asana_client = AsanaClient(
            config.asana.access_token,
            config.asana.workspace_gid,
            config.asana.user_gid,
            config.asana.portfolio_gid
        )
        asana_result = asana_client.test_connection()
        results["asana"] = asana_result

        if not output_json:
            if asana_result["success"]:
                console.print(f"[green]✓ Connected as: {asana_result['user']}[/green]")
                console.print(f"[green]✓ Workspace: {asana_result['workspace']}[/green]")
                if asana_result.get("portfolio"):
                    console.print(f"[green]✓ Portfolio: {asana_result['portfolio']}[/green]")
                else:
                    console.print("[dim]  No portfolio configured[/dim]")
            else:
                console.print("[red]✗ Connection failed:[/red]")
                for error in asana_result["errors"]:
                    console.print(f"[red]  - {error}[/red]")
    except Exception as e:
        results["asana"] = {"success": False, "errors": [str(e)]}
        if not output_json:
            console.print(f"[red]✗ Error: {e}[/red]")

    # Test GitHub (optional)
    if not output_json:
        console.print("\n[bold cyan]== GitHub Status ==[/bold cyan]")

    if hasattr(config, 'github') and config.github and config.github.token:
        try:
            github_response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {config.github.token}"}
            )
            if github_response.status_code == 200:
                github_user = github_response.json().get("login", "Unknown")
                results["github"] = {"success": True, "user": github_user}
                if not output_json:
                    console.print(f"[green]✓ Connected as: {github_user}[/green]")
            else:
                results["github"] = {"success": False, "errors": [f"HTTP {github_response.status_code}"]}
                if not output_json:
                    console.print(f"[red]✗ Authentication failed (status {github_response.status_code})[/red]")
        except Exception as e:
            results["github"] = {"success": False, "errors": [str(e)]}
            if not output_json:
                console.print(f"[red]✗ Error: {e}[/red]")
    else:
        results["github"] = {"success": True, "configured": False}
        if not output_json:
            console.print("[dim]  Not configured (optional)[/dim]")

    # Summary
    all_ok = (results["notion"] and results["notion"].get("success", False) and
              results["asana"] and results["asana"].get("success", False))

    if output_json:
        results["all_ok"] = all_ok
        console.print(json.dumps(results, indent=2))
    else:
        console.print("\n" + "=" * 40)
        if all_ok:
            console.print("[bold green]✓ All connections OK[/bold green]")
        else:
            console.print("[bold red]✗ Some connections failed[/bold red]")
            console.print("[yellow]Run 'notion-dev login' to reconfigure[/yellow]")


@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def info(ctx, output_json):
    """Affiche les informations du projet courant"""
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    # Prepare JSON data structure
    info_data = {
        "project": {
            "name": project_info['name'],
            "path": project_info['path'],
            "cache": project_info['cache'],
            "is_git_repo": project_info['is_git_repo'],
            "notion_database_modules_id": config.notion.database_modules_id,
            "notion_database_features_id": config.notion.database_features_id,
            "asana_workspace_gid": config.asana.workspace_gid,
            "asana_portfolio_gid": config.asana.portfolio_gid
        },
        "current_task": None
    }
    
    if not output_json:
        # Panneau avec les infos du projet
        portfolio_info = f"Portfolio: {config.asana.portfolio_gid[:8]}..." if config.asana.portfolio_gid else "Portfolio: Non configuré (tous les tickets)"
        
        info_content = f"""[bold]Nom:[/bold] {project_info['name']}
[bold]Chemin:[/bold] {project_info['path']}
[bold]Cache:[/bold] {project_info['cache']}
[bold]Git Repository:[/bold] {'✅ Oui' if project_info['is_git_repo'] else '❌ Non'}

[bold]Configuration:[/bold]
- Notion Database Modules: {config.notion.database_modules_id[:8]}...
- Notion Database Features: {config.notion.database_features_id[:8]}...
- Asana Workspace: {config.asana.workspace_gid}
- {portfolio_info}
"""
        
        panel = Panel(
            info_content,
            title=f"📊 Projet: {project_info['name']}",
            border_style="blue"
        )
        console.print(panel)
    
    # Check current working task
    import os
    cache_dir = project_info['path'] + "/.notion-dev"
    current_task_file = f"{cache_dir}/current_task.txt"
    
    if os.path.exists(current_task_file):
        with open(current_task_file, 'r') as f:
            current_task_id = f.read().strip()
        
        # Get task details from Asana
        asana_client = AsanaClient(
            config.asana.access_token,
            config.asana.workspace_gid,
            config.asana.user_gid,
            config.asana.portfolio_gid
        )
        
        if not output_json:
            with console.status("[bold green]Récupération du ticket courant..."):
                task = asana_client.get_task(current_task_id)
        else:
            task = asana_client.get_task(current_task_id)
        
        if task:
            # Build Asana URL
            project_id = task.project_gid or "0"
            asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"
            
            # Handle multiple feature codes
            if hasattr(task, 'feature_codes') and task.feature_codes:
                feature_display = ', '.join(task.feature_codes)
                if len(task.feature_codes) > 1:
                    feature_display += f" (principal: {task.feature_code})"
            else:
                feature_display = task.feature_code or 'Non défini'
            
            # Try to get started_at timestamp from current_task file metadata
            started_at = None
            try:
                started_at = datetime.fromtimestamp(os.path.getmtime(current_task_file)).isoformat()
            except (OSError, ValueError):
                pass
            
            # Get Notion URL if we have a feature code
            notion_url = None
            if task.feature_code:
                # Get feature from Notion to get the page ID
                notion_client = NotionClient(
                    config.notion.token,
                    config.notion.database_modules_id,
                    config.notion.database_features_id
                )
                feature = notion_client.get_feature(task.feature_code)
                if feature and hasattr(feature, 'notion_id'):
                    notion_url = f"https://www.notion.so/{feature.notion_id.replace('-', '')}"
            
            # Prepare task data for JSON
            info_data["current_task"] = {
                "id": task.gid,
                "name": task.name,
                "feature_code": task.feature_code,
                "feature_codes": task.feature_codes if hasattr(task, 'feature_codes') else [],
                "status": "completed" if task.completed else "in_progress",
                "started_at": started_at,
                "url": asana_url,
                "notion_url": notion_url
            }
            
            if not output_json:
                task_content = f"""[bold]{task.name}[/bold]

ID: {task.gid}
Feature Code(s): {feature_display}
Statut: {'✅ Terminé' if task.completed else '🔄 En cours'}
Asana: [link={asana_url}]{asana_url}[/link]"""
                
                if notion_url:
                    task_content += f"\nNotion: [link={notion_url}]{notion_url}[/link]"
                
                task_panel = Panel(
                    task_content,
                    title="🎯 Ticket en cours",
                    border_style="green"
                )
                console.print(task_panel)
        else:
            if not output_json:
                console.print("[dim]⚠️ Ticket courant introuvable (supprimé ?)[/dim]")
    else:
        if not output_json:
            console.print("[dim]💡 Aucun ticket en cours. Utilise 'notion-dev work [ID]' pour commencer.[/dim]")
    
    if output_json:
        print(json.dumps(info_data, indent=2, ensure_ascii=False))

@cli.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def tickets(ctx, output_json):
    """Liste vos tickets Asana assignés (filtrés par portfolio si configuré)"""
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    if not output_json:
        # Afficher le projet courant et le filtre portfolio
        portfolio_info = f" (Portfolio: {config.asana.portfolio_gid[:8]}...)" if config.asana.portfolio_gid else " (Tous projets)"
        console.print(f"[dim]Projet courant: {project_info['name']} ({project_info['path']}){portfolio_info}[/dim]\n")
    
    if not output_json:
        with console.status("[bold green]Récupération des tickets Asana..."):
            asana_client = AsanaClient(
                config.asana.access_token,
                config.asana.workspace_gid,
                config.asana.user_gid,
                config.asana.portfolio_gid
            )
            
            tasks = asana_client.get_my_tasks()
    else:
        asana_client = AsanaClient(
            config.asana.access_token,
            config.asana.workspace_gid,
            config.asana.user_gid,
            config.asana.portfolio_gid
        )
        
        tasks = asana_client.get_my_tasks()
    
    if not tasks:
        if output_json:
            print(json.dumps({"tasks": []}, indent=2, ensure_ascii=False))
        else:
            console.print("[yellow]Aucun ticket trouvé[/yellow]")
            if config.asana.portfolio_gid:
                console.print("[dim]💡 Vérifiez que le portfolio contient des projets avec vos tickets[/dim]")
        return
    
    # Prepare JSON data if needed
    if output_json:
        # Get Notion client for fetching Notion URLs
        notion_client = NotionClient(
            config.notion.token,
            config.notion.database_modules_id,
            config.notion.database_features_id
        )
        
        tasks_data = []
        for task in tasks:
            # Build Asana URL
            project_id = task.project_gid or "0"
            asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"
            
            # Get Notion URL if we have a feature code
            notion_url = None
            if task.feature_code:
                try:
                    feature = notion_client.get_feature(task.feature_code)
                    if feature and hasattr(feature, 'notion_id'):
                        notion_url = f"https://www.notion.so/{feature.notion_id.replace('-', '')}"
                except Exception:
                    pass
            
            task_data = {
                "id": task.gid,
                "name": task.name,
                "feature_code": task.feature_code,
                "status": "completed" if task.completed else "in_progress",
                "completed": task.completed,
                "due_on": task.due_on,
                "url": asana_url,
                "notion_url": notion_url,
                "project_name": task.project_name,
                "project_gid": task.project_gid
            }
            tasks_data.append(task_data)
        
        print(json.dumps({"tasks": tasks_data}, indent=2, ensure_ascii=False))
        return
    
    # Affichage en tableau avec groupement par projet si portfolio configuré
    if config.asana.portfolio_gid:
        # Grouper les tickets par projet
        projects_tasks = defaultdict(list)
        for task in tasks:
            project_name = task.project_name or "📋 Sans projet"
            projects_tasks[project_name].append(task)
        
        # Afficher un tableau par projet (projets récents en haut)
        # Récupérer l'ordre des projets depuis le portfolio
        portfolio_projects = asana_client.get_portfolio_projects()
        project_order = {p.name: i for i, p in enumerate(portfolio_projects)}
        
        # Trier les projets selon l'ordre du portfolio
        sorted_projects = sorted(projects_tasks.items(), 
                               key=lambda x: project_order.get(x[0], 999))
        
        for project_name, project_tasks in sorted_projects:
            # En-tête de projet
            console.print(f"\n[bold blue]📁 {project_name}[/bold blue] ({len(project_tasks)} tickets)")
            
            # Tableau pour ce projet
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Nom", style="white", width=45)
            table.add_column("Feature", style="green", width=12)
            table.add_column("Statut", style="magenta", width=12)
            
            for task in project_tasks:
                status = "✅ Terminé" if task.completed else "🔄 En cours"
                feature_code = task.feature_code or "❓ Non défini"
                
                table.add_row(
                    task.gid,  # Full ID
                    task.name[:40] + "..." if len(task.name) > 40 else task.name,
                    feature_code,
                    status
                )
            
            console.print(table)
        
        # Résumé total
        total_tasks = len(tasks)
        total_projects = len(projects_tasks)
        console.print(f"\n[dim]Total: {total_tasks} tickets dans {total_projects} projets[/dim]")
        
    else:
        # Affichage en tableau unique si pas de portfolio
        table = Table(title="Mes Tickets Asana")
        table.add_column("ID", style="cyan")
        table.add_column("Nom", style="white")
        table.add_column("Feature", style="green")
        table.add_column("Projet", style="blue")
        table.add_column("Statut", style="magenta")
        
        for task in tasks:
            status = "✅ Terminé" if task.completed else "🔄 En cours"
            feature_code = task.feature_code or "❓ Non défini"
            project_name = task.project_name or "Sans projet"
            
            table.add_row(
                task.gid[-8:],  # Derniers 8 caractères de l'ID
                task.name[:40] + "..." if len(task.name) > 40 else task.name,
                feature_code,
                project_name[:20] + "..." if len(project_name) > 20 else project_name,
                status
            )
        
        console.print(table)

@cli.command()
@click.argument('task_id')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts (for non-interactive use)')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def work(ctx, task_id, yes, output_json):
    """Démarre le travail sur un ticket spécifique

    Examples:
        notion-dev work 1234567890  # Interactive mode with confirmation
        notion-dev work 1234567890 --yes  # Non-interactive mode (for scripts/MCP)
        notion-dev work 1234567890 --yes --json  # JSON output for MCP
    """
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    # Clients
    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )
    
    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )
    
    context_builder = ContextBuilder(notion_client, config)

    # Load task
    if not output_json:
        with console.status("[bold green]Chargement du ticket..."):
            task = asana_client.get_task(task_id)
    else:
        task = asana_client.get_task(task_id)

    if not task:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Ticket {task_id} not found"}, indent=2))
        else:
            console.print(f"[red]❌ Ticket {task_id} non trouvé[/red]")
        return

    # Check if we're switching from another task
    cache_dir = project_info['path'] + "/.notion-dev"
    current_task_file = f"{cache_dir}/current_task.txt"

    # Ensure cache directory exists
    import os
    os.makedirs(cache_dir, exist_ok=True)

    previous_task_id = None
    if os.path.exists(current_task_file):
        with open(current_task_file, 'r') as f:
            previous_task_id = f.read().strip()

    # If switching to a different task, add transition comment to previous task
    if previous_task_id and previous_task_id != task_id:
        if not output_json:
            with console.status(f"[bold yellow]Vérification du ticket précédent {previous_task_id[-8:]}..."):
                previous_task = asana_client.get_task(previous_task_id)
        else:
            previous_task = asana_client.get_task(previous_task_id)

        if previous_task and not previous_task.completed:
            if not output_json:
                with console.status("[bold yellow]Ajout du commentaire de transition..."):
                    success = asana_client.add_comment_to_task(previous_task_id, "moves on to another task, stay tuned")
                if success:
                    console.print(f"[dim]✅ Commentaire de transition ajouté au ticket {previous_task_id[-8:]}[/dim]")
                else:
                    console.print("[dim]⚠️ Impossible d'ajouter le commentaire de transition[/dim]")
            else:
                asana_client.add_comment_to_task(previous_task_id, "moves on to another task, stay tuned")

    # Add comment to indicate working on the new task
    comment_added = False
    if not output_json:
        with console.status("[bold green]Ajout du commentaire 'is working on it'..."):
            comment_added = asana_client.add_comment_to_task(task_id, "is working on it")
        if comment_added:
            console.print("[dim]✅ Commentaire ajouté au ticket Asana[/dim]")
        else:
            console.print("[dim]⚠️ Impossible d'ajouter le commentaire[/dim]")
    else:
        comment_added = asana_client.add_comment_to_task(task_id, "is working on it")

    # Update current task cache
    with open(current_task_file, 'w') as f:
        f.write(task_id)

    if not output_json:
        # Affichage des infos du ticket + projet
        panel = Panel(
            f"[bold]{task.name}[/bold]\n\n"
            f"ID: {task.gid}\n"
            f"Feature Code: {task.feature_code or 'Non défini'}\n"
            f"Projet Asana: {task.project_name or 'Non défini'}\n"
            f"Statut: {'✅ Terminé' if task.completed else '🔄 En cours'}\n\n"
            f"[dim]Projet local: {project_info['name']}[/dim]",
            title="📋 Ticket Asana"
        )
        console.print(panel)

    if not task.feature_code:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "error": "No feature code defined for this ticket",
                "hint": "Add 'Feature Code: XX01' in the Asana description"
            }, indent=2))
        else:
            console.print("[red]❌ Ce ticket n'a pas de code feature défini[/red]")
            console.print("[yellow]💡 Ajoutez 'Feature Code: XX01' dans la description Asana[/yellow]")
        return

    # Génération du contexte
    if not output_json:
        with console.status("[bold green]Génération du contexte IA..."):
            context = context_builder.build_task_context(task)
    else:
        context = context_builder.build_task_context(task)

    if not context:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Unable to load feature {task.feature_code}"}, indent=2))
        else:
            console.print(f"[red]❌ Impossible de charger la feature {task.feature_code}[/red]")
        return

    feature = context['feature']

    if not output_json:
        # Affichage du contexte feature
        feature_panel = Panel(
            f"[bold green]{feature.code} - {feature.name}[/bold green]\n\n"
            f"Module: {feature.module_name}\n"
            f"Status: {feature.status}\n"
            f"Plans: {', '.join(feature.plan) if isinstance(feature.plan, list) else (feature.plan or 'N/A')}\n"
            f"User Rights: {', '.join(feature.user_rights) if isinstance(feature.user_rights, list) else (feature.user_rights or 'N/A')}",
            title="🎯 Feature"
        )
        console.print(feature_panel)

    # Export vers AGENTS.md (forcé à la racine du projet)
    export_success = False
    if yes or output_json or Confirm.ask("Exporter le contexte vers AGENTS.md?", default=True):
        if not output_json:
            with console.status("[bold green]Export vers AGENTS.md..."):
                export_success = context_builder.export_to_agents_md(context, project_info['path'])
        else:
            export_success = context_builder.export_to_agents_md(context, project_info['path'])

        if not output_json:
            if export_success:
                console.print(f"[green]✅ Contexte exporté vers {project_info['path']}/AGENTS.md[/green]")
                console.print("[yellow]💡 Vous pouvez maintenant ouvrir votre éditeur AI et commencer à coder![/yellow]")
                console.print("[dim]Le fichier .cursorrules sera automatiquement chargé par Cursor[/dim]")
            else:
                console.print("[red]❌ Erreur lors de l'export[/red]")

    # JSON output
    if output_json:
        import json as json_module
        print(json_module.dumps({
            "success": True,
            "ticket": {
                "id": task.gid,
                "name": task.name,
                "feature_code": task.feature_code,
                "status": "completed" if task.completed else "in_progress",
                "project": task.project_name or "Non défini"
            },
            "feature": f"{task.feature_code} - Feature loaded",
            "actions": {
                "comment_added": comment_added,
                "context_exported": export_success,
                "export_path": f"{project_info['path']}/AGENTS.md"
            },
            "message": f"Vous travaillez maintenant sur: {task.name}"
        }, indent=2, ensure_ascii=False))

@cli.command()
@click.argument('message')
@click.pass_context
def comment(ctx, message):
    """Ajoute un commentaire au ticket en cours de travail"""
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    # Check current task
    import os
    cache_dir = project_info['path'] + "/.notion-dev"
    current_task_file = f"{cache_dir}/current_task.txt"
    
    if not os.path.exists(current_task_file):
        console.print("[red]❌ Aucun ticket en cours de travail[/red]")
        console.print("[dim]💡 Utilise 'notion-dev work [ID]' pour commencer à travailler sur un ticket[/dim]")
        return
    
    with open(current_task_file, 'r') as f:
        current_task_id = f.read().strip()
    
    # Add comment to current task
    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )
    
    with console.status(f"[bold green]Ajout du commentaire au ticket {current_task_id[-8:]}..."):
        success = asana_client.add_comment_to_task(current_task_id, message)
    
    if success:
        console.print(f"[green]✅ Commentaire ajouté au ticket {current_task_id[-8:]}[/green]")
        console.print(f"[dim]Message: \"{message}\"[/dim]")
    else:
        console.print("[red]❌ Impossible d'ajouter le commentaire[/red]")

@cli.command()
@click.pass_context
def done(ctx):
    """Marque le travail terminé et réassigne le ticket à son créateur"""
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    # Check current task
    import os
    cache_dir = project_info['path'] + "/.notion-dev"
    current_task_file = f"{cache_dir}/current_task.txt"
    
    if not os.path.exists(current_task_file):
        console.print("[red]❌ Aucun ticket en cours de travail[/red]")
        console.print("[dim]💡 Utilise 'notion-dev work [ID]' pour commencer à travailler sur un ticket[/dim]")
        return
    
    with open(current_task_file, 'r') as f:
        current_task_id = f.read().strip()
    
    # Get task details
    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )
    
    with console.status(f"[bold green]Récupération du ticket {current_task_id[-8:]}..."):
        task = asana_client.get_task(current_task_id)
    
    if not task:
        console.print(f"[red]❌ Ticket {current_task_id} non trouvé[/red]")
        return
    
    # Add completion comment
    with console.status("[bold green]Ajout du commentaire de fin..."):
        comment_success = asana_client.add_comment_to_task(current_task_id, "work is done, waiting for approval")
    
    # Reassign to creator if available
    reassign_success = False
    if task.created_by_gid:
        with console.status("[bold green]Réassignation au créateur..."):
            reassign_success = asana_client.reassign_task(current_task_id, task.created_by_gid)
    
    # Display results
    if comment_success:
        console.print(f"[green]✅ Commentaire de fin ajouté au ticket {current_task_id[-8:]}[/green]")
    else:
        console.print("[red]❌ Impossible d'ajouter le commentaire de fin[/red]")
    
    if reassign_success:
        console.print("[green]✅ Ticket réassigné au créateur[/green]")
    elif task.created_by_gid:
        console.print("[yellow]⚠️ Impossible de réassigner le ticket[/yellow]")
    else:
        console.print("[yellow]⚠️ Pas de créateur identifié pour la réassignation[/yellow]")
    
    # Clear current task
    if comment_success:
        os.remove(current_task_file)
        console.print("[dim]💡 Ticket retiré de la liste 'en cours'[/dim]")

@cli.command()
@click.option('--feature', '-f', help='Code de la feature (required in non-interactive mode)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts (for non-interactive use)')
@click.pass_context
def context(ctx, feature, yes):
    """Génère le contexte IA pour une feature

    Examples:
        notion-dev context  # Interactive mode, will prompt for feature code
        notion-dev context --feature CC01  # Specify feature code
        notion-dev context -f CC01 --yes  # Non-interactive mode (for scripts/MCP)
    """
    config = ctx.obj['config']
    project_info = config.get_project_info()

    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )

    context_builder = ContextBuilder(notion_client, config)

    if not feature:
        if yes:
            console.print("[red]❌ --feature est requis en mode non-interactif (--yes)[/red]")
            return
        feature = Prompt.ask("Code de la feature")
    
    console.print(f"[dim]Projet courant: {project_info['name']}[/dim]\n")
    
    with console.status(f"[bold green]Chargement de la feature {feature}..."):
        context = context_builder.build_feature_context(feature)
    
    if not context:
        console.print(f"[red]❌ Feature {feature} non trouvée[/red]")
        return
    
    feature_obj = context['feature']
    
    # Affichage des infos
    info_panel = Panel(
        f"[bold green]{feature_obj.code} - {feature_obj.name}[/bold green]\n\n"
        f"Module: {feature_obj.module_name}\n"
        f"Status: {feature_obj.status}\n"
        f"Description: {feature_obj.content[:200]}...\n\n"
        f"[dim]Export vers: {project_info['path']}/.cursor/[/dim]",
        title="🎯 Feature trouvée"
    )
    console.print(info_panel)
    
    # Export
    # Skip confirmation if --yes flag is set
    if yes or Confirm.ask("Exporter vers AGENTS.md?", default=True):
        success = context_builder.export_to_agents_md(context)

        if success:
            console.print("[green]✅ Contexte exporté vers AGENTS.md![/green]")
        else:
            console.print("[red]❌ Erreur lors de l'export[/red]")

@cli.command('create-ticket')
@click.option('--name', '-n', required=True, help='Ticket title')
@click.option('--feature', '-f', default='', help='Feature code (e.g., CC01)')
@click.option('--notes', default='', help='Ticket description')
@click.option('--due', default='', help='Due date (YYYY-MM-DD)')
@click.option('--project', '-p', default='', help='Asana project GID (uses first portfolio project if not specified)')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def create_ticket(ctx, name, feature, notes, due, project, output_json):
    """Create a new Asana ticket"""
    config = ctx.obj['config']

    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )

    # Prepend feature code to notes if provided
    full_notes = notes
    if feature:
        feature_header = f"## Feature Code\n{feature}\n\n"
        full_notes = feature_header + notes

    if not output_json:
        with console.status("[bold green]Création du ticket..."):
            task = asana_client.create_task(
                name=name,
                notes=full_notes,
                project_gid=project if project else None,
                due_on=due if due else None
            )
    else:
        task = asana_client.create_task(
            name=name,
            notes=full_notes,
            project_gid=project if project else None,
            due_on=due if due else None
        )

    if task:
        project_id = task.project_gid or "0"
        asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"

        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "ticket": {
                    "id": task.gid,
                    "name": task.name,
                    "feature_code": task.feature_code,
                    "url": asana_url,
                    "due_on": task.due_on
                }
            }, indent=2, ensure_ascii=False))
        else:
            console.print("[green]✅ Ticket créé avec succès![/green]")
            console.print(f"[bold]ID:[/bold] {task.gid}")
            console.print(f"[bold]Nom:[/bold] {task.name}")
            if task.feature_code:
                console.print(f"[bold]Feature:[/bold] {task.feature_code}")
            console.print(f"[bold]URL:[/bold] [link={asana_url}]{asana_url}[/link]")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": "Failed to create ticket"}, indent=2))
        else:
            console.print("[red]❌ Erreur lors de la création du ticket[/red]")


@cli.command('update-ticket')
@click.argument('task_id')
@click.option('--name', '-n', default='', help='New ticket title')
@click.option('--notes', default='', help='New notes content')
@click.option('--append', is_flag=True, help='Append to existing notes instead of replacing')
@click.option('--due', default='', help='New due date (YYYY-MM-DD)')
@click.option('--assignee', default='', help='New assignee GID')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def update_ticket(ctx, task_id, name, notes, append, due, assignee, output_json):
    """Update an existing Asana ticket"""
    config = ctx.obj['config']

    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )

    if not output_json:
        with console.status(f"[bold green]Mise à jour du ticket {task_id}..."):
            task = asana_client.update_task(
                task_gid=task_id,
                name=name if name else None,
                notes=notes if notes else None,
                append_notes=append,
                due_on=due if due else None,
                assignee_gid=assignee if assignee else None
            )
    else:
        task = asana_client.update_task(
            task_gid=task_id,
            name=name if name else None,
            notes=notes if notes else None,
            append_notes=append,
            due_on=due if due else None,
            assignee_gid=assignee if assignee else None
        )

    if task:
        project_id = task.project_gid or "0"
        asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"

        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "ticket": {
                    "id": task.gid,
                    "name": task.name,
                    "feature_code": task.feature_code,
                    "url": asana_url,
                    "due_on": task.due_on,
                    "completed": task.completed
                }
            }, indent=2, ensure_ascii=False))
        else:
            console.print("[green]✅ Ticket mis à jour![/green]")
            console.print(f"[bold]ID:[/bold] {task.gid}")
            console.print(f"[bold]Nom:[/bold] {task.name}")
            if task.feature_code:
                console.print(f"[bold]Feature:[/bold] {task.feature_code}")
            console.print(f"[bold]URL:[/bold] [link={asana_url}]{asana_url}[/link]")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Failed to update ticket {task_id}"}, indent=2))
        else:
            console.print(f"[red]❌ Erreur lors de la mise à jour du ticket {task_id}[/red]")


# =============================================================================
# Notion Commands - Modules
# =============================================================================

@cli.command('modules')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def list_modules(ctx, output_json):
    """List all modules from Notion database"""
    config = ctx.obj['config']

    notion_client = NotionClient(config.notion.token, config.notion.database_modules_id)

    if not output_json:
        with console.status("[bold green]Fetching modules..."):
            modules = notion_client.get_all_modules()
    else:
        modules = notion_client.get_all_modules()

    if output_json:
        import json as json_module
        modules_data = [{
            "code_prefix": m.code_prefix,
            "name": m.name,
            "description": m.description,
            "application": m.application,
            "status": m.status,
            "notion_id": m.notion_id
        } for m in modules]
        print(json_module.dumps({"modules": modules_data}, indent=2, ensure_ascii=False))
    else:
        if not modules:
            console.print("[yellow]No modules found[/yellow]")
            return

        table = Table(title="Modules Notion")
        table.add_column("Code", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Application", style="green")
        table.add_column("Status", style="magenta")

        for module in modules:
            table.add_row(
                module.code_prefix,
                module.name,
                module.application or "-",
                module.status or "-"
            )

        console.print(table)
        console.print(f"\n[dim]{len(modules)} module(s) found[/dim]")


@cli.command('module')
@click.argument('code_prefix')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def get_module(ctx, code_prefix, output_json):
    """Get detailed information about a module"""
    config = ctx.obj['config']

    notion_client = NotionClient(config.notion.token, config.notion.database_modules_id)

    if not output_json:
        with console.status(f"[bold green]Fetching module {code_prefix}..."):
            module = notion_client.get_module_by_prefix(code_prefix.upper())
    else:
        module = notion_client.get_module_by_prefix(code_prefix.upper())

    if not module:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Module '{code_prefix}' not found"}, indent=2))
        else:
            console.print(f"[red]❌ Module '{code_prefix}' not found[/red]")
        return

    if output_json:
        import json as json_module
        module_data = {
            "code_prefix": module.code_prefix,
            "name": module.name,
            "description": module.description,
            "application": module.application,
            "status": module.status,
            "notion_id": module.notion_id,
            "content": module.content,
            "repository_url": module.repository_url,
            "branch": module.branch,
            "code_path": module.code_path
        }
        print(json_module.dumps({"module": module_data}, indent=2, ensure_ascii=False))
    else:
        panel = Panel(
            f"[bold]Name:[/bold] {module.name}\n"
            f"[bold]Code:[/bold] {module.code_prefix}\n"
            f"[bold]Application:[/bold] {module.application or '-'}\n"
            f"[bold]Status:[/bold] {module.status or '-'}\n"
            f"[bold]Description:[/bold] {module.description or '-'}",
            title=f"Module {module.code_prefix}"
        )
        console.print(panel)

        if module.content:
            console.print("\n[bold]Content:[/bold]")
            console.print(module.content[:2000] + ("..." if len(module.content) > 2000 else ""))


# =============================================================================
# Notion Commands - Features
# =============================================================================

@cli.command('features')
@click.option('--module', '-m', 'module_prefix', default='', help='Filter by module prefix (e.g., CC, API)')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def list_features(ctx, module_prefix, output_json):
    """List all features from Notion database"""
    config = ctx.obj['config']

    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )

    if not output_json:
        with console.status("[bold green]Fetching features..."):
            features = notion_client.get_all_features()
    else:
        features = notion_client.get_all_features()

    # Filter by module if specified
    if module_prefix:
        features = [f for f in features if f.code.upper().startswith(module_prefix.upper())]

    if output_json:
        import json as json_module
        features_data = [{
            "code": f.code,
            "name": f.name,
            "module_name": f.module_name,
            "status": f.status,
            "plan": f.plan,
            "user_rights": f.user_rights,
            "notion_id": f.notion_id
        } for f in features]
        print(json_module.dumps({"features": features_data}, indent=2, ensure_ascii=False))
    else:
        if not features:
            console.print("[yellow]No features found[/yellow]")
            return

        table = Table(title="Features Notion")
        table.add_column("Code", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Module", style="green")
        table.add_column("Status", style="magenta")

        for feature in features:
            table.add_row(
                feature.code,
                feature.name,
                feature.module_name or "-",
                feature.status or "-"
            )

        console.print(table)
        console.print(f"\n[dim]{len(features)} feature(s) found[/dim]")


@cli.command('feature')
@click.argument('code')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def get_feature(ctx, code, output_json):
    """Get detailed information about a feature"""
    config = ctx.obj['config']

    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )

    if not output_json:
        with console.status(f"[bold green]Fetching feature {code}..."):
            feature = notion_client.get_feature_by_code(code.upper())
    else:
        feature = notion_client.get_feature_by_code(code.upper())

    if not feature:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Feature '{code}' not found"}, indent=2))
        else:
            console.print(f"[red]❌ Feature '{code}' not found[/red]")
        return

    # Get module info (content + repository info)
    module_content = None
    module_repository_url = None
    module_branch = None
    module_code_path = None
    if feature.module_name:
        module = notion_client.get_module_by_prefix(feature.code[:2].upper())
        if module:
            module_content = module.content
            module_repository_url = module.repository_url
            module_branch = module.branch
            module_code_path = module.code_path

    if output_json:
        import json as json_module
        feature_data = {
            "code": feature.code,
            "name": feature.name,
            "module_name": feature.module_name,
            "status": feature.status,
            "plan": feature.plan,
            "user_rights": feature.user_rights,
            "notion_id": feature.notion_id,
            "content": feature.content,
            "module_content": module_content,
            "module_repository_url": module_repository_url,
            "module_branch": module_branch,
            "module_code_path": module_code_path
        }
        print(json_module.dumps({"feature": feature_data}, indent=2, ensure_ascii=False))
    else:
        panel = Panel(
            f"[bold]Name:[/bold] {feature.name}\n"
            f"[bold]Code:[/bold] {feature.code}\n"
            f"[bold]Module:[/bold] {feature.module_name or '-'}\n"
            f"[bold]Status:[/bold] {feature.status or '-'}\n"
            f"[bold]Plan:[/bold] {', '.join(feature.plan) if feature.plan else '-'}\n"
            f"[bold]User Rights:[/bold] {', '.join(feature.user_rights) if feature.user_rights else '-'}",
            title=f"Feature {feature.code}"
        )
        console.print(panel)

        if feature.content:
            console.print("\n[bold]Content:[/bold]")
            console.print(feature.content[:3000] + ("..." if len(feature.content) > 3000 else ""))


# =============================================================================
# Asana Commands - Projects
# =============================================================================

@cli.command('projects')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def list_projects(ctx, output_json):
    """List Asana projects from portfolio"""
    config = ctx.obj['config']

    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid,
        config.asana.portfolio_gid
    )

    if not output_json:
        with console.status("[bold green]Fetching projects..."):
            projects = asana_client.get_portfolio_projects()
    else:
        projects = asana_client.get_portfolio_projects()

    if output_json:
        import json as json_module
        projects_data = [{
            "gid": p.gid,
            "name": p.name,
            "color": p.color
        } for p in projects]
        print(json_module.dumps({"projects": projects_data}, indent=2, ensure_ascii=False))
    else:
        if not projects:
            console.print("[yellow]No projects found in portfolio[/yellow]")
            return

        table = Table(title="Asana Projects")
        table.add_column("GID", style="cyan", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Color", style="green")

        for project in projects:
            table.add_row(
                project.gid,
                project.name,
                project.color or "-"
            )

        console.print(table)
        console.print(f"\n[dim]{len(projects)} project(s) found[/dim]")


# =============================================================================
# Notion Commands - Create/Update Modules
# =============================================================================

@cli.command('create-module')
@click.option('--name', '-n', required=True, help='Module name')
@click.option('--prefix', '-p', required=True, help='Code prefix (2-3 chars, e.g., CC, API)')
@click.option('--description', '-d', required=True, help='Short description')
@click.option('--application', '-a', default='Backend', type=click.Choice(['Backend', 'Frontend', 'Service']), help='Application type')
@click.option('--content', default='', help='Full documentation content in markdown')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def create_module(ctx, name, prefix, description, application, content, output_json):
    """Create a new module in Notion"""
    config = ctx.obj['config']

    notion_client = NotionClient(config.notion.token, config.notion.database_modules_id)

    if not output_json:
        with console.status("[bold green]Creating module..."):
            module = notion_client.create_module(
                name=name,
                code_prefix=prefix.upper(),
                description=description,
                application=application,
                content_markdown=content
            )
    else:
        module = notion_client.create_module(
            name=name,
            code_prefix=prefix.upper(),
            description=description,
            application=application,
            content_markdown=content
        )

    if module:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "message": f"Module '{name}' created successfully",
                "module": {
                    "code_prefix": module.code_prefix,
                    "name": module.name,
                    "application": module.application,
                    "status": module.status,
                    "notion_id": module.notion_id
                }
            }, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✅ Module '{name}' created successfully![/green]")
            console.print(f"[bold]Code:[/bold] {module.code_prefix}")
            console.print(f"[bold]Notion ID:[/bold] {module.notion_id}")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": "Failed to create module"}, indent=2))
        else:
            console.print("[red]❌ Error creating module[/red]")


@cli.command('create-feature')
@click.option('--name', '-n', required=True, help='Feature name')
@click.option('--module', '-m', required=True, help='Parent module prefix (e.g., CC, API)')
@click.option('--content', default='', help='Documentation content in markdown')
@click.option('--plan', default='', help='Comma-separated plans (e.g., free,premium)')
@click.option('--rights', default='', help='Comma-separated user rights (e.g., admin,user)')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def create_feature(ctx, name, module, content, plan, rights, output_json):
    """Create a new feature in Notion"""
    config = ctx.obj['config']

    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )

    # Parse plan and rights
    plan_list = [p.strip() for p in plan.split(',') if p.strip()] if plan else []
    rights_list = [r.strip() for r in rights.split(',') if r.strip()] if rights else []

    if not output_json:
        with console.status("[bold green]Creating feature..."):
            feature = notion_client.create_feature(
                name=name,
                module_prefix=module.upper(),
                content_markdown=content,
                plan=plan_list,
                user_rights=rights_list
            )
    else:
        feature = notion_client.create_feature(
            name=name,
            module_prefix=module.upper(),
            content_markdown=content,
            plan=plan_list,
            user_rights=rights_list
        )

    if feature:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "message": f"Feature '{feature.code} - {name}' created successfully",
                "feature": {
                    "code": feature.code,
                    "name": feature.name,
                    "module": feature.module_name,
                    "status": feature.status,
                    "notion_id": feature.notion_id
                }
            }, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✅ Feature '{feature.code} - {name}' created successfully![/green]")
            console.print(f"[bold]Code:[/bold] {feature.code}")
            console.print(f"[bold]Notion ID:[/bold] {feature.notion_id}")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": "Failed to create feature"}, indent=2))
        else:
            console.print("[red]❌ Error creating feature[/red]")


@cli.command('update-module')
@click.argument('code_prefix')
@click.option('--content', '-c', required=True, help='New content in markdown')
@click.option('--append', is_flag=True, help='Append to existing content instead of replacing')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def update_module(ctx, code_prefix, content, append, output_json):
    """Update a module's documentation content"""
    config = ctx.obj['config']

    notion_client = NotionClient(config.notion.token, config.notion.database_modules_id)

    if not output_json:
        with console.status(f"[bold green]Updating module {code_prefix}..."):
            success = notion_client.update_module_content(
                code_prefix=code_prefix.upper(),
                content_markdown=content,
                replace=not append
            )
    else:
        success = notion_client.update_module_content(
            code_prefix=code_prefix.upper(),
            content_markdown=content,
            replace=not append
        )

    if success:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "message": f"Module '{code_prefix}' updated successfully"
            }, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✅ Module '{code_prefix}' updated successfully![/green]")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Failed to update module '{code_prefix}'"}, indent=2))
        else:
            console.print(f"[red]❌ Error updating module '{code_prefix}'[/red]")


@cli.command('update-feature')
@click.argument('code')
@click.option('--content', '-c', required=True, help='New content in markdown')
@click.option('--append', is_flag=True, help='Append to existing content instead of replacing')
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def update_feature(ctx, code, content, append, output_json):
    """Update a feature's documentation content"""
    config = ctx.obj['config']

    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )

    if not output_json:
        with console.status(f"[bold green]Updating feature {code}..."):
            success = notion_client.update_feature_content(
                code=code.upper(),
                content_markdown=content,
                replace=not append
            )
    else:
        success = notion_client.update_feature_content(
            code=code.upper(),
            content_markdown=content,
            replace=not append
        )

    if success:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "message": f"Feature '{code}' updated successfully"
            }, indent=2, ensure_ascii=False))
        else:
            console.print(f"[green]✅ Feature '{code}' updated successfully![/green]")
    else:
        if output_json:
            import json as json_module
            print(json_module.dumps({"error": f"Failed to update feature '{code}'"}, indent=2))
        else:
            console.print(f"[red]❌ Error updating feature '{code}'[/red]")


@cli.command()
@click.pass_context
def interactive(ctx):
    """Mode interactif"""
    config = ctx.obj['config']
    project_info = config.get_project_info()
    
    # Bannière avec info projet
    portfolio_info = f"\nPortfolio: {config.asana.portfolio_gid[:8]}..." if config.asana.portfolio_gid else ""
    banner = Panel(
        f"[bold blue]NotionDev CLI v1.0[/bold blue]\n"
        f"Projet: {project_info['name']}\n"
        f"Path: {project_info['path']}{portfolio_info}",
        title="🚀 Bienvenue"
    )
    console.print(banner)
    
    while True:
        console.print("\n[bold]Que voulez-vous faire ?[/bold]")
        console.print("1. 📋 Voir mes tickets Asana")
        console.print("2. 🎯 Générer contexte pour une feature")
        console.print("3. 🔄 Travailler sur un ticket")
        console.print("4. 💬 Ajouter un commentaire au ticket en cours")
        console.print("5. ✅ Marquer le travail comme terminé")
        console.print("6. 📊 Infos du projet")
        console.print("7. 🚪 Quitter")
        
        choice = Prompt.ask("Votre choix", choices=["1", "2", "3", "4", "5", "6", "7"])
        
        if choice == "1":
            ctx.invoke(tickets)
        elif choice == "2":
            feature_code = Prompt.ask("Code de la feature")
            ctx.invoke(context, feature=feature_code)
        elif choice == "3":
            task_id = Prompt.ask("ID du ticket")
            ctx.invoke(work, task_id=task_id)
        elif choice == "4":
            # Check if there's a current task
            current_task_file = Path.home() / ".notion-dev" / "current_task.txt"
            if current_task_file.exists():
                message = Prompt.ask("Votre commentaire")
                ctx.invoke(comment, message=message)
            else:
                console.print("[yellow]⚠️ Aucun ticket en cours. Utilisez d'abord 'Travailler sur un ticket'[/yellow]")
        elif choice == "5":
            # Check if there's a current task
            current_task_file = Path.home() / ".notion-dev" / "current_task.txt"
            if current_task_file.exists():
                if Confirm.ask("Marquer le travail comme terminé et réassigner au créateur ?"):
                    ctx.invoke(done)
            else:
                console.print("[yellow]⚠️ Aucun ticket en cours. Utilisez d'abord 'Travailler sur un ticket'[/yellow]")
        elif choice == "6":
            ctx.invoke(info)
        elif choice == "7":
            console.print("[green]👋 À bientôt![/green]")
            break


if __name__ == '__main__':
    cli()


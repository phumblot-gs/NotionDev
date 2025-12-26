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
@click.option('--config', default=None, help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """NotionDev - Intégration Notion ↔ Asana ↔ Git pour développeurs"""
    try:
        ctx.ensure_object(dict)
        ctx.obj['config'] = Config.load(config)
        
        # Setup logging with rotation
        setup_logging(ctx.obj['config'])
        
        # Validation de la config
        if not ctx.obj['config'].validate():
            console.print("[red]❌ Configuration invalide. Vérifiez votre fichier config.yml[/red]")
            raise click.Abort()
            
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        console.print("[yellow]💡 Créez le fichier de configuration: ~/.notion-dev/config.yml[/yellow]")
        raise click.Abort()

@cli.command()
@click.pass_context  
def debug_features(ctx):
    """Debug: Liste toutes les features dans Notion"""
    config = ctx.obj['config']
    notion_client = NotionClient(config.notion.token, 
                                config.notion.database_features_id, 
                                config.notion.database_modules_id)
    
    # Query all features
    url = f"https://api.notion.com/v1/databases/{config.notion.database_features_id}/query"
    headers = {
        "Authorization": f"Bearer {config.notion.token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    response = requests.post(url, headers=headers, json={})
    results = response.json().get('results', [])
    
    console.print(f"[bold]Found {len(results)} features in Notion:[/bold]")
    for page in results[:10]:  # Show first 10
        props = page['properties']
        # Try to get code from different property types
        code = None
        if 'code' in props:
            if 'rich_text' in props['code'] and props['code']['rich_text']:
                code = props['code']['rich_text'][0]['plain_text']
            elif 'title' in props['code'] and props['code']['title']:
                code = props['code']['title'][0]['plain_text']
        
        name = None
        if 'name' in props:
            if 'title' in props['name'] and props['name']['title']:
                name = props['name']['title'][0]['plain_text']
            elif 'rich_text' in props['name'] and props['name']['rich_text']:
                name = props['name']['rich_text'][0]['plain_text']
                
        console.print(f"- Code: {code}, Name: {name}")

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
@click.pass_context
def work(ctx, task_id, yes):
    """Démarre le travail sur un ticket spécifique

    Examples:
        notion-dev work 1234567890  # Interactive mode with confirmation
        notion-dev work 1234567890 --yes  # Non-interactive mode (for scripts/MCP)
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
    
    with console.status("[bold green]Chargement du ticket..."):
        task = asana_client.get_task(task_id)
    
    if not task:
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
        with console.status(f"[bold yellow]Vérification du ticket précédent {previous_task_id[-8:]}..."):
            previous_task = asana_client.get_task(previous_task_id)
        
        if previous_task and not previous_task.completed:
            with console.status("[bold yellow]Ajout du commentaire de transition..."):
                success = asana_client.add_comment_to_task(previous_task_id, "moves on to another task, stay tuned")
                if success:
                    console.print(f"[dim]✅ Commentaire de transition ajouté au ticket {previous_task_id[-8:]}[/dim]")
                else:
                    console.print("[dim]⚠️ Impossible d'ajouter le commentaire de transition[/dim]")
    
    # Add comment to indicate working on the new task
    with console.status("[bold green]Ajout du commentaire 'is working on it'..."):
        success = asana_client.add_comment_to_task(task_id, "is working on it")
        if success:
            console.print("[dim]✅ Commentaire ajouté au ticket Asana[/dim]")
        else:
            console.print("[dim]⚠️ Impossible d'ajouter le commentaire[/dim]")
    
    # Update current task cache
    with open(current_task_file, 'w') as f:
        f.write(task_id)
    
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
        console.print("[red]❌ Ce ticket n'a pas de code feature défini[/red]")
        console.print("[yellow]💡 Ajoutez 'Feature Code: XX01' dans la description Asana[/yellow]")
        return
    
    # Génération du contexte
    with console.status("[bold green]Génération du contexte IA..."):
        context = context_builder.build_task_context(task)
    
    if not context:
        console.print(f"[red]❌ Impossible de charger la feature {task.feature_code}[/red]")
        return
    
    # Affichage du contexte feature
    feature = context['feature']
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
    # Skip confirmation if --yes flag is set
    if yes or Confirm.ask("Exporter le contexte vers AGENTS.md?", default=True):
        with console.status("[bold green]Export vers AGENTS.md..."):
            # Force export to project root, not current directory
            success = context_builder.export_to_agents_md(context, project_info['path'])

        if success:
            console.print(f"[green]✅ Contexte exporté vers {project_info['path']}/AGENTS.md[/green]")
            console.print("[yellow]💡 Vous pouvez maintenant ouvrir votre éditeur AI et commencer à coder![/yellow]")
            console.print("[dim]Le fichier .cursorrules sera automatiquement chargé par Cursor[/dim]")
        else:
            console.print("[red]❌ Erreur lors de l'export[/red]")

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
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def create_ticket(ctx, name, feature, notes, due, output_json):
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
                due_on=due if due else None
            )
    else:
        task = asana_client.create_task(
            name=name,
            notes=full_notes,
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


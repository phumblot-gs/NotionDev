#!/bin/bash

# NotionDev - Script d'installation automatique pour macOS
# Usage: ./install_notion_dev.sh

set -e  # Arrêter le script en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction d'affichage avec couleurs
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTION_DEV_DIR="$SCRIPT_DIR/notion_dev"
INSTALL_DIR="$HOME/notion-dev-install"
CONFIG_DIR="$HOME/.notion-dev"

print_status "🚀 Installation de NotionDev pour macOS"
echo "=================================================="

# Vérification des prérequis
print_status "Vérification des prérequis..."

# Vérifier Python 3.10+
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 n'est pas installé. Installez-le via Homebrew: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python 3.10+ requis. Version actuelle: $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION détecté"

# Vérifier pip
if ! python3 -m pip --version &> /dev/null; then
    print_error "pip n'est pas installé"
    exit 1
fi

print_success "pip détecté"

# Vérifier que le dossier source existe
if [ ! -d "$NOTION_DEV_DIR" ]; then
    print_error "Dossier notion_dev non trouvé dans $NOTION_DEV_DIR"
    print_error "Assurez-vous que le script est dans le même dossier que notion_dev/"
    exit 1
fi

print_success "Dossier source notion_dev trouvé"

# Créer le dossier d'installation
print_status "Création du dossier d'installation..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copier la structure du projet
print_status "Copie des fichiers du projet..."

# Créer la structure de dossiers
mkdir -p "$INSTALL_DIR/notion_dev/core"
mkdir -p "$INSTALL_DIR/notion_dev/cli"
mkdir -p "$INSTALL_DIR/notion_dev/models"
mkdir -p "$INSTALL_DIR/notion_dev/utils"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/templates"

# Copier les fichiers Python depuis notion_dev/
if [ -d "$NOTION_DEV_DIR/core" ]; then
    cp -r "$NOTION_DEV_DIR/core"/* "$INSTALL_DIR/notion_dev/core/"
fi

# Gérer le dossier CLI
if [ -d "$NOTION_DEV_DIR/cli" ]; then
    cp -r "$NOTION_DEV_DIR/cli"/* "$INSTALL_DIR/notion_dev/cli/"
fi

# Créer main.py dans cli/ s'il n'existe pas (c'est le fichier du prototype)
if [ ! -f "$INSTALL_DIR/notion_dev/cli/main.py" ]; then
    print_warning "Fichier main.py manquant, création depuis le prototype..."
    
    cat > "$INSTALL_DIR/notion_dev/cli/main.py" << 'MAINPY'
import click
import logging
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich import print as rprint
from ..core.config import Config
from ..core.notion_client import NotionClient
from ..core.asana_client import AsanaClient
from ..core.context_builder import ContextBuilder

console = Console()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group()
@click.option('--config', default=None, help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """NotionDev - Intégration Notion ↔ Asana ↔ Git pour développeurs"""
    try:
        ctx.ensure_object(dict)
        ctx.obj['config'] = Config.load(config)
        
        # Validation de la config
        if not ctx.obj['config'].validate():
            console.print("[red]❌ Configuration invalide. Vérifiez votre fichier config.yml[/red]")
            raise click.Abort()
            
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        console.print("[yellow]💡 Utilisez 'notion-dev init' pour créer la configuration[/yellow]")
        raise click.Abort()

@cli.command()
@click.pass_context
def tickets(ctx):
    """Liste vos tickets Asana assignés"""
    config = ctx.obj['config']
    
    with console.status("[bold green]Récupération des tickets Asana..."):
        asana_client = AsanaClient(
            config.asana.access_token,
            config.asana.workspace_gid,
            config.asana.user_gid
        )
        
        tasks = asana_client.get_my_tasks()
    
    if not tasks:
        console.print("[yellow]Aucun ticket trouvé[/yellow]")
        return
    
    # Affichage sous forme de tableau
    table = Table(title="Mes Tickets Asana")
    table.add_column("ID", style="cyan")
    table.add_column("Nom", style="white")
    table.add_column("Feature", style="green")
    table.add_column("Statut", style="magenta")
    
    for task in tasks:
        status = "✅ Terminé" if task.completed else "🔄 En cours"
        feature_code = task.feature_code or "❓ Non défini"
        
        table.add_row(
            task.gid[-8:],  # Derniers 8 caractères de l'ID
            task.name[:50] + "..." if len(task.name) > 50 else task.name,
            feature_code,
            status
        )
    
    console.print(table)

@cli.command()
@click.argument('task_id')
@click.pass_context
def work(ctx, task_id):
    """Démarre le travail sur un ticket spécifique"""
    config = ctx.obj['config']
    
    # Clients
    asana_client = AsanaClient(
        config.asana.access_token,
        config.asana.workspace_gid,
        config.asana.user_gid
    )
    
    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )
    
    context_builder = ContextBuilder(notion_client)
    
    with console.status("[bold green]Chargement du ticket..."):
        task = asana_client.get_task(task_id)
    
    if not task:
        console.print(f"[red]❌ Ticket {task_id} non trouvé[/red]")
        return
    
    # Affichage des infos du ticket
    panel = Panel(
        f"[bold]{task.name}[/bold]\n\n"
        f"ID: {task.gid}\n"
        f"Feature Code: {task.feature_code or 'Non défini'}\n"
        f"Statut: {'✅ Terminé' if task.completed else '🔄 En cours'}",
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
        f"Plans: {', '.join(feature.plan)}\n"
        f"User Rights: {', '.join(feature.user_rights)}",
        title="🎯 Feature"
    )
    console.print(feature_panel)
    
    # Export vers AGENTS.md
    if Confirm.ask("Exporter le contexte vers AGENTS.md?", default=True):
        with console.status("[bold green]Export vers AGENTS.md..."):
            success = context_builder.export_to_agents_md(
                context,
                config.project.repository_path
            )

        if success:
            console.print("[green]✅ Contexte exporté vers AGENTS.md[/green]")
            console.print("[yellow]💡 Vous pouvez maintenant ouvrir votre éditeur AI et commencer à coder![/yellow]")
        else:
            console.print("[red]❌ Erreur lors de l'export[/red]")

@cli.command()
@click.option('--feature', help='Code de la feature')
@click.pass_context
def context(ctx, feature):
    """Génère le contexte IA pour une feature"""
    config = ctx.obj['config']
    
    notion_client = NotionClient(
        config.notion.token,
        config.notion.database_modules_id,
        config.notion.database_features_id
    )
    
    context_builder = ContextBuilder(notion_client)
    
    if not feature:
        feature = Prompt.ask("Code de la feature")
    
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
        f"Description: {feature_obj.content[:200]}...",
        title="🎯 Feature trouvée"
    )
    console.print(info_panel)
    
    # Export
    if Confirm.ask("Exporter vers AGENTS.md?", default=True):
        success = context_builder.export_to_agents_md(
            context,
            config.project.repository_path
        )

        if success:
            console.print("[green]✅ Contexte exporté vers AGENTS.md![/green]")
        else:
            console.print("[red]❌ Erreur lors de l'export[/red]")

@cli.command()
@click.pass_context
def interactive(ctx):
    """Mode interactif"""
    config = ctx.obj['config']
    
    # Bannière
    banner = Panel(
        "[bold blue]NotionDev CLI v1.0[/bold blue]\n"
        f"Projet: {config.project.name}",
        title="🚀 Bienvenue"
    )
    console.print(banner)
    
    while True:
        console.print("\n[bold]Que voulez-vous faire ?[/bold]")
        console.print("1. 📋 Voir mes tickets Asana")
        console.print("2. 🎯 Générer contexte pour une feature")
        console.print("3. 🔄 Travailler sur un ticket")
        console.print("4. 🚪 Quitter")
        
        choice = Prompt.ask("Votre choix", choices=["1", "2", "3", "4"])
        
        if choice == "1":
            ctx.invoke(tickets)
        elif choice == "2":
            feature_code = Prompt.ask("Code de la feature")
            ctx.invoke(context, feature=feature_code)
        elif choice == "3":
            task_id = Prompt.ask("ID du ticket")
            ctx.invoke(work, task_id=task_id)
        elif choice == "4":
            console.print("[green]👋 À bientôt![/green]")
            break

if __name__ == '__main__':
    cli()
MAINPY
fi

# Créer __init__.py dans cli/ s'il n'existe pas
if [ ! -f "$INSTALL_DIR/notion_dev/cli/__init__.py" ]; then
    touch "$INSTALL_DIR/notion_dev/cli/__init__.py"
fi

# Copier __init__.py si il existe
if [ -f "$NOTION_DEV_DIR/__init__.py" ]; then
    cp "$NOTION_DEV_DIR/__init__.py" "$INSTALL_DIR/notion_dev/"
fi

# Note: AsanaClient is now copied from the source directory with portfolio support

# Créer les fichiers de configuration du projet
cat > "$INSTALL_DIR/setup.py" << 'EOF'
from setuptools import setup, find_packages

setup(
    name="notion-dev",
    version="1.0.0",
    author="Votre Équipe",
    author_email="dev@votre-entreprise.com",
    description="Intégration Notion ↔ Asana ↔ Git pour développeurs",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=[
        "asana>=3.2.0",
        "notion-client>=2.2.1", 
        "click>=8.1.7",
        "pyyaml>=6.0.1",
        "rich>=13.7.0",
        "requests>=2.31.0",
        "gitpython>=3.1.40",
    ],
    entry_points={
        "console_scripts": [
            "notion-dev=notion_dev.cli.main:cli",
        ],
    },
)
EOF

cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
asana>=3.2.0
notion-client>=2.2.1
click>=8.1.7
pyyaml>=6.0.1
rich>=13.7.0
requests>=2.31.0
gitpython>=3.1.40
EOF

cat > "$INSTALL_DIR/README.md" << 'EOF'
# NotionDev

Intégration Notion ↔ Asana ↔ Git pour développeurs

## Installation

```bash
pip install -e .
```

## Configuration

Créer `~/.notion-dev/config.yml` avec vos tokens API.

## Usage

```bash
notion-dev tickets        # Lister vos tickets
notion-dev work TASK-ID   # Travailler sur un ticket
notion-dev interactive    # Mode interactif
```
EOF

# Créer tous les fichiers __init__.py nécessaires
cat > "$INSTALL_DIR/notion_dev/__init__.py" << 'EOF'
"""
NotionDev - Intégration Notion ↔ Asana ↔ Git pour développeurs
"""

__version__ = "1.0.0"

from .core.config import Config
from .core.models import Feature, Module, AsanaTask
from .core.notion_client import NotionClient
from .core.asana_client import AsanaClient
from .core.context_builder import ContextBuilder

__all__ = [
    'Config',
    'Feature', 
    'Module',
    'AsanaTask',
    'NotionClient',
    'AsanaClient', 
    'ContextBuilder'
]
EOF

# Créer __init__.py pour chaque sous-module
touch "$INSTALL_DIR/notion_dev/core/__init__.py"
touch "$INSTALL_DIR/notion_dev/cli/__init__.py"
touch "$INSTALL_DIR/notion_dev/models/__init__.py"
touch "$INSTALL_DIR/notion_dev/utils/__init__.py"

print_success "Fichiers copiés avec succès"

# Créer l'environnement virtuel
print_status "Création de l'environnement virtuel..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

print_success "Environnement virtuel créé"

# Installer les dépendances
print_status "Installation des dépendances..."
pip install --upgrade pip
pip install -r requirements.txt

print_success "Dépendances installées"

# Installer le package en mode développement
print_status "Installation de NotionDev..."
pip install -e .

print_success "NotionDev installé"

# Créer le dossier de configuration
print_status "Configuration initiale..."
mkdir -p "$CONFIG_DIR"

# Créer un fichier de config exemple s'il n'existe pas
if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    if [ ! -f "$CONFIG_DIR/config.example.yml" ]; then
        cat > "$CONFIG_DIR/config.example.yml" << 'EOF'
# Configuration NotionDev - Renommer en config.yml et compléter

notion:
  # Token d'intégration Notion (https://www.notion.so/my-integrations)
  token: "secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  
  # ID de votre database "Modules" 
  database_modules_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  
  # ID de votre database "Features"
  database_features_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

asana:
  # Personal Access Token Asana (https://app.asana.com/0/my-apps)
  access_token: "x/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  
  # GID de votre workspace Asana
  workspace_gid: "1234567890123456"
  
  # Votre User GID Asana
  user_gid: "1234567890123456"

  # OPTIONNEL: GID du portfolio pour filtrer les tickets (recommandé)
  # Si non défini, tous vos tickets seront affichés
  #portfolio_gid: "1234567890123456"

ai:
  context_max_length: 32000
  include_code_examples: true

git:
  default_branch: "main"
  header_comment_style: "auto"

logging:
  level: "INFO"
  file: "notion-dev.log"
EOF
        print_success "Fichier de config exemple créé dans $CONFIG_DIR/config.example.yml"
    else
        print_warning "Fichier config.example.yml existe déjà"
    fi
    
    print_warning "Renommez-le en config.yml et ajoutez vos tokens API"
else
    print_success "Fichier config.yml existe déjà - configuration préservée"
    print_warning "Si vous voulez un nouveau template: $CONFIG_DIR/config.example.yml"
fi

# Test de l'installation (sans config)
print_status "Test de l'installation..."

# D'abord tester si le module s'importe correctement
echo "Testing module import..."
if python -c "import notion_dev; print('✓ Module importé avec succès')" 2>/dev/null; then
    print_success "Module Python importé correctement"
    
    # Tester l'importation du CLI
    if python -c "from notion_dev.cli.main import cli; print('✓ CLI importé')" 2>/dev/null; then
        print_success "CLI importé correctement"
        
        # Tester la commande help
        if python -m notion_dev.cli.main --help > /dev/null 2>&1; then
            print_success "CLI accessible via python -m notion_dev.cli.main"
        elif notion-dev --help > /dev/null 2>&1; then
            print_success "CLI accessible via notion-dev"
        else
            print_warning "CLI installé mais commande pas accessible"
        fi
    else
        print_warning "CLI non importable, vérifiez main.py"
    fi
else
    print_error "Erreur d'importation du module Python"
    print_warning "Diagnostic détaillé:"
    python -c "import notion_dev" 2>&1 || true
    exit 1
fi

print_warning "⚠️  Configuration requise avant utilisation complète"

# Ajouter une commande de test de config
cat > "$INSTALL_DIR/test_config.sh" << 'EOF'
#!/bin/bash
# Script de test de la configuration NotionDev

echo "🧪 Test de la configuration NotionDev..."

# Activer l'environnement
source "$(dirname "$0")/venv/bin/activate"

# Test de base (sans config)
echo "1. Test installation de base..."
if python -m notion_dev.cli.main --help > /dev/null 2>&1; then
    echo "   ✅ CLI fonctionnel"
else
    echo "   ❌ Problème avec l'installation"
    exit 1
fi

# Test de la config
echo "2. Test de la configuration..."
if [ -f "$HOME/.notion-dev/config.yml" ]; then
    echo "   ✅ Fichier config.yml trouvé"
else
    echo "   ❌ Fichier config.yml manquant"
    echo "   💡 Copiez et éditez: cp ~/.notion-dev/config.example.yml ~/.notion-dev/config.yml"
    exit 1
fi

# Test détaillé des connexions
echo "3. Test des connexions API..."

# Test Asana séparément
echo "   3a. Test connexion Asana..."
ASANA_TEST=$(python -c "
try:
    from notion_dev.core.config import Config
    from notion_dev.core.asana_client import AsanaClient
    config = Config.load()
    client = AsanaClient(config.asana.access_token, config.asana.workspace_gid, config.asana.user_gid)
    tasks = client.get_my_tasks()
    print('ASANA_OK')
except Exception as e:
    print(f'ASANA_ERROR: {str(e)}')
" 2>&1)

if [[ $ASANA_TEST == *"ASANA_OK"* ]]; then
    echo "      ✅ Connexion Asana réussie"
    ASANA_SUCCESS=true
else
    echo "      ❌ Erreur connexion Asana:"
    echo "         $ASANA_TEST" | sed 's/ASANA_ERROR: //'
    ASANA_SUCCESS=false
fi

# Test Notion séparément
echo "   3b. Test connexion Notion..."
NOTION_TEST=$(python -c "
try:
    from notion_dev.core.config import Config
    from notion_dev.core.notion_client import NotionClient
    config = Config.load()
    client = NotionClient(config.notion.token, config.notion.database_modules_id, config.notion.database_features_id)
    # Test simple: chercher les features
    features = client.search_features()
    print('NOTION_OK')
except Exception as e:
    print(f'NOTION_ERROR: {str(e)}')
" 2>&1)

if [[ $NOTION_TEST == *"NOTION_OK"* ]]; then
    echo "      ✅ Connexion Notion réussie"
    NOTION_SUCCESS=true
else
    echo "      ❌ Erreur connexion Notion:"
    echo "         $NOTION_TEST" | sed 's/NOTION_ERROR: //'
    NOTION_SUCCESS=false
fi

# Test workflow complet
echo "4. Test workflow complet..."
if [ "$ASANA_SUCCESS" = true ] && [ "$NOTION_SUCCESS" = true ]; then
    echo "   ✅ Toutes les connexions OK"
    
    # Test d'un workflow simple
    WORKFLOW_TEST=$(python -c "
try:
    from notion_dev.core.config import Config
    from notion_dev.core.asana_client import AsanaClient
    config = Config.load()
    client = AsanaClient(config.asana.access_token, config.asana.workspace_gid, config.asana.user_gid)
    tasks = client.get_my_tasks()
    print(f'WORKFLOW_OK: {len(tasks)} tickets trouvés')
except Exception as e:
    print(f'WORKFLOW_ERROR: {str(e)}')
" 2>&1)
    
    if [[ $WORKFLOW_TEST == *"WORKFLOW_OK"* ]]; then
        echo "   🎉 Configuration complète et fonctionnelle !"
        echo "   📋 $WORKFLOW_TEST" | sed 's/WORKFLOW_OK: //'
        echo ""
        echo "🚀 Vous pouvez maintenant utiliser:"
        echo "   notion-dev tickets"
        echo "   notion-dev interactive"
    else
        echo "   ⚠️  APIs connectées mais workflow incomplet:"
        echo "      $WORKFLOW_TEST" | sed 's/WORKFLOW_ERROR: //'
    fi
else
    echo "   ❌ Connexions incomplètes"
    echo ""
    echo "🔧 Actions de dépannage:"
    
    if [ "$ASANA_SUCCESS" = false ]; then
        echo "   📋 Asana:"
        echo "      - Vérifiez le Personal Access Token"
        echo "      - Vérifiez workspace_gid et user_gid"
        echo "      - Testez sur: https://app.asana.com/api/1.0/users/me"
    fi
    
    if [ "$NOTION_SUCCESS" = false ]; then
        echo "   📝 Notion:"
        echo "      - Vérifiez le token d'intégration"
        echo "      - Vérifiez les IDs des databases"
        echo "      - L'intégration a-t-elle accès aux databases ?"
    fi
fi
EOF

chmod +x "$INSTALL_DIR/test_config.sh"

# Créer un script d'activation pour faciliter l'usage
cat > "$INSTALL_DIR/activate_notion_dev.sh" << EOF
#!/bin/bash
# Script d'activation de l'environnement NotionDev

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
source "\$SCRIPT_DIR/venv/bin/activate"

echo "🚀 Environnement NotionDev activé"
echo "Python path: \$(which python)"
echo "Utilisez 'python -m notion_dev.cli.main --help' pour commencer"
echo "Ou si l'alias fonctionne: 'notion-dev --help'"
echo "Pour désactiver: deactivate"
EOF

chmod +x "$INSTALL_DIR/activate_notion_dev.sh"

# Créer un alias global (optionnel)
read -p "Voulez-vous créer un alias global 'notion-dev' ? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SHELL_CONFIG=""
    
    # Détecter le shell
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_CONFIG="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_CONFIG="$HOME/.bash_profile"
    fi
    
    if [ -n "$SHELL_CONFIG" ]; then
        echo "" >> "$SHELL_CONFIG"
        echo "# NotionDev alias" >> "$SHELL_CONFIG"
        echo "alias notion-dev='source $INSTALL_DIR/venv/bin/activate && python -m notion_dev.cli.main'" >> "$SHELL_CONFIG"
        
        print_success "Alias ajouté à $SHELL_CONFIG"
        print_warning "Redémarrez votre terminal ou exécutez: source $SHELL_CONFIG"
    else
        print_warning "Shell non détecté, alias non créé"
    fi
fi

# Résumé final
echo ""
echo "=================================================="
print_success "🎉 Installation terminée avec succès !"
echo "=================================================="
echo ""
echo "📁 Installation dans: $INSTALL_DIR"
echo "⚙️  Configuration:     $CONFIG_DIR"
echo "🧪 Test complet:      $INSTALL_DIR/test_config.sh"
echo ""
echo "🚀 Prochaines étapes:"
if [ -f "$CONFIG_DIR/config.yml" ]; then
    echo "   1. Configuration: ✅ Déjà configurée"
    echo "      Si vous voulez modifier: nano $CONFIG_DIR/config.yml"
else
    echo "   1. Configurer vos tokens API:"
    echo "      cp $CONFIG_DIR/config.example.yml $CONFIG_DIR/config.yml"
    echo "      # Puis éditer config.yml avec vos tokens"
fi
echo ""
echo "   2. Activer l'environnement:"
echo "      source $INSTALL_DIR/activate_notion_dev.sh"
echo ""
echo "   3. Tester l'installation de base:"
echo "      python -m notion_dev.cli.main --help"
echo "      # ou si l'alias fonctionne: notion-dev --help"
echo ""
echo "   4. Tester la configuration complète:"
echo "      $INSTALL_DIR/test_config.sh"
echo ""
echo "📖 Documentation complète: README.md dans $INSTALL_DIR"
echo ""

# Proposer d'ouvrir la config
if [ ! -f "$CONFIG_DIR/config.yml" ]; then
    read -p "Voulez-vous ouvrir le fichier de configuration maintenant ? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$CONFIG_DIR/config.example.yml" "$CONFIG_DIR/config.yml"
        
        # Essayer d'ouvrir avec différents éditeurs
        if command -v code &> /dev/null; then
            code "$CONFIG_DIR/config.yml"
        elif command -v nano &> /dev/null; then
            nano "$CONFIG_DIR/config.yml"
        elif command -v vim &> /dev/null; then
            vim "$CONFIG_DIR/config.yml"
        else
            print_warning "Éditeur non trouvé. Ouvrez manuellement: $CONFIG_DIR/config.yml"
        fi
    fi
else
    print_success "Configuration existante préservée dans $CONFIG_DIR/config.yml"
fi

print_success "Installation NotionDev terminée ! 🚀"


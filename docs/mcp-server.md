# NotionDev MCP Server

Le serveur MCP (Model Context Protocol) de NotionDev permet à Claude Code d'interagir directement avec Notion et Asana pour gérer la documentation et les tickets de développement.

## Installation

### Prérequis

1. NotionDev doit être installé et configuré :
   ```bash
   pip install notion-dev
   ```

2. Vérifiez que la configuration existe :
   ```bash
   notion-dev info
   ```

### Ajouter le serveur MCP à Claude Code

```bash
# Méthode 1: Via la commande notion-dev-mcp
claude mcp add --transport stdio notiondev -- notion-dev-mcp

# Méthode 2: Via Python directement
claude mcp add --transport stdio notiondev -- python -m notion_dev.mcp_server.server
```

### Vérifier l'installation

Dans Claude Code, tapez `/mcp` pour voir la liste des serveurs MCP disponibles. `notiondev` devrait apparaître dans la liste.

## Fonctionnalités

### Tools (Outils)

| Tool | Description |
|------|-------------|
| `notiondev_check_installation` | Vérifie si NotionDev est installé et configuré |
| `notiondev_get_install_instructions` | Guide d'installation détaillé |
| `notiondev_list_tickets` | Liste les tickets Asana assignés |
| `notiondev_get_info` | Infos projet et ticket courant |
| `notiondev_work_on_ticket` | Démarre le travail sur un ticket |
| `notiondev_add_comment` | Ajoute un commentaire au ticket courant |
| `notiondev_mark_done` | Marque le ticket comme terminé |
| `notiondev_list_modules` | Liste tous les modules Notion |
| `notiondev_get_module` | Détails d'un module spécifique |
| `notiondev_list_features` | Liste les features (optionnel: par module) |
| `notiondev_get_feature` | Détails d'une feature spécifique |
| `notiondev_create_module` | Crée un nouveau module dans Notion |
| `notiondev_create_feature` | Crée une nouvelle feature dans Notion |
| `notiondev_update_module_content` | Met à jour la doc d'un module |
| `notiondev_update_feature_content` | Met à jour la doc d'une feature |

### Prompts (Modèles)

| Prompt | Description |
|--------|-------------|
| `/mcp__notiondev__notiondev_methodology` | Explication de la méthodologie specs-first |
| `/mcp__notiondev__notiondev_module_template` | Template de documentation module |
| `/mcp__notiondev__notiondev_feature_template` | Template de documentation feature |
| `/mcp__notiondev__notiondev_init_project` | Workflow d'initialisation de projet |

### Resources (Ressources)

| Resource | Description |
|----------|-------------|
| `@notiondev://config` | Configuration actuelle (sans tokens) |
| `@notiondev://current-task` | Ticket en cours de travail |
| `@notiondev://methodology` | Documentation de la méthodologie |

## Utilisation

### Lister les tickets

```
Utilisateur: Montre-moi mes tickets Asana
Claude: [Utilise notiondev_list_tickets]
```

### Travailler sur un ticket

```
Utilisateur: Je veux travailler sur le ticket 1234567890
Claude: [Utilise notiondev_work_on_ticket avec task_id="1234567890"]
```

### Créer un module

```
Utilisateur: Crée un nouveau module "Authentification" avec le préfixe AU
Claude: [Utilise notiondev_create_module]
```

### Initialiser la documentation d'un projet

```
Utilisateur: Aide-moi à documenter ce projet dans Notion
Claude: [Utilise le prompt notiondev_init_project puis guide l'utilisateur]
```

## Configuration Entreprise

### Déploiement pour une équipe

Pour déployer le serveur MCP à toute une équipe, ajoutez la configuration dans `.mcp.json` à la racine de vos projets :

```json
{
  "mcpServers": {
    "notiondev": {
      "type": "stdio",
      "command": "notion-dev-mcp",
      "env": {}
    }
  }
}
```

### Variables d'environnement

Le serveur MCP utilise la même configuration que le CLI (`~/.notion-dev/config.yml`). Aucune variable d'environnement supplémentaire n'est requise.

## Dépannage

### Le serveur ne démarre pas

1. Vérifiez que `notion-dev` est installé :
   ```bash
   notion-dev --version
   ```

2. Vérifiez la configuration :
   ```bash
   notion-dev info
   ```

3. Testez le serveur MCP directement :
   ```bash
   notion-dev-mcp
   # Devrait afficher des logs et attendre des commandes
   ```

### Les outils ne fonctionnent pas

1. Dans Claude Code, vérifiez que le serveur est connecté :
   ```
   /mcp
   ```

2. Vérifiez les logs :
   ```bash
   tail -f ~/.notion-dev/notion-dev.log
   ```

### Erreurs de permission Notion

Assurez-vous que votre intégration Notion a accès aux bases de données Modules et Features :
1. Ouvrez chaque base de données dans Notion
2. Cliquez sur "..." > "Connexions" > Ajoutez votre intégration

## Architecture

```
notion_dev/
├── mcp_server/
│   ├── __init__.py
│   └── server.py      # Serveur FastMCP avec tous les tools/prompts/resources
├── core/
│   ├── notion_client.py  # Client Notion (lecture + écriture batch)
│   ├── asana_client.py   # Client Asana
│   └── ...
└── cli/
    └── main.py           # CLI classique
```

Le serveur MCP réutilise les mêmes clients que le CLI, garantissant un comportement cohérent.

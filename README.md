# NotionDev

> **Intégration Notion ↔ Asana ↔ Git pour développeurs**  
> Accélérez votre développement avec un contexte IA chargé automatiquement depuis vos spécifications Notion

NotionDev est adapté aux grands projets qui nécessitent de concentrer les agents IA sur un context présenté de manière très précise pour éviter les régressions sur le code.
Nous implémentons un workflow avec un context switching automatique, qui s'appuie sur vos spécifications.
Pour cela nous supposons que votre application est organisée en modules, et vos modules en features. Nous supposons aussi que vos modules et vos features sont documentées dans deux bases Notion.

NotionDev permet aux développeurs de charger automatiquement le contexte complet de leurs features depuis Notion directement dans les rules de leur IDE (Cursor), tout en synchronisant avec les tickets Asana qui leur sont assignés.
Ils peuvent alors commenter les tickets Asana, taguer leur code avec les features implémentées, et réassigner un ticket à la personne qui l'a créée lorsque le travail est terminé.

NotionDev fonctionne dans un environnement multi-projets : vous pouvez avoir en local plusieurs projets git, vous pouvez travailler des features distinctes dans chaque projet.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Fonctionnalités

- 🎯 **Workflow intégré** : Ticket Asana +  Documentation Notion → Contexte IA → Code
- 🤖 **IA Context automatique** : Export direct vers Cursor avec specs complètes
- 🔄 **Multi-projets** : Détection automatique du projet courant
- 📋 **Traçabilité** : Headers automatiques dans le code pour lier fonctionnel ↔ technique
- 🚀 **Zero config par projet** : Une seule configuration globale pour tous vos projets

## 🎯 Cas d'usage

**Avant NotionDev :**
```bash
# Workflow manuel et dispersé
1. Ouvrir ticket Asana
2. Chercher la documentation dans Notion  
3. Copier-coller des specs dans Cursor
4. Coder sans contexte complet
5. Le code ne référence pas directement les spécifications implémentées
```

**Avec NotionDev :**
```bash
# Workflow automatisé et intégré
notion-dev work TASK-123456789
# → Charge automatiquement tout le contexte dans Cursor
# → Prêt à coder avec l'IA 
# Le code généré mentionne les features implémentées
```

## 📋 Prérequis

- **Python 3.9+**
- **macOS**
- **Accès APIs** : Notion + Asana
- **Structure Notion** : Databases "Modules" et "Features" avec codes features

### Structure Notion requise

Pour fonctionner, votre workspace Notion doit contenir 2 databases avec les attributs ci-dessous (attention à la casse) :

**Database "Modules" :**
- `name` (Title) : Nom du module
- `description` (Text) : Description courte  
- `status` (Select) : draft, review, validated, obsolete
- `application` (Select) : service, backend, frontend
- `code_prefix` (Text) : Préfixe des codes features (AU, DA, API...)

**Database "Features" :**
- `code` (Text) : Code unique (AU01, DA02...)
- `name` (Title) : Nom de la feature
- `status` (Select) : draft, review, validated, obsolete
- `module` (Relation) : Lien vers le module parent
- `plan` (Multi-select) : Plans de souscription  
- `user_rights` (Multi-select) : Droits d'accès

## 🚀 Installation

### Installation automatique

```bash
# 1. Cloner le repository
git clone https://github.com/votre-org/notion-dev.git
cd notion-dev

# 2. Lancer l'installation
chmod +x install_notion_dev.sh
./install_notion_dev.sh
```

Le script d'installation va :
- ✅ Vérifier Python 3.9+
- ✅ Créer un environnement virtuel
- ✅ Installer toutes les dépendances
- ✅ Configurer l'alias global `notion-dev`
- ✅ Créer le template de configuration

### Configuration

#### 1. Récupérer les tokens API

**🔑 Token Notion :**
1. Aller sur https://www.notion.so/my-integrations
2. Créer une nouvelle intégration "NotionDev"
3. Copier le token (commence par `secret_`)
4. Récupérer les ID des databases pour les modules et les features
   URL : `notion.so/workspace/[DATABASE_ID]?v=...`

**🔑 Token Asana :**
1. Aller sur https://app.asana.com/0/my-apps
2. Créer un "Personal Access Token"
3. Copier le token généré
4. Récupérer l'ID de votre workspace
5. récupérer l'ID de votre compte utilisateur

#### 2. Configurer le fichier config.yml

```bash
# Copier le template
cp ~/.notion-dev/config.example.yml ~/.notion-dev/config.yml

# Éditer avec vos tokens
nano ~/.notion-dev/config.yml
```

```yaml
notion:
  token: "secret_VOTRE_TOKEN_NOTION"
  database_modules_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  
  database_features_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

asana:
  access_token: "x/VOTRE_TOKEN_ASANA"
  workspace_gid: "1234567890123456"
  user_gid: "1234567890123456"
```

#### 3. Tester l'installation

```bash
# Test complet de la configuration
~/notion-dev-install/test_config.sh

# Premier test
notion-dev tickets
```

## 📖 Utilisation

### Commandes principales

```bash
# Voir les infos du projet courant
notion-dev info

# Lister vos tickets Asana assignés  
notion-dev tickets

# Travailler sur un ticket spécifique
notion-dev work TASK-123456789

# Récupérer le contexte pour une feature
# autre que celle inscrite dans le ticket Asana
notion-dev context --feature AU01

# Enregistrer un commentaire au ticket dans Asana
notion-dev comment "Ceci est un commentaire"

# Marquer le travail terminé
# L'action assigne le ticket à la personne qui l'a créé
notion-dev done

# Mode interactif
notion-dev interactive
```

### Workflow développeur type

Pour comprendre l'esprit de NotionDev, voici un exemple de workflow de travail.
Dans cet exemple on considère que la documentation a été validée dans Notion (Definition of Ready), et que les tickets Asana ont été inscrits au sprint courant, assignés aux développeurs.
Nous nous mettons ici dans la peau d'un développeur.

#### 🌅 Matin - Choisir son ticket

```bash
cd ~/projets/mon-saas-frontend
notion-dev tickets
```

```
                    Mes Tickets Asana                    
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ ID      ┃ Nom                             ┃ Feature     ┃ St atut      ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ 23456789│ Implémenter SSO Google          │ AU02        │ 🔄 En c ours │
│ 34567890│ Dashboard analytics             │ DA01        │ 🔄 En c ours │
└─────────┴────────────────────────────────┴─────────────┴─────────────┘
```

#### 🎯 Démarrer le travail

```bash
notion-dev work 23456789
```

```
📋 Ticket Asana
AU02 - Implémenter SSO Google

ID: 1234567890123456
Feature Code: AU02
Status: 🔄 En cours
Projet: mon-saas-frontend

🎯 Feature
AU02 - SSO Google Login

Module: User Authentication
Status: validated
Plans: premium
User Rights: standard, admin

Exporter le contexte vers Cursor? [Y/n]: y
✅ Contexte exporté vers /Users/dev/projets/mon-saas-frontend/.cursor/
💡 Vous pouvez maintenant ouvrir Cursor et commencer à coder!
```

#### 💻 Développer avec Cursor

```bash
# Ouvrir Cursor avec le contexte chargé
cursor .
```

Le contexte IA contient automatiquement :
- ✅ Spécifications complètes de la feature AU02
- ✅ Documentation du module User Authentication  
- ✅ Standards de code avec headers obligatoires
- ✅ Instructions pour l'IA adaptées au projet

#### 🔄 Changer de projet

```bash
# Passer à un autre projet - détection automatique
cd ~/projets/mon-saas-api
notion-dev info
```

```
📊 Projet: mon-saas-api
Nom: mon-saas-api
Chemin: /Users/dev/projets/mon-saas-api
Cache: /Users/dev/projets/mon-saas-api/.notion-dev
Git Repository: ✅ Oui
```

### Headers de traçabilité

Dans le contexte chargé dans le dossier /.cursor, NotionDev ajoute des instructions pour que l'agent IA insère automatiquement un header dans chaque fichier du projet avec le code de la feature.
L'objectif est de vérifier la couverture fonctionnelle du code, et d'éviter les regression puisque l'agent IA a pour intstruction de ne pas modifier le code correspondant à une feature autre que celle en cours de travail.

```typescript
/**
 * NOTION FEATURES: AU02
 * MODULES: User Authentication
 * DESCRIPTION: Service d'authentification Google OAuth
 * LAST_SYNC: 2025-01-15
 */
export class GoogleAuthService {
  // Implementation...
}
```

## 🏗️ Architecture

### Multi-projets automatique

NotionDev détecte automatiquement le projet depuis le dossier courant :

```bash
~/projets/
├── saas-frontend/          # notion-dev → Context "saas-frontend"
│   └── .notion-dev/        # Cache isolé
├── saas-api/              # notion-dev → Context "saas-api"  
│   └── .notion-dev/        # Cache isolé
└── saas-admin/            # notion-dev → Context "saas-admin"
    └── .notion-dev/        # Cache isolé
```

## ⚙️ Configuration avancée

### Optimisation pour votre IA

```yaml
ai:
  # Pour Claude Opus/Sonnet (recommandé)
  context_max_length: 100000
  include_code_examples: true
  
  # Pour GPT-3.5 (plus limité)
  context_max_length: 32000
  include_code_examples: false
```

### Alias shell personnalisé

```bash
# Dans ~/.zshrc ou ~/.bash_profile
alias nd="notion-dev"
alias ndt="notion-dev tickets"
alias ndw="notion-dev work"
alias ndi="notion-dev info"
```

## 🔧 Dépannage

### Erreurs courantes

**❌ "Configuration invalide"**
```bash
# Vérifier les tokens
notion-dev info
# Retester la config
~/notion-dev-install/test_config.sh
```

### Logs de debug

```bash
# Voir les logs détaillés
tail -f ~/.notion-dev/notion-dev.log

# Debug avec niveau verbose
export NOTION_DEV_LOG_LEVEL=DEBUG
notion-dev tickets
```

## 🤝 Contribution

### Développement local

```bash
# Cloner et installer en mode développement
git clone https://github.com/votre-org/notion-dev.git
cd notion-dev
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Structure du projet

```
notion-dev/
├── notion_dev/
│   ├── core/              # Logique métier
│   │   ├── config.py      # Configuration multi-projets
│   │   ├── asana_client.py # Client Asana API
│   │   ├── notion_client.py # Client Notion API
│   │   └── context_builder.py # Générateur contexte IA
│   ├── cli/
│   │   └── main.py        # Interface CLI
│   └── models/            # Modèles de données
├── install_notion_dev.sh  # Script d'installation
└── README.md
```

## 📝 Changelog

### v1.0.0 (2025-01-26)
- ✅ Version initiale
- ✅ Support multi-projets automatique
- ✅ Intégration Notion + Asana + Cursor
- ✅ Headers de traçabilité automatiques
- ✅ Client Asana API 5.2.0 compatible

## 📄 License

MIT License - voir [LICENSE](LICENSE) pour plus de détails.

## 💬 Support

- **Issues** : [GitHub Issues](https://github.com/votre-org/notion-dev/issues)
- **Documentation** : [Wiki](https://github.com/votre-org/notion-dev/wiki)
- **Discussions** : [GitHub Discussions](https://github.com/votre-org/notion-dev/discussions)

---

**Développé avec ❤️ pour accélérer le développement avec l'IA**

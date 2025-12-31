#!/bin/bash
# NOTION FEATURES: ND03
# MODULES: NotionDev
# DESCRIPTION: Deployment script for NotionDev MCP Server on fly.io
# LAST_SYNC: 2025-12-31

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
STAGING_APP="notiondev-staging"
PROD_APP="notiondev-prod"
REGION="cdg"  # Paris

usage() {
    echo "Usage: $0 <command> [environment]"
    echo ""
    echo "Commands:"
    echo "  create <staging|prod>   Create a new fly.io app"
    echo "  secrets <staging|prod>  Set secrets interactively"
    echo "  deploy <staging|prod>   Deploy to fly.io"
    echo "  logs <staging|prod>     View logs"
    echo "  status <staging|prod>   Check app status"
    echo "  ssh <staging|prod>      SSH into the app"
    echo "  destroy <staging|prod>  Destroy the app (careful!)"
    echo "  github-token            Generate fly.io token for GitHub Actions"
    echo "  setup-branches          Create staging and production branches"
    echo ""
    echo "Examples:"
    echo "  $0 create staging       # Create staging app"
    echo "  $0 secrets staging      # Configure secrets"
    echo "  $0 deploy staging       # Deploy to staging"
    echo "  $0 deploy prod          # Deploy to production"
    echo "  $0 github-token         # Get token for GitHub Actions"
    echo "  $0 setup-branches       # Create git branches for CI/CD"
    exit 1
}

get_app_name() {
    local env=$1
    if [ "$env" == "staging" ]; then
        echo "$STAGING_APP"
    elif [ "$env" == "prod" ]; then
        echo "$PROD_APP"
    else
        echo -e "${RED}Invalid environment: $env${NC}"
        exit 1
    fi
}

get_config_file() {
    local env=$1
    if [ "$env" == "staging" ]; then
        echo "fly.toml"
    elif [ "$env" == "prod" ]; then
        echo "fly.prod.toml"
    fi
}

check_fly_cli() {
    if ! command -v fly &> /dev/null; then
        echo -e "${RED}fly CLI is not installed.${NC}"
        echo "Install it with: curl -L https://fly.io/install.sh | sh"
        exit 1
    fi
}

cmd_create() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${YELLOW}Creating fly.io app: $app${NC}"

    fly apps create "$app" --org personal || {
        echo -e "${YELLOW}App may already exist, continuing...${NC}"
    }

    # Create volume for repo cache
    local volume_name="notiondev_repos"
    if [ "$env" == "prod" ]; then
        volume_name="notiondev_repos_prod"
    fi

    echo -e "${YELLOW}Creating volume: $volume_name${NC}"
    fly volumes create "$volume_name" \
        --app "$app" \
        --region "$REGION" \
        --size 1 \
        --yes || {
        echo -e "${YELLOW}Volume may already exist, continuing...${NC}"
    }

    echo -e "${GREEN}App $app created successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure secrets: $0 secrets $env"
    echo "  2. Deploy: $0 deploy $env"
}

cmd_secrets() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${YELLOW}Setting secrets for: $app${NC}"
    echo ""
    echo "You'll need the following values:"
    echo "  - GOOGLE_CLIENT_ID (from Google Cloud Console)"
    echo "  - GOOGLE_CLIENT_SECRET (from Google Cloud Console)"
    echo "  - JWT_SECRET (generate with: openssl rand -hex 32)"
    echo "  - ALLOWED_EMAIL_DOMAIN (e.g., grand-shooting.com)"
    echo "  - SERVICE_NOTION_TOKEN (from Notion integration)"
    echo "  - SERVICE_ASANA_TOKEN (Asana PAT)"
    echo "  - GITHUB_TOKEN (optional, for private repos)"
    echo ""

    read -p "GOOGLE_CLIENT_ID: " google_client_id
    read -p "GOOGLE_CLIENT_SECRET: " google_client_secret
    read -p "JWT_SECRET (or press Enter to generate): " jwt_secret
    if [ -z "$jwt_secret" ]; then
        jwt_secret=$(openssl rand -hex 32)
        echo "Generated JWT_SECRET: $jwt_secret"
    fi
    read -p "ALLOWED_EMAIL_DOMAIN: " allowed_domain
    read -p "SERVICE_NOTION_TOKEN: " notion_token
    read -p "SERVICE_ASANA_TOKEN: " asana_token
    read -p "GITHUB_TOKEN (optional, press Enter to skip): " github_token

    # Set MCP_BASE_URL based on environment
    local base_url
    if [ "$env" == "staging" ]; then
        base_url="https://notiondev-staging.grand-shooting.com"
    else
        base_url="https://notiondev.grand-shooting.com"
    fi

    echo ""
    echo -e "${YELLOW}Setting secrets...${NC}"

    fly secrets set \
        --app "$app" \
        GOOGLE_CLIENT_ID="$google_client_id" \
        GOOGLE_CLIENT_SECRET="$google_client_secret" \
        JWT_SECRET="$jwt_secret" \
        ALLOWED_EMAIL_DOMAIN="$allowed_domain" \
        SERVICE_NOTION_TOKEN="$notion_token" \
        SERVICE_ASANA_TOKEN="$asana_token" \
        MCP_BASE_URL="$base_url"

    if [ -n "$github_token" ]; then
        fly secrets set --app "$app" GITHUB_TOKEN="$github_token"
    fi

    echo -e "${GREEN}Secrets configured successfully!${NC}"
}

cmd_deploy() {
    local env=$1
    local app=$(get_app_name "$env")
    local config=$(get_config_file "$env")

    echo -e "${YELLOW}Deploying to: $app${NC}"

    # Update app name in config if needed
    if [ "$env" == "staging" ]; then
        fly deploy --config fly.toml --app "$app"
    else
        fly deploy --config fly.prod.toml --app "$app"
    fi

    echo -e "${GREEN}Deployed successfully to $app!${NC}"
    echo ""
    echo "App URL: https://$app.fly.dev"
    if [ "$env" == "staging" ]; then
        echo "Custom domain: https://notiondev-staging.grand-shooting.com"
    else
        echo "Custom domain: https://notiondev.grand-shooting.com"
    fi
}

cmd_logs() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${YELLOW}Viewing logs for: $app${NC}"
    fly logs --app "$app"
}

cmd_status() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${YELLOW}Status for: $app${NC}"
    fly status --app "$app"
}

cmd_ssh() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${YELLOW}SSH into: $app${NC}"
    fly ssh console --app "$app"
}

cmd_destroy() {
    local env=$1
    local app=$(get_app_name "$env")

    echo -e "${RED}WARNING: This will destroy the app $app and all its data!${NC}"
    read -p "Type the app name to confirm: " confirm

    if [ "$confirm" == "$app" ]; then
        fly apps destroy "$app" --yes
        echo -e "${GREEN}App $app destroyed.${NC}"
    else
        echo -e "${YELLOW}Destruction cancelled.${NC}"
    fi
}

cmd_github_token() {
    echo -e "${YELLOW}Generating fly.io API token for GitHub Actions...${NC}"
    echo ""
    echo "This will create a deploy token. Copy it and add it to GitHub:"
    echo "  Repository → Settings → Secrets and variables → Actions → New repository secret"
    echo "  Name: FLY_API_TOKEN"
    echo ""

    fly tokens create deploy -o GRAFMAKER -x 999999h

    echo ""
    echo -e "${GREEN}Token created!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Copy the token above"
    echo "  2. Go to your GitHub repository settings"
    echo "  3. Add it as secret 'FLY_API_TOKEN'"
}

cmd_setup_branches() {
    echo -e "${YELLOW}Setting up staging and production branches...${NC}"

    # Get current branch
    local current_branch=$(git branch --show-current)

    # Create staging branch if it doesn't exist
    if git show-ref --verify --quiet refs/heads/staging; then
        echo "Branch 'staging' already exists"
    else
        echo "Creating 'staging' branch from main..."
        git branch staging main
        echo -e "${GREEN}Branch 'staging' created${NC}"
    fi

    # Create production branch if it doesn't exist
    if git show-ref --verify --quiet refs/heads/production; then
        echo "Branch 'production' already exists"
    else
        echo "Creating 'production' branch from main..."
        git branch production main
        echo -e "${GREEN}Branch 'production' created${NC}"
    fi

    echo ""
    echo -e "${GREEN}Branches created successfully!${NC}"
    echo ""
    echo "Workflow:"
    echo "  1. Develop on 'main' or feature branches"
    echo "  2. Merge to 'staging' → auto-deploys to staging"
    echo "  3. Merge to 'production' → auto-deploys to production"
    echo ""
    echo "To push branches to remote:"
    echo "  git push origin staging"
    echo "  git push origin production"
}

# Main
check_fly_cli

COMMAND=$1
ENVIRONMENT=$2

# Commands that don't need environment parameter
case $COMMAND in
    github-token)
        cmd_github_token
        exit 0
        ;;
    setup-branches)
        cmd_setup_branches
        exit 0
        ;;
esac

# Commands that need environment parameter
if [ $# -lt 2 ]; then
    usage
fi

case $COMMAND in
    create)
        cmd_create "$ENVIRONMENT"
        ;;
    secrets)
        cmd_secrets "$ENVIRONMENT"
        ;;
    deploy)
        cmd_deploy "$ENVIRONMENT"
        ;;
    logs)
        cmd_logs "$ENVIRONMENT"
        ;;
    status)
        cmd_status "$ENVIRONMENT"
        ;;
    ssh)
        cmd_ssh "$ENVIRONMENT"
        ;;
    destroy)
        cmd_destroy "$ENVIRONMENT"
        ;;
    *)
        usage
        ;;
esac

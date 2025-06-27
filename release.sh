#!/bin/bash
# release.sh - Script to automate version bumping and tagging for NotionDev

if [ -z "$1" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.3"
    exit 1
fi

VERSION=$1

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 1.0.3)"
    exit 1
fi

echo "🔄 Updating version to $VERSION..."

# Update version in all files
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" notion_dev/__init__.py
sed -i '' "s/version=\".*\"/version=\"$VERSION\"/" setup.py
sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# Show changes
echo "📝 Version changes:"
git diff notion_dev/__init__.py setup.py pyproject.toml

# Ask for confirmation
read -p "Continue with commit and tag? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted"
    exit 1
fi

# Commit and tag
git add notion_dev/__init__.py setup.py pyproject.toml
git commit -m "chore: bump version to $VERSION"
git tag -a "v$VERSION" -m "Release version $VERSION"

# Push
echo "🚀 Pushing to GitHub..."
git push origin main
git push origin "v$VERSION"

echo "✅ Version $VERSION tagged and pushed!"
echo "📦 Now create a release on GitHub to trigger PyPI publishing:"
echo "   https://github.com/phumblot-gs/NotionDev/releases/new?tag=v$VERSION"
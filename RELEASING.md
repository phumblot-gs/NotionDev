# Release Process for NotionDev

This guide describes how to release a new version of NotionDev.

## Prerequisites

1. You must have a PyPI account and API token
2. The `PYPI_API_TOKEN` secret must be configured in GitHub Actions
3. You must have permissions to create releases on GitHub

## Release Steps

### 1. Update Version

Update the version in two places:
```python
# notion_dev/__init__.py
__version__ = "1.1.0"  # New version

# setup.py
version='1.1.0',  # Same version
```

### 2. Update Changelog

Add a new section to README.md:
```markdown
### v1.1.0 (2025-01-27)
- ✅ New feature X
- 🐛 Fixed bug Y
- 📚 Improved documentation
```

### 3. Commit and Push

```bash
git add .
git commit -m "Bump version to 1.1.0"
git push origin main
```

### 4. Create GitHub Release

1. Go to https://github.com/phumblot-gs/NotionDev/releases
2. Click "Draft a new release"
3. Choose a tag: `v1.1.0` (create new tag on publish)
4. Release title: `NotionDev v1.1.0`
5. Describe the changes (can copy from changelog)
6. Click "Publish release"

### 5. Verify

The GitHub Action will automatically:
1. Build the package
2. Check the package quality
3. Verify version matches tag
4. Upload to PyPI

Check the Actions tab to monitor progress.

### 6. Post-Release

After successful release:
```bash
# Verify on PyPI
pip install --upgrade notion-dev
notion-dev --version

# Should show the new version
```

## Version Numbering

We follow semantic versioning:
- **Major** (1.0.0 → 2.0.0): Breaking changes
- **Minor** (1.0.0 → 1.1.0): New features, backward compatible
- **Patch** (1.0.0 → 1.0.1): Bug fixes only

## Troubleshooting

### Build Failed
- Check GitHub Actions logs
- Ensure version numbers match everywhere
- Run `python -m build` locally to test

### PyPI Upload Failed
- Verify `PYPI_API_TOKEN` is set correctly
- Check token hasn't expired
- Ensure package name isn't taken

### Version Mismatch
- Tag must be `v1.1.0` format
- Version in code must be `1.1.0` (without v)
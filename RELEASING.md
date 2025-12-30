# Releasing NotionDev

This document describes the process for releasing new versions of NotionDev to PyPI.

## 📋 Pre-release Checklist

Before creating a release, ensure:

- [ ] All tests pass locally: `pytest`
- [ ] All changes are committed and pushed to main
- [ ] README.md is up to date with new features
- [ ] CHANGELOG.md is updated (if maintained)
- [ ] No hardcoded test values or debug prints in code

## 🚀 Quick Release (Recommended)

Use the `release.sh` script to automate the entire process:

```bash
./release.sh 1.4.0
```

This script will:
1. Validate the version format (X.Y.Z)
2. Update version in all 3 files (`__init__.py`, `setup.py`, `pyproject.toml`)
3. Show the diff for review
4. Commit the changes
5. Create an annotated git tag
6. Push to GitHub (main branch + tag)

After the script completes, create a GitHub release to trigger PyPI publishing.

---

## 🔢 Manual Version Update Process

If you prefer to update manually, NotionDev uses semantic versioning (MAJOR.MINOR.PATCH). Version numbers must be synchronized in **THREE** locations:

### 1. Update Version Numbers

#### File 1: `notion_dev/__init__.py`
```python
__version__ = "1.4.0"  # Update this line
```

#### File 2: `setup.py`
```python
setup(
    name="notion-dev",
    version="1.4.0",  # Update this line
    ...
)
```

#### File 3: `pyproject.toml`
```toml
[project]
name = "notion-dev"
version = "1.4.0"  # Update this line
```

### 2. Commit Version Changes

```bash
git add notion_dev/__init__.py setup.py pyproject.toml
git commit -m "chore: bump version to 1.4.0"
git push origin main
```

### 3. Create Git Tag

```bash
git tag -a v1.4.0 -m "Release version 1.4.0"
git push origin v1.4.0
```

## 🏷️ Creating a GitHub Release

1. Go to https://github.com/phumblot-gs/NotionDev/releases
2. Click "Create a new release"
3. Select the tag you just created (e.g., v1.4.0)
4. Fill in release details:
   - **Release title**: e.g., v1.4.0
   - **Description**: List main changes, fixes, and new features
5. Click "Publish release"

### 3. Automated PyPI Publishing

Once the release is published, GitHub Actions will automatically:
1. Build the package
2. Run tests
3. Publish to PyPI

Monitor the workflow at: https://github.com/phumblot-gs/NotionDev/actions

## 🚨 Troubleshooting

### Version Mismatch Error

If you see "Version mismatch: package version X != tag Y":
- Ensure all three version files are synchronized
- Tag name must match version (e.g., v1.0.3 tag for version 1.0.3)

### Package Already Exists on PyPI

If you see "File already exists" error:
- You cannot reuse version numbers on PyPI
- Increment the version number and try again
- Delete and recreate the tag if needed

### Workflow Uses Old Code

GitHub Actions uses the workflow from the tagged commit. If you need to update the workflow:

```bash
# Delete the tag
git tag -d v1.0.3
git push origin :refs/tags/v1.0.3

# Make workflow changes, commit, push

# Recreate the tag
git tag -a v1.0.3 -m "Release version 1.0.3"
git push origin v1.0.3
```

## ⚠️ Important Notes

1. **Version Synchronization**: Always ensure version numbers are identical in all three files
2. **No Version Reuse**: Once published to PyPI, a version number cannot be reused
3. **Test First**: Always test the release process with a pre-release version if unsure
4. **Tag Format**: Tags must be formatted as `vX.Y.Z` (with 'v' prefix)
5. **Automated Publishing**: PyPI publishing only happens when creating a GitHub release, not just pushing tags

## 🔐 PyPI Token

The PyPI API token is stored as a GitHub secret (`PYPI_API_TOKEN`). If you need to update it:
1. Generate a new token at https://pypi.org/manage/account/token/
2. Update the secret at: Settings → Secrets and variables → Actions
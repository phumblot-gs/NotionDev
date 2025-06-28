# Installation Instructions

## Copy Files to Your Extension Directory

Run this command to copy all files to your extension directory:

```bash
cp -r /Users/phf/notion_dev-project/extension-files/* /Users/phf/notion-dev-cursor-extension/
```

## Next Steps

1. Navigate to your extension directory:
   ```bash
   cd /Users/phf/notion-dev-cursor-extension
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Compile the TypeScript:
   ```bash
   npm run compile
   ```

4. Test the extension:
   - Open the extension folder in VS Code/Cursor
   - Press F5 to launch a new Extension Development Host window
   - Test the NotionDev commands and views

5. Package the extension (optional):
   ```bash
   npm install -g @vscode/vsce
   vsce package
   ```

## Important Notes

- The extension requires the NotionDev CLI to be installed (`pip install notion-dev`)
- Make sure to configure your API tokens when prompted
- The extension will create a `.cursorrules` file in your workspace when you work on a task

## JSON Support

The extension uses JSON output from NotionDev CLI commands:
- `notion-dev tickets --json` - Returns list of tasks in JSON format
- `notion-dev info --json` - Returns current project and task info in JSON format

These features are available in NotionDev v1.0.3 and later. Make sure you have the latest version:
```bash
pip install --upgrade notion-dev
```
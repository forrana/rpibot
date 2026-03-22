# Git Hooks

This directory contains Git hooks for the project.

## Available Hooks

### pre-commit
- **Purpose**: Automatically trim trailing whitespace and spaces on empty lines
- **Files affected**: `.py`, `.js`, `.css`, `.html`
- **Behavior**: Runs automatically before each commit

## How It Works

1. **Trigger**: Runs when you execute `git commit`
2. **Action**: 
   - Identifies staged files with relevant extensions
   - Trims trailing whitespace from all lines
   - Re-stages the cleaned files
3. **Result**: Clean code with no trailing whitespace

## Installation

The hooks are already set up. No additional installation needed.

## Customization

To modify the pre-commit hook:
1. Edit `.git/hooks/pre-commit`
2. Make it executable: `chmod +x .git/hooks/pre-commit`

## Bypassing Hooks

If you need to bypass hooks temporarily:
```bash
git commit --no-verify -m "Your commit message"
```

## Adding New Hooks

Create executable scripts in `.git/hooks/` with the appropriate names:
- `pre-push` - runs before push
- `commit-msg` - checks commit messages
- etc.

## Notes

- Hooks are local to each repository
- They don't transfer with `git clone` (need to be set up manually)
- Hooks must be executable to work
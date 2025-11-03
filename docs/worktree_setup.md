# Worktree Configuration for Cursor Agents

This repo includes automatic symlink setup for Cursor Agent worktrees to ensure they have access to shared resources like `secrets.toml` and database files.

## What Gets Symlinked

When Cursor creates a worktree for an agent, the following files are automatically symlinked from the project root:

- `.streamlit/secrets.toml` - Streamlit secrets configuration
- All `*.db*` files - Database files and their auxiliary files (`.db-shm`, `.db-wal`, `.db-info`, etc.)

## Automatic Setup

A Git `post-checkout` hook is configured to automatically run when worktrees are created. However, if automatic setup doesn't work for some reason, you can manually run:

```bash
./scripts/setup_worktree_symlinks.sh /path/to/worktree
```

Or from within a worktree directory:
```bash
cd /path/to/worktree
../scripts/setup_worktree_symlinks.sh .
```

## Manual Setup for Existing Worktrees

To set up symlinks for all existing worktrees:

```bash
# List all worktrees
git worktree list

# For each worktree, run:
./scripts/setup_worktree_symlinks.sh /path/to/worktree
```

Or use this one-liner to set up all `.cursor/worktrees`:
```bash
for wt in ~/.cursor/worktrees/wcmkts_north/*/; do ./scripts/setup_worktree_symlinks.sh "$wt"; done
```

## How It Works

1. **Setup Script** (`scripts/setup_worktree_symlinks.sh`):
   - Creates `.streamlit` directory if needed
   - Creates symlinks for `secrets.toml`
   - Finds all `*.db*` files in project root and creates symlinks

2. **Git Hook** (`.git/hooks/post-checkout`):
   - Automatically detects when checking out into a `.cursor/worktrees` directory
   - Runs the setup script automatically

## Troubleshooting

- **Symlinks not created automatically**: Run the setup script manually
- **Database files not found**: Ensure database files exist in project root
- **Permission denied**: Ensure the script is executable: `chmod +x scripts/setup_worktree_symlinks.sh`

## Notes

- Symlinks point to files in the project root, so all worktrees share the same databases and secrets
- Database auxiliary files (`.db-shm`, `.db-wal`) are created dynamically by SQLite and will work once SQLite creates them
- The symlinks are not tracked by Git (as per `.gitignore`)


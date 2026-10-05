# Git repository backups

A mirror clone on an encrypted USB disk preserves branches and tags when the hosting service is unavailable. Once a week, fetch every remote and verify that a fresh clone can be restored from the disk without internet access. Uncommitted working files need a separate copy; a remote repository alone is not a complete backup.

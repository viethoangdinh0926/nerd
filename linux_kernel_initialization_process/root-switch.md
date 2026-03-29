# Root Switch

## Summary
- Transitions the system from the temporary initramfs root filesystem to the real root filesystem
- Uses mechanisms like `switch_root` or `pivot_root` to replace the current root mount
- Moves or unmounts the initramfs environment after the real root is ready
- Updates the process root (`/`) so all subsequent operations use the new filesystem
- Ensures continuity of the running system while changing the root filesystem
- Prepares the environment for executing the real init system from the new root
- Marks the final step before full user-space startup on the actual root filesystem

---

## Relationships
- performs -> [1] switch_root
- performs -> [2] pivot_root

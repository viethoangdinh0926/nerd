# Real Init System

## Type
concept

## Domain
systems

## Summary
- Represents the start of the real user-space init system after the kernel hands off control
- Executes the main init program (e.g., `/sbin/init`) as PID 1
- Commonly launches systemd as the modern init system
- Takes over full system initialization from the kernel and initramfs
- Starts essential services, daemons, and background processes
- Mounts and manages filesystems, devices, and system resources
- Establishes system state (targets/runlevels) and service dependencies
- Transitions the system into a fully operational multi-user environment

---

## Relationships
- executes -> [1] /sbin/init
- executes -> [2] systemd

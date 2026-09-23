"""PyInstaller entry point - imports smartcopy as a real package so its
internal relative imports resolve correctly, rather than pointing
PyInstaller directly at a file inside the package (which breaks them)."""

from smartcopy.cli import main

if __name__ == "__main__":
    main()

# Prompting

A personal collection of prompts, coding guidelines, and utilities designed primarily for Python-based codebases and AI-assisted code editing.

## Overview

This repository contains:

- **Rules**: Comprehensive rules for Python project architecture, testing, and code style.
- **Boundary Mocking Utilities**: Centralized testing infrastructure for mocking external system boundaries in a consistent way.

## Key Components

### PYTHON_RULES.md
Detailed architectural and development guidelines:
- Hexagonal architecture principles ("functional core, imperative shell").
- Strict separation between data and functions.
- Test-first development approach with boundary mocking.
- Modern Python typing conventions.
- Functional programming style guidelines.

### boundaries.py
Comprehensive boundary mocking system for testing:
- HTTP requests and responses.
- File system operations.
- Environment variables.
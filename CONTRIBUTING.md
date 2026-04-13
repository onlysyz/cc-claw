# Contributing to CC-Claw

Thank you for your interest in contributing to CC-Claw!

## Quick Start

```bash
# Fork and clone
git clone https://github.com/your-fork/cc-claw.git
cd cc-claw

# Install in dev mode
pip install -e ".[dev]"

# Create a branch
git checkout -b feature/your-feature

# Make changes and test
pytest tests/

# Commit and push
git commit -m "feat: add new feature"
git push origin feature/your-feature

# Open a PR
```

## Development Setup

### Requirements

- Python 3.9+
- Claude Code CLI
- Git

### Installation

```bash
# Clone the repo
git clone https://github.com/onlysyz/cc-claw.git
cd cc-claw

# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
cc-claw --version
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cc_claw tests/

# Run specific test file
pytest tests/test_daemon.py

# Run in watch mode
ptw tests/
```

## Project Structure

```
cc-claw/
├── client/              # Local daemon
│   ├── daemon.py       # Main entry
│   ├── handler.py      # Message handling
│   └── ...
├── server/             # Cloud server
├── tests/              # Test suite
└── docs/               # Documentation
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/)
- Use type hints where possible
- Max line length: 100 characters

### Async Code

- Use `async def` and `await` consistently
- Don't block in async functions (no `time.sleep`, use `asyncio.sleep`)
- Always handle exceptions in async code

### Testing

- Write tests for all new features
- Aim for >80% coverage
- Use pytest fixtures
- Mock external dependencies

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix a bug
docs: update documentation
refactor: restructure code
test: add tests
chore: maintenance
```

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to your branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### PR Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested the changes

## Checklist
- [ ] Code follows the style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
```

## Issues

### Bug Reports

Please include:
- CC-Claw version
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior

### Feature Requests

Please include:
- Use case description
- Proposed solution
- Alternative solutions considered

## Community

- 💬 [Discord](https://discord.gg/cc-claw)
- 🐦 [Twitter](https://twitter.com/ccclaw)
- 📖 [Documentation](https://docs.cc-claw.dev)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
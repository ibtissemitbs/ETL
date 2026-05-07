# Contributing to ETL Platform

## Development Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd ETL
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Code Style

- Use Python PEP 8 standards
- Add docstrings to functions
- Keep functions focused and small
- Use type hints where possible

## Testing

Run tests before committing:
```bash
cd backend
python -m uvicorn main:app --reload
```

## Commit Messages

Use clear, descriptive commit messages:
- ✅ `feat: Add CSV export functionality`
- ✅ `fix: Handle empty columns in profiler`
- ❌ `update stuff`
- ❌ `WIP`

## Reporting Issues

When reporting bugs:
1. Describe the exact steps to reproduce
2. Include error messages
3. Specify Python version and OS
4. Attach sample data if relevant

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test thoroughly
5. Commit with clear messages
6. Push and create a PR with description

## Project Structure

**Do not modify without discussing:**
- `/backend/main.py` - Core API
- `/src/rag_engine.py` - RAG system
- `/frontend/index.html` - UI

**Feel free to improve:**
- Add new cleaning rules
- Extend data format support
- Improve documentation
- Add tests

## Performance

When adding features:
- Consider memory usage for large files
- Avoid blocking operations
- Test with realistic data sizes

## Questions?

Open an issue with the `question` label.

---

Thank you for contributing! 🚀

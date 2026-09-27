# Contributing to diff_and_compare_tool

Thank you for your interest in contributing to **diff_and_compare_tool**!

## Getting Started

1. **Fork the repository** on GitHub: [https://github.com/vikrantblu/diff_and_compare_tool](https://github.com/vikrantblu/diff_and_compare_tool)
2. **Clone your fork**:
   ```bash
   git clone https://github.com/your-username/diff_and_compare_tool.git
   cd diff_and_compare_tool
   ```
3. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Development Workflow

- Run the application:
  ```bash
  python app/main.py
  ```
- Run tests:
  ```bash
  python -m unittest discover tests
  # or
  python tests/test_all_engines.py
  ```

## Pull Request Guidelines

- Ensure all existing tests pass before submitting a pull request.
- Add unit tests for any new features or bug fixes.
- Follow PEP 8 style guidelines for Python code.
- Do not commit hardcoded absolute paths, credentials, or personal identification.
- Keep commits focused and provide descriptive commit messages.

## Questions & Community Discussions

Have a question, feedback, or feature idea?
Head over to [GitHub Discussions](https://github.com/vikrantblu/diff_and_compare_tool/discussions) to ask questions, propose ideas, or connect with the maintainers without needing to open an issue.

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

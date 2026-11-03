CFG to CNF Converter — Automata Theory

1. Install Python 3.9 or later.
2. Open Command Prompt / Terminal in this folder.
3. Install dependencies:
       pip install -r requirements.txt
4. Start the dashboard:
       streamlit run cfg_to_cnf_dashboard.py
5. Your browser opens the local dashboard.

Grammar input format:
    S -> aA | bB
    A -> aAA | epsilon
    B -> bB | b

Rules:
- One production per line.
- Use -> or →.
- Use | for alternatives.
- Uppercase letters are non-terminals.
- Lowercase letters/digits are terminals.
- Use ε, eps, or epsilon for the empty string.
- Put spaces between symbols when needed, e.g. S -> a A B.
- Multi-character terminal tokens can be quoted, e.g. S -> "id" A.

The dashboard displays the grammar after each conversion stage, explains why
the transformation is needed, validates the final CNF, and lets you download
the resulting grammar as a text file.

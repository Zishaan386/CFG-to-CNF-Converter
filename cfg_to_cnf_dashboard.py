"""
CFG to CNF Converter — Automata Theory
Run:
    pip install -r requirements.txt
    streamlit run cfg_to_cnf_dashboard.py

Grammar input:
    S -> aA | bB
    A -> aAA | epsilon
    B -> bB | b

Conventions:
 - Each uppercase letter is a non-terminal (S, A, B, ...).
- Lowercase letters/digits are terminals.
 - Separate symbols with spaces; variables are single uppercase letters.
- Quoted terminals are supported: S -> "id" A
- Alternatives are separated by |.
- Use epsilon, eps, or ε for the empty string.
"""

from collections import defaultdict, deque
import re
import streamlit as st

EPSILON = "ε"
TOKEN_RE = re.compile(r'"[^"]+"|[A-Z]|[a-z0-9]|ε|epsilon|eps')

def is_nonterminal(symbol):
    return bool(re.fullmatch(r"[A-Z][A-Za-z0-9_]*", symbol))

def display_symbol(symbol):
    if symbol == EPSILON:
        return EPSILON
    if is_nonterminal(symbol):
        return symbol
    if len(symbol) == 1 and symbol.isalnum() and symbol.islower():
        return symbol
    return symbol

def format_rhs(rhs):
    if not rhs:
        return EPSILON
    # Compact display for single-character symbols; spaced display otherwise.
    if all(len(x) == 1 for x in rhs):
        return "".join(display_symbol(x) for x in rhs)
    return " ".join(display_symbol(x) for x in rhs)

def format_grammar(grammar, order=None):
    if not grammar:
        return "(no productions)"
    keys = list(order or grammar.keys())
    keys += [k for k in grammar if k not in keys]
    lines = []
    for lhs in keys:
        alternatives = grammar.get(lhs, [])
        if alternatives:
            lines.append(f"{lhs} → " + " | ".join(format_rhs(rhs) for rhs in alternatives))
    return "\n".join(lines) if lines else "(no productions)"

def parse_grammar(raw):
    grammar = defaultdict(list)
    start = None
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line:
            lhs, rhs_text = line.split("->", 1)
        elif "→" in line:
            lhs, rhs_text = line.split("→", 1)
        else:
            raise ValueError(f"Line {line_no}: expected '->' or '→'.")
        lhs = lhs.strip()
        if not is_nonterminal(lhs):
            raise ValueError(f"Line {line_no}: '{lhs}' must be an uppercase non-terminal.")
        if start is None:
            start = lhs
        for alternative in rhs_text.split("|"):
            alt = alternative.strip()
            if not alt or alt.lower() in {"epsilon", "eps"} or alt == EPSILON:
                rhs = ()
            else:
                # Spaces permit multi-character names; without spaces, split into symbols.
                if " " in alt.strip():
                    tokens = alt.split()
                else:
                    tokens = TOKEN_RE.findall(alt)
                    if "".join(tokens) != alt:
                        raise ValueError(
                            f"Line {line_no}: cannot tokenize '{alt}'. "
                            "Use uppercase names for variables and lowercase letters for terminals."
                        )
                rhs_list = []
                for token in tokens:
                    if token in {EPSILON, "epsilon", "eps"}:
                        raise ValueError(f"Line {line_no}: epsilon must appear alone in an alternative.")
                    if token.startswith('"') or token.startswith("'"):
                        rhs_list.append(token[1:-1])
                    else:
                        rhs_list.append(token)
                rhs = tuple(rhs_list)
            if rhs not in grammar[lhs]:
                grammar[lhs].append(rhs)
    if not grammar or start is None:
        raise ValueError("Enter at least one production.")
    defined = set(grammar)
    for lhs, alternatives in grammar.items():
        for rhs in alternatives:
            for symbol in rhs:
                if is_nonterminal(symbol) and symbol not in defined:
                    raise ValueError(f"Non-terminal '{symbol}' is used but has no production.")
    return dict(grammar), start

def clone(grammar):
    return {lhs: list(dict.fromkeys(tuple(rhs) for rhs in alternatives))
            for lhs, alternatives in grammar.items()}

def add_rule(grammar, lhs, rhs):
    rhs = tuple(rhs)
    grammar.setdefault(lhs, [])
    if rhs not in grammar[lhs]:
        grammar[lhs].append(rhs)

def fresh_name(base, used):
    candidate = base
    i = 0
    while candidate in used:
        i += 1
        candidate = f"{base}{i}"
    used.add(candidate)
    return candidate

def nullable_variables(grammar):
    nullable = set()
    changed = True
    while changed:
        changed = False
        for lhs, alternatives in grammar.items():
            if lhs in nullable:
                continue
            for rhs in alternatives:
                if not rhs or all(is_nonterminal(s) and s in nullable for s in rhs):
                    nullable.add(lhs)
                    changed = True
                    break
    return nullable

def eliminate_epsilon(grammar, start):
    g = clone(grammar)
    nullable = nullable_variables(g)
    out = {lhs: [] for lhs in g}
    for lhs, alternatives in g.items():
        for rhs in alternatives:
            nullable_positions = [i for i, s in enumerate(rhs)
                                  if is_nonterminal(s) and s in nullable]
            # Each nullable occurrence can independently be retained or omitted.
            variants = {()}
            for symbol in rhs:
                next_variants = set()
                can_omit = is_nonterminal(symbol) and symbol in nullable
                for prefix in variants:
                    next_variants.add(prefix + (symbol,))
                    if can_omit:
                        next_variants.add(prefix)
                variants = next_variants
            for variant in variants:
                if variant or lhs == start:
                    add_rule(out, lhs, variant)
    # Empty production is permitted only at the (fresh) start symbol.
    for lhs in list(out):
        if lhs != start:
            out[lhs] = [rhs for rhs in out[lhs] if rhs]
    if start in nullable:
        add_rule(out, start, ())
    return out, nullable

def eliminate_unit(grammar):
    g = clone(grammar)
    nts = set(g)
    out = {lhs: [] for lhs in g}
    for lhs in g:
        closure = {lhs}
        queue = deque([lhs])
        while queue:
            current = queue.popleft()
            for rhs in g.get(current, []):
                if len(rhs) == 1 and rhs[0] in nts and rhs[0] not in closure:
                    closure.add(rhs[0])
                    queue.append(rhs[0])
        for variable in closure:
            for rhs in g.get(variable, []):
                if not (len(rhs) == 1 and rhs[0] in nts):
                    add_rule(out, lhs, rhs)
    return out

def remove_useless(grammar, start):
    g = clone(grammar)
    nts = set(g)
    # First remove non-generating variables.
    generating = set()
    changed = True
    while changed:
        changed = False
        for lhs, alternatives in g.items():
            if lhs not in generating and any(
                all(not is_nonterminal(s) or s in generating for s in rhs)
                for rhs in alternatives
            ):
                generating.add(lhs)
                changed = True
    g = {lhs: [rhs for rhs in alternatives
               if all(not is_nonterminal(s) or s in generating for s in rhs)]
         for lhs, alternatives in g.items() if lhs in generating}
    if start not in g:
        return {}, {"generating": generating, "reachable": set()}
    # Then remove variables unreachable from the start.
    reachable = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for rhs in g.get(current, []):
            for symbol in rhs:
                if is_nonterminal(symbol) and symbol in g and symbol not in reachable:
                    reachable.add(symbol)
                    queue.append(symbol)
    g = {lhs: alternatives for lhs, alternatives in g.items() if lhs in reachable}
    return g, {"generating": generating, "reachable": reachable}

def replace_terminals(grammar):
    g = clone(grammar)
    used = set(g)
    terminal_map = {}
    out = {lhs: [] for lhs in g}
    for lhs, alternatives in g.items():
        for rhs in alternatives:
            if len(rhs) >= 2:
                new_rhs = []
                for symbol in rhs:
                    if not is_nonterminal(symbol):
                        if symbol not in terminal_map:
                            variable = fresh_name("T", used)
                            terminal_map[symbol] = variable
                            out[variable] = [(symbol,)]
                        new_rhs.append(terminal_map[symbol])
                    else:
                        new_rhs.append(symbol)
                add_rule(out, lhs, new_rhs)
            else:
                add_rule(out, lhs, rhs)
    return out, terminal_map

def binarize(grammar):
    g = clone(grammar)
    used = set(g)
    out = {lhs: [] for lhs in g}
    created = []
    for lhs, alternatives in g.items():
        for rhs in alternatives:
            if len(rhs) <= 2:
                add_rule(out, lhs, rhs)
                continue
            # Right-branching decomposition: A -> X1 C1, C1 -> X2 C2, ...
            current_lhs = lhs
            remaining = list(rhs)
            while len(remaining) > 2:
                helper = fresh_name("C", used)
                created.append(helper)
                add_rule(out, current_lhs, (remaining[0], helper))
                current_lhs = helper
                remaining = remaining[1:]
            add_rule(out, current_lhs, tuple(remaining))
    return out, created

def validate_cnf(grammar, start):
    errors = []
    for lhs, alternatives in grammar.items():
        for rhs in alternatives:
            if len(rhs) == 1 and rhs[0] == EPSILON:
                errors.append(f"{lhs} → ε is stored incorrectly.")
            elif len(rhs) == 0:
                if lhs != start:
                    errors.append(f"ε-production at non-start variable {lhs}.")
            elif len(rhs) == 1:
                if is_nonterminal(rhs[0]):
                    errors.append(f"Unit production: {lhs} → {rhs[0]}.")
            elif len(rhs) == 2:
                if not all(is_nonterminal(s) for s in rhs):
                    errors.append(f"Two-symbol RHS must contain only variables: {lhs} → {format_rhs(rhs)}.")
            else:
                errors.append(f"RHS has more than two symbols: {lhs} → {format_rhs(rhs)}.")
    return errors

def convert_to_cnf(original, original_start):
    steps = []
    g = clone(original)
    used = set(g)

    # Always add a fresh start symbol. It guarantees that the start variable
    # never appears on any RHS and safely handles nullable original starts.
    new_start = fresh_name("S0", used)
    g[new_start] = [(original_start,)]
    steps.append({
        "title": "1. Introduce a new start symbol",
        "reason": (f"Created {new_start} → {original_start}. This keeps the start "
                   "variable out of every right-hand side and makes ε handling safe."),
        "grammar": clone(g)
    })

    g, nullable = eliminate_epsilon(g, new_start)
    steps.append({
        "title": "2. Eliminate ε-productions",
        "reason": ("Nullable variables: " + (", ".join(sorted(nullable)) if nullable else "none") +
                   ". For every production, the program creates the alternatives formed "
                   "by optionally omitting nullable variables. Only the new start may retain ε."),
        "grammar": clone(g)
    })

    before_unit = clone(g)
    g = eliminate_unit(g)
    steps.append({
        "title": "3. Eliminate unit productions",
        "reason": ("A unit production has exactly one variable on its RHS (for example A → B). "
                   "The non-unit productions reachable through unit chains are copied to the "
                   "left-hand variable, then the unit rules are removed."),
        "grammar": clone(g)
    })

    g, useless_info = remove_useless(g, new_start)
    steps.append({
        "title": "4. Remove useless symbols",
        "reason": ("First removed non-generating variables (those that can never derive a string "
                   "of terminals), then removed variables unreachable from the start symbol. "
                   "Generating set: " + (", ".join(sorted(useless_info["generating"])) or "none") +
                   ". Reachable set after filtering: " +
                   (", ".join(sorted(useless_info["reachable"])) or "none") + "."),
        "grammar": clone(g)
    })

    g, terminal_map = replace_terminals(g)
    mapping_text = ", ".join(f"{v} → {t}" for t, v in terminal_map.items()) or "no replacements needed"
    steps.append({
        "title": "5. Replace terminals in long productions",
        "reason": ("A terminal cannot appear alongside other symbols in a CNF production. "
                   "Created helper variables: " + mapping_text + "."),
        "grammar": clone(g)
    })

    g, helpers = binarize(g)
    steps.append({
        "title": "6. Break long productions into pairs",
        "reason": ("Every RHS with more than two symbols was split into a chain of productions "
                   "containing exactly two variables. New helper variables: " +
                   (", ".join(helpers) if helpers else "none") + "."),
        "grammar": clone(g)
    })

    # Remove duplicate rules and empty dictionary entries.
    g = {lhs: list(dict.fromkeys(alts)) for lhs, alts in g.items() if alts}
    errors = validate_cnf(g, new_start)
    if errors:
        raise RuntimeError("CNF validation failed:\n" + "\n".join(errors))
    return new_start, g, steps

st.set_page_config(page_title="CFG → CNF Converter", page_icon="📘", layout="wide")

st.markdown("""
<style>
.main {background: #f7f8fc;}
.block-container {padding-top: 2rem; max-width: 1200px;}
.hero {padding: 1.4rem 1.6rem; border-radius: 16px; color: white;
       background: linear-gradient(115deg,#172554,#2563eb);}
.hero h1 {margin:0; color:white; font-size:2rem;}
.hero p {margin:.45rem 0 0; color:#dbeafe;}
.note {padding: .8rem 1rem; background:#eff6ff; border-left:4px solid #2563eb;
       border-radius:8px; color:#1e3a8a;}
.step-card {padding: .6rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>📘 CFG → CNF Converter</h1>
  <p>Automata Theory · Step-by-step conversion with explanations</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("How to enter a grammar")
    st.markdown("""
- One production per line.
- Use `->` or `→`.
- Separate alternatives with `|`.
- Uppercase letters are variables.
- Lowercase letters are terminals.
- Use `ε`, `eps`, or `epsilon` for empty string.
- Separate symbols with spaces; uppercase letters are variables.
""")
grammar_text = st.text_area("Enter your CFG", height=190)

col1, col2 = st.columns([1, 4])
with col1:
    convert = st.button("Convert to CNF", type="primary", use_container_width=True)
with col2:
    st.caption("The converter applies all six standard stages and validates the final grammar.")

if convert:
    try:
        original, start = parse_grammar(grammar_text)
        new_start, result, steps = convert_to_cnf(original, start)
        st.session_state["conversion"] = {
            "original": original, "start": start, "new_start": new_start,
            "result": result, "steps": steps
        }
    except Exception as exc:
        st.error(str(exc))
        st.session_state.pop("conversion", None)

if "conversion" in st.session_state:
    data = st.session_state["conversion"]
    st.divider()
    st.subheader("Conversion result")
    m1, m2, m3 = st.columns(3)
    m1.metric("Original variables", len(data["original"]))
    m2.metric("Conversion stages", len(data["steps"]))
    m3.metric("Final variables", len(data["result"]))

    tab1, tab2, tab3 = st.tabs(["Step-by-step solution", "Final CNF", "CNF checklist"])

    with tab1:
        st.markdown("### Original grammar")
        st.code(format_grammar(data["original"]), language="text")
        for step_no, step in enumerate(data["steps"], 1):
            with st.expander(step["title"], expanded=(step_no == 1)):
                st.markdown("**Why is this step required?**")
                st.write(step["reason"])
                st.markdown("**Grammar after this step**")
                st.code(format_grammar(step["grammar"]), language="text")

    with tab2:
        st.success(f"Conversion completed. New start symbol: {data['new_start']}")
        st.code(format_grammar(data["result"]), language="text")
        st.download_button(
            "Download final CNF (.txt)",
            data=f"Start symbol: {data['new_start']}\n\n{format_grammar(data['result'])}\n",
            file_name="converted_cnf.txt",
            mime="text/plain"
        )

    with tab3:
        st.markdown("A valid CNF grammar must satisfy these conditions:")
        checks = []
        for lhs, alternatives in data["result"].items():
            for rhs in alternatives:
                if not rhs:
                    checks.append((f"{lhs} → ε", lhs == data["new_start"],
                                   "Empty production is allowed only for the new start symbol."))
                elif len(rhs) == 1:
                    checks.append((f"{lhs} → {format_rhs(rhs)}",
                                   not is_nonterminal(rhs[0]),
                                   "A single-symbol RHS must be a terminal."))
                elif len(rhs) == 2:
                    checks.append((f"{lhs} → {format_rhs(rhs)}",
                                   all(is_nonterminal(s) for s in rhs),
                                   "A two-symbol RHS must contain two variables."))
                else:
                    checks.append((f"{lhs} → {format_rhs(rhs)}", False,
                                   "RHS must contain at most two symbols."))
        for rule, passed, explanation in checks:
            st.write(("✅ " if passed else "❌ ") + f"`{rule}` — {explanation}")
        if all(row[1] for row in checks):
            st.success("All productions satisfy the CNF conditions.")

else:
    st.info("Enter a grammar and click **Convert to CNF** to see the complete solution.")
    st.markdown("""
    <div class="note">
    <b>Important:</b> The program assumes uppercase identifiers are non-terminals
    and lowercase letters are terminals. Separate symbols with spaces when needed.
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.caption("CFG to CNF Converter · Educational tool for Automata Theory")

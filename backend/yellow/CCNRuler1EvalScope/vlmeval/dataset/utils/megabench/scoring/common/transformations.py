# Private iCAP Yellow implementation. Do not publish.
"""Like-to-like data transformations."""
import re
import unicodedata

def remove_def_indef_articles(text: str) -> str:
    """Remove definite and indefinite articles."""
    text_list = [t for t in text.split(' ') if t.lower() not in {'the', 'a'}]
    return ' '.join(text_list)

def replace_macrons_with_latex_overline(text: str) -> str:
    """Replace letters with macrons with the LaTeX bar."""
    result = []
    for char in text:
        if char.isalpha():
            decomposed = unicodedata.normalize('NFD', char)
            if len(decomposed) > 1 and decomposed[1] == '̄':
                result.append(f'\\overline{{{decomposed[0]}}}')
            else:
                result.append(char)
        elif char != '̄':
            result.append(char)
        else:
            result[-1] = f'\\overline{{{result[-1]}}}'
    return ''.join(result)

def fix_overline_underscores(text: str) -> str:
    """Puts underscores that are outside \\overline within overline."""
    pattern = '\\\\overline\\{([^}]*)\\}_([^{}\\\\ ]*)'
    return re.sub(pattern, '\\\\overline{\\1_\\2}', text)
greek_to_latex = {'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta', 'ε': '\\epsilon', 'ζ': '\\zeta', 'η': '\\eta', 'θ': '\\theta', 'ι': '\\iota', 'κ': '\\kappa', 'λ': '\\lambda', 'μ': '\\mu', 'ν': '\\nu', 'ξ': '\\xi', 'ο': '\\omicron', 'π': '\\pi', 'ρ': '\\rho', 'σ': '\\sigma', 'τ': '\\tau', 'υ': '\\upsilon', 'φ': '\\phi', 'χ': '\\chi', 'ψ': '\\psi', 'ω': '\\omega', 'Α': '\\Alpha', 'Β': '\\Beta', 'Γ': '\\Gamma', 'Δ': '\\Delta', 'Ε': '\\Epsilon', 'Ζ': '\\Zeta', 'Η': '\\Eta', 'Θ': '\\Theta', 'Ι': '\\Iota', 'Κ': '\\Kappa', 'Λ': '\\Lambda', 'Μ': '\\Mu', 'Ν': '\\Nu', 'Ξ': '\\Xi', 'Ο': '\\Omicron', 'Π': '\\Pi', 'Ρ': '\\Rho', 'Σ': '\\Sigma', 'Τ': '\\Tau', 'Υ': '\\Upsilon', 'Φ': '\\Phi', 'Χ': '\\Chi', 'Ψ': '\\Psi', 'Ω': '\\Omega'}

def replace_greek_letters(text: str) -> str:
    """Replace Greek letters in Unicode with their LaTeX equivalents."""
    return re.sub('[α-ωΑ-Ω]', lambda match: greek_to_latex[match.group()] + ' ', text)

def remove_latex_math_delimiters(latex_str):
    env_pattern = '\\\\(begin|end)\\{.*?\\}(?:\\[[^\\[\\]]*\\])?'
    latex_str = re.sub(env_pattern, '', latex_str)
    inline_math_pattern = '\\\\\\(|\\\\\\)'
    latex_str = re.sub(inline_math_pattern, '', latex_str)
    display_math_pattern = '\\\\\\[|\\\\\\]'
    latex_str = re.sub(display_math_pattern, '', latex_str)
    return latex_str

def normalize_latex(text: str) -> str:
    """Normalize the LaTeX expression."""
    text = text.replace('\\bar', '\\overline')
    text = replace_macrons_with_latex_overline(text)
    text = fix_overline_underscores(text)
    text = replace_greek_letters(text)
    text = remove_latex_math_delimiters(text)
    return text

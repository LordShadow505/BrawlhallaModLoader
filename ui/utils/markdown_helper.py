import re

def render_markdown_to_html(md_text: str) -> str:
    """
    Converts GitHub Flavored Markdown (release notes, changelogs) into clean,
    beautifully styled dark-mode HTML compatible with Qt QLabel / QTextBrowser.
    """
    if not md_text:
        return ""
    
    text = md_text.replace("\r\n", "\n")

    # 1. Tables: convert | col1 | col2 | into styled HTML <table>
    def parse_table(match):
        raw_block = match.group(0).strip()
        lines = [line.strip() for line in raw_block.split('\n') if line.strip()]
        if len(lines) < 2:
            return match.group(0)
        
        headers = [c.strip() for c in lines[0].strip('|').split('|')]
        rows = []
        for line in lines[2:]:
            cols = [c.strip() for c in line.strip('|').split('|')]
            rows.append(cols)
        
        html = ['<table style="width:100%; border-collapse:collapse; margin:10px 0; background-color:#16171B; border:1px solid #2B2C30; border-radius:6px;">']
        html.append('<thead><tr style="background-color:#22242A;">')
        for h in headers:
            html.append(f'<th style="padding:8px 12px; text-align:left; color:#FFFFFF; border-bottom:1px solid #333640; font-size:11px; font-weight:bold;">{h}</th>')
        html.append('</tr></thead><tbody>')
        for row in rows:
            html.append('<tr style="border-bottom:1px solid #23252C;">')
            for cell in row:
                html.append(f'<td style="padding:8px 12px; color:#DDDDDD; font-size:11px;">{cell}</td>')
            html.append('</tr>')
        html.append('</tbody></table>')
        return "".join(html)

    table_pattern = re.compile(r'(?:(?:\|[^\n]+\|\n)+)', re.MULTILINE)
    text = table_pattern.sub(parse_table, text)

    # 2. Callout / Notice blocks: *** text ***
    def parse_callout(match):
        content = match.group(1).strip()
        return f'<div style="background-color:#2A2215; border:1px solid #D97706; border-radius:6px; padding:10px 14px; margin:10px 0; color:#FBBF24; font-weight:bold; font-size:11px;">{content}</div>'

    text = re.sub(r'\*\*\*\s*(.*?)\s*\*\*\*', parse_callout, text, flags=re.DOTALL)

    # 3. Horizontal rules (--- or ***)
    text = re.sub(r'^(?:---|\*\*\*|___)\s*$', '<hr style="border:none; border-top:1px solid #2B2C30; margin:14px 0;" />', text, flags=re.MULTILINE)

    # 4. Headers
    text = re.sub(r'^#\s+(.*?)$', r'<h1 style="color:#FFFFFF; font-size:16px; font-weight:bold; margin-top:14px; margin-bottom:6px; border-bottom:1px solid #2B2C30; padding-bottom:4px;">\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.*?)$', r'<h2 style="color:#4A9CEC; font-size:14px; font-weight:bold; margin-top:12px; margin-bottom:6px;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.*?)$', r'<h3 style="color:#4DB6AC; font-size:12px; font-weight:bold; margin-top:10px; margin-bottom:4px;">\1</h3>', text, flags=re.MULTILINE)

    # 5. Bold & Italic
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    # 6. Images & Links
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1" height="16" style="vertical-align:middle;" />', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" style="color:#4DB6AC; text-decoration:underline;">\1</a>', text)

    # 7. Unordered Lists (- item or * item)
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            item_text = stripped[2:].strip()
            if not in_list:
                in_list = True
                new_lines.append('<ul style="margin:4px 0 8px 16px; padding:0;">')
            new_lines.append(f'<li style="margin-bottom:3px; color:#E0E0E0; font-size:11px;">{item_text}</li>')
        else:
            if in_list:
                in_list = False
                new_lines.append('</ul>')
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')

    text = '\n'.join(new_lines)

    # 8. Paragraphs / Linebreaks
    blocks = text.split('\n\n')
    formatted_blocks = []
    for b in blocks:
        b_strip = b.strip()
        if not b_strip:
            continue
        if b_strip.startswith('<h') or b_strip.startswith('<ul') or b_strip.startswith('<table') or b_strip.startswith('<div') or b_strip.startswith('<hr'):
            formatted_blocks.append(b_strip)
        else:
            formatted_blocks.append(f'<p style="margin:4px 0; color:#DDDDDD; font-size:11px; line-height:1.4;">{b_strip.replace(chr(10), "<br/>")}</p>')

    return '\n'.join(formatted_blocks)

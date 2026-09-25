utf-8import os
import tokenize
import re
from io import BytesIO

def remove_python_comments(filepath):
    try:
        with open(filepath, 'rb') as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    result = []
    try:
        tokens = tokenize.tokenize(BytesIO(source).readline)
        last_lineno = -1
        last_col = 0
        for tok in tokens:
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end

            if start_line > last_lineno:
                last_col = 0
            if start_col > last_col:
                result.append(" " * (start_col - last_col))

            if token_type == tokenize.COMMENT:
                pass 
            else:
                result.append(token_string)
            
            last_lineno = end_line
            last_col = end_col
            
        new_source = "".join(result).encode('utf-8')
        
        if new_source != source:
            with open(filepath, 'wb') as f:
                f.write(new_source)
            print(f"Stripped comments from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def remove_html_comments(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        
        
        new_content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Stripped comments from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    repo_dir = r"c:\Users\Saanvi\Desktop\SAANVI\SSRISS_ASSIGNMENTS"
    for root, dirs, files in os.walk(repo_dir):
        if '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            filepath = os.path.join(root, file)
            if file.endswith(".py"):
                remove_python_comments(filepath)
            elif file.endswith((".html", ".htm")):
                remove_html_comments(filepath)

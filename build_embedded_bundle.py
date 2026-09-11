import os
import zipfile
import io
import base64

def generate_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        # Templates
        for f in os.listdir('templates'):
            p = os.path.join('templates', f)
            if os.path.isfile(p):
                zf.write(p, p.replace('\\', '/'))
        # Static
        for root, _, files in os.walk('static'):
            for f in files:
                p = os.path.join(root, f)
                zf.write(p, p.replace('\\', '/'))
    
    b64_str = base64.b64encode(buf.getvalue()).decode('ascii')
    
    with open('embedded_assets.py', 'w', encoding='utf-8') as f:
        f.write('# Embedded assets for Cam-EDC deployment\n')
        f.write('EMBEDDED_ASSETS_ZIP = """' + b64_str + '"""\n')
    
    print(f"Generated embedded_assets.py successfully! (Size: {len(b64_str)} chars)")

if __name__ == '__main__':
    generate_bundle()

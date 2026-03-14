import sass
import os
import time

def build_sass():
    scss_dir = os.path.join("mp", "static", "scss")
    css_dir = os.path.join("mp", "static", "css")
    
    if not os.path.exists(css_dir):
        os.makedirs(css_dir)

    print(f"Building SCSS from {scss_dir} to {css_dir}")

    # Compile all .scss files in the directory that don't start with _
    for filename in os.listdir(scss_dir):
        if filename.endswith(".scss") and not filename.startswith("_"):
            input_path = os.path.join(scss_dir, filename)
            output_path = os.path.join(css_dir, filename.replace(".scss", ".css"))
            
            try:
                # Compile using sass
                # include_paths allows @import to find files in the same directory
                with open(input_path, "r", encoding="utf-8") as f:
                    scss_content = f.read()
                
                css_content = sass.compile(
                    string=scss_content, 
                    include_paths=[scss_dir],
                    output_style='compressed' # or 'nested', 'expanded', 'compact'
                )
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(css_content)
                
                print(f"Compiled {filename} -> {os.path.basename(output_path)}")
                
            except Exception as e:
                print(f"Error compiling {filename}: {e}")

if __name__ == "__main__":
    build_sass()

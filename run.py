from mp import create_app

app = create_app()

if __name__ == "__main__":
    try:
        from build_assets import build_sass
        build_sass()
    except ImportError:
        print("Required packages for SCSS build not found. Skipping...")
    app.run()
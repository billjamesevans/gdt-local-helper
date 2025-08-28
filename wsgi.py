from app import create_app
app = create_app()

if __name__ == '__main__':
    # Respect FLASK_RUN_HOST/PORT if set by environment during direct run
    import os
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_RUN_PORT', '5000'))
    app.run(host=host, port=port)

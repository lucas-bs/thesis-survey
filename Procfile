release: curl https://sh.rustup.rs -sSf | sh -s -- -y
web: gunicorn --worker-class eventlet -w 1 run:app

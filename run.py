from gpt import socketio, app

# add host='0.0.0.0' for all devices in the network to connect to the server
if __name__ == '__main__':
    # Run the application on the development server
    socketio.run(app, host='0.0.0.0', allow_unsafe_werkzeug=True)


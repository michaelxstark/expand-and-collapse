from flask import Flask, jsonify, send_from_directory
import threading
import os
import random
import time
import queue
import librosa
import datetime


# Server start time in UTC
server_start_time = datetime.datetime.now(datetime.UTC)


#generate mute states for voices
def generate_mutes():
    all_mutes = [0, 0, 0]
    mutes = [random.randint(0, 1) for i in range(3)]
    while True:
        if mutes == all_mutes:
            mutes = [random.randint(0, 1) for i in range(3)]
        else:
            return mutes


#select part
def draw_part():
    part = random.randint(1, 16)
    return part


#choose octave
def choose_oct():
    octave = random.choice(['norm', 'UP'])
    return octave


#calculate file lengths for sleep times
def calculate_file_length(file_num, folder, abbr):
    # Updated path to include audio folder
    y, sr = librosa.load(f'static/audio/{folder}/{folder} Oct norm/{file_num} U {abbr} norm.mp3', sr=None)
    length = len(y) / sr
    return length


#make dictionary with file lengths
global file_lengths
file_lengths = {f'{i}': calculate_file_length(i, 'Ordinario', 'ord') for i in range(1, 17, 1)}


# Shared state for active voices (not queues!)
current_ord_state = {'voices': [], 'start_time': 0, 'duration': 0}
current_krebs_state = {'voices': [], 'start_time': 0, 'duration': 0}
state_lock = threading.Lock()

# Flask app
app = Flask(__name__, static_folder="static")


@app.route('/server-start-time')
def get_server_start_time():
    return jsonify({
        "start_time": server_start_time,
        "timezone": "UTC"
    })


@app.route('/check-audio/<path:filename>')
def check_audio(filename):
    import os
    from flask import Response
    full_path = os.path.join('static/audio', filename)
    if os.path.exists(full_path):
        file_size = os.path.getsize(full_path)
        # Return first 32 bytes to check header
        with open(full_path, 'rb') as f:
            header = f.read(32).hex()
        return jsonify({
            'exists': True,
            'size': file_size,
            'header': header
        })
    return jsonify({'exists': False})


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    print(f"Attempting to serve: {filename}")
    full_path = f"static/audio/{filename}"
    print(f"Full path: {full_path}")
    return send_from_directory('static/audio', filename,
                             mimetype='audio/mp3')


@app.route('/test-files')
def test_files():
    import os
    files = []
    for root, dirs, filenames in os.walk('static/audio'):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return jsonify(files)


@app.route('/')
def index():
    return send_from_directory("static", "index.html")


@app.route('/file-lengths')
def get_file_lengths():
    return jsonify(file_lengths)


@app.route('/get_ord', methods=['GET'])
def get_ord():
    # Return the current state for Ordinario (all clients get the same data)
    with state_lock:
        return jsonify(current_ord_state)


@app.route('/get_krebs', methods=['GET'])
def get_krebs():
    # Return the current state for Krebs (all clients get the same data)
    with state_lock:
        return jsonify(current_krebs_state)


def process_audio(folder, abbr, state_dict):
    while True:
        # Use UTC timestamp (time.time() is already UTC-based)
        current_time = time.time()

        mute_states = generate_mutes()
        part = draw_part()
        oct = choose_oct()

        # Remove 'static/audio' from base path
        base_path = f"{folder}/{folder} Oct {oct}"
        under = f"{base_path}/{part} U {abbr} {oct}.mp3"
        middle = f"{base_path}/{part} M {abbr} {oct}.mp3"
        over = f"{base_path}/{part} O {abbr} {oct}.mp3"
        voices = [under, middle, over]
        active_voices = [voices[e] for e, m in enumerate(mute_states) if m > 0]

        # Update the shared state (instead of putting in queue)
        with state_lock:
            state_dict['voices'] = active_voices
            state_dict['start_time'] = current_time
            state_dict['duration'] = file_lengths[f'{part}']

        print(f"Updated state for {folder}:", active_voices, f"Start time (UTC): {current_time}")
        time.sleep(file_lengths[f'{part}'])


# Start threads for audio processing
thread_ord = threading.Thread(target=process_audio, args=("Ordinario", "ord", current_ord_state))
thread_krebs = threading.Thread(target=process_audio, args=("Krebs", "Krebs", current_krebs_state))


if __name__ == '__main__':
    #time.sleep(20)
    thread_ord.start()
    thread_krebs.start()
    port = int(os.environ.get('PORT', 8000))  # Use Render's port, fallback to 5000 locally
    app.run(host='0.0.0.0', port=port)

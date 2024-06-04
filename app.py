import json
import os
import re
from flask import Flask, request, render_template, redirect, url_for
from plexapi.server import PlexServer
from collections import defaultdict

app = Flask(__name__)

def load_config(config_file='config.json'):
    with open(config_file, 'r') as file:
        config = json.load(file)
    return config

def connect_plex(config):
    baseurl = config['PLEX_SERVER']
    token = config['PLEX_TOKEN']
    return PlexServer(baseurl, token)

def list_libraries(plex):
    return plex.library.sections()

def get_library(libraries, index):
    return libraries[index]

def score_file(media, config):
    score = 0

    filename = os.path.basename(media.parts[0].file)
    for pattern, value in config['FILENAME_SCORES'].items():
        if re.search(pattern, filename, re.IGNORECASE):
            score += value

    audio_codec = media.audioCodec or "Unknown"
    score += config['AUDIO_CODEC_SCORES'].get(audio_codec, 0)

    video_codec = media.videoCodec or "Unknown"
    score += config['VIDEO_CODEC_SCORES'].get(video_codec, 0)

    resolution = media.videoResolution or "Unknown"
    score += config['VIDEO_RESOLUTION_SCORES'].get(resolution, 0)

    if config['SCORE_FILESIZE']:
        score += media.parts[0].size / (1024 * 1024)  # Score by MB

    return score

def find_duplicates(library):
    duplicates = defaultdict(list)
    for item in library.all():
        for media in item.media:
            key = (item.title, item.year)
            duplicates[key].append(media)
    return {k: v for k, v in duplicates.items() if len(v) > 1}

@app.route('/')
def index():
    config = load_config()
    plex = connect_plex(config)
    libraries = list_libraries(plex)
    return render_template('index.html', libraries=libraries)

@app.route('/library/<int:library_id>')
def library(library_id):
    config = load_config()
    plex = connect_plex(config)
    libraries = list_libraries(plex)
    library = get_library(libraries, library_id)
    duplicates = find_duplicates(library)
    
    duplicate_media = []
    for title, medias in duplicates.items():
        media_scores = {media: score_file(media, config) for media in medias}
        sorted_media = sorted(media_scores.items(), key=lambda x: x[1], reverse=True)
        duplicate_media.append((title, sorted_media))

    return render_template('library.html', library=library, duplicate_media=duplicate_media)

@app.route('/delete', methods=['POST'])
def delete():
    config = load_config()
    plex = connect_plex(config)
    media_id = request.form['media_id']
    media = plex.fetchItem(media_id)
    media.delete()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

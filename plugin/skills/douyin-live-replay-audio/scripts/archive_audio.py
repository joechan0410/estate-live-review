"""Keep verified MP3 recordings and remove superseded audio after active readers finish."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time



def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def active_reader(label):
    commands = subprocess.check_output(['ps', '-axo', 'command='], text=True)
    scripts = ('transcribe_missing.py', 'analyze_audio.py', 'pipeline.transcribe_missing', 'pipeline.analyze_audio')
    return any(label in command and any(script in command for script in scripts)
               for command in commands.splitlines())


def archive(folder, audio_bitrate=16):
    import soundfile as sf

    complete_path = folder / 'complete.json'
    complete = json.loads(complete_path.read_text())
    root, label = folder.parent.parent, folder.name
    output = root / 'audio' / f'{label}.mp3'
    candidates = [root / 'audio' / f'{label}{suffix}' for suffix in ('.wav', '.m4a', '.aac', '.flac')]
    sources = [path for path in candidates if path.exists()]
    previous = complete.get('mp3_archive', {})
    if not output.exists() or not previous.get('verified'):
        if not sources:
            raise ValueError(f'{label}: no completed source recording')
        # The 16 kHz analysis PCM is the timing reference for existing transcripts.
        source = next((path for path in sources if path.suffix == '.wav'), sources[0])
        source_info = sf.info(source) if source.suffix == '.wav' else None
        duration = source_info.duration if source_info else float(complete['audio_duration'])
        temporary = output.with_name(f'{label}.encoding.mp3')
        subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-y',
                        '-i', str(source), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000',
                        '-c:a', 'libmp3lame', '-b:a', f'{audio_bitrate}k', '-threads', '1', str(temporary)], check=True)
        info = sf.info(temporary)
        if info.channels != 1 or info.samplerate != 16000 or abs(info.duration-duration) > 0.2:
            raise ValueError(f'{label}: MP3 format/duration validation failed')
        subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-nostdin',
                        '-i', str(temporary), '-f', 'null', '-'], check=True)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(output)
        previous = {'verified': True, 'verified_at': datetime.now().astimezone().isoformat(),
                    'format': f'MP3 {audio_bitrate} kbps mono 16 kHz', 'bitrate_kbps': audio_bitrate,
                    'source_for_encoding': str(source),
                    'source_seconds': duration, 'decoded_seconds': info.duration,
                    'duration_delta_seconds': info.duration-duration,
                    'mp3_bytes': output.stat().st_size, 'sha256': digest,
                    'source_files': [{'path': str(path), 'bytes': path.stat().st_size} for path in sources],
                    'deleted_files': [], 'removed_bytes': 0, 'status': 'verified_cleanup_pending'}
        complete.setdefault('source_audio_duration', complete.get('audio_duration'))
        complete['audio'] = str(output)
        complete['analysis_audio'] = str(output)
        complete.pop('wav', None)
        complete['audio_duration'] = info.duration
        complete['duration_difference'] = info.duration - complete['playlist_duration']
        complete['mp3_archive'] = previous
        write_json(complete_path, complete)
    # Older running scripts may reopen a WAV between chunks. Wait for the process,
    # not merely for lsof to show the file closed at this particular instant.
    if active_reader(label):
        return {'label': label, 'status': 'verified_cleanup_pending_active_reader'}
    for path in sources:
        if str(path) == str(output):
            continue
        size = path.stat().st_size
        path.unlink()
        previous['deleted_files'].append(str(path))
        previous['removed_bytes'] += size
    previous['status'] = 'mp3_only'
    previous['net_saved_bytes'] = previous['removed_bytes'] - previous['mp3_bytes']
    previous['cleanup_at'] = datetime.now().astimezone().isoformat()
    complete['mp3_archive'] = previous
    write_json(complete_path, complete)
    return {'label': label, 'status': previous['status'], 'saved_bytes': previous['net_saved_bytes']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--hours', type=float, default=18)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--audio-bitrate', type=int, choices=(16, 24, 32, 40, 48, 64), default=16,
                        help='MP3 kbps for new archives (default: 16); reuse already verified MP3 files')
    args = parser.parse_args()
    root = args.root.resolve()
    started, errors = time.time(), {}
    while True:
        folders = []
        for complete in sorted((root / 'data').glob('*/complete.json')):
            meta = json.loads(complete.read_text())
            if meta.get('mp3_archive', {}).get('status') != 'mp3_only':
                folders.append(complete.parent)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(archive, folder, args.audio_bitrate): folder.name for folder in folders}
            for future, label in futures.items():
                try:
                    print(json.dumps(future.result(), ensure_ascii=False), flush=True)
                    errors.pop(label, None)
                except Exception as exc:
                    errors[label] = f'{type(exc).__name__}: {exc}'
                    print(json.dumps({'label': label, 'error': errors[label]}, ensure_ascii=False), flush=True)
        archives = [json.loads(p.read_text()).get('mp3_archive', {}) for p in (root / 'data').glob('*/complete.json')]
        state = {'updated': datetime.now().astimezone().isoformat(),
                 'verified_mp3': sum(bool(x.get('verified')) for x in archives),
                 'mp3_only': sum(x.get('status') == 'mp3_only' for x in archives),
                 'net_saved_bytes': sum(x.get('net_saved_bytes', 0) for x in archives),
                 'pending_active_readers': sum(x.get('status') == 'verified_cleanup_pending' for x in archives),
                 'errors': errors}
        write_json(root / 'data/mp3-archive-state.json', state)
        if not args.watch or time.time() - started > args.hours * 3600:
            break
        time.sleep(20)
    if errors:
        raise RuntimeError('One or more recordings failed MP3 validation; their sources were retained')


if __name__ == '__main__':
    main()

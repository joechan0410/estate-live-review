"""Optional Apple Silicon local ASR for an explicitly selected recording interval."""
import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path


def chunk_ranges(start, end, chunk_seconds=600.0):
    """Partition the requested range, retaining fractional start/end boundaries."""
    for name, value in (("start", start), ("end", end), ("chunk_seconds", chunk_seconds)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
    if start < 0 or end <= start or chunk_seconds <= 0:
        raise ValueError('require 0 <= start < end and positive chunk_seconds')
    cursor = float(start)
    while cursor < end:
        finish = min(cursor + chunk_seconds, float(end))
        yield cursor, finish
        cursor = finish


def transcribe_interval(root, label, start, end=None,
                        model='mlx-community/whisper-large-v3-turbo-q4',
                        prompt_file=None, chunk_seconds=600.0):
    import soundfile as sf
    import mlx_whisper

    root = Path(root).resolve()
    audio = next((root / 'audio' / (label + ext) for ext in ('.mp3', '.wav', '.m4a')
                  if (root / 'audio' / (label + ext)).is_file()), None)
    if audio is None:
        raise FileNotFoundError(f'No recording for {label}')
    duration = sf.info(audio).duration
    end = duration if end is None else min(end, duration)
    ranges = list(chunk_ranges(start, end, chunk_seconds))
    out = root / 'data' / label / 'local_asr'
    out.mkdir(parents=True, exist_ok=True)
    prompt = Path(prompt_file).read_text(encoding='utf-8') if prompt_file else '房产直播，保留原话。'
    written = []
    for begin, finish in ranges:
        stem = f'{int(begin):06d}' if begin.is_integer() else f'{begin:010.3f}'
        path = out / (stem + '.json')
        if path.exists():
            previous = json.loads(path.read_text(encoding='utf-8'))
            if (previous['start'], previous['end'], previous.get('model')) != (begin, finish, model):
                raise ValueError(f'Existing ASR chunk has a different range or model: {path.name}')
            continue
        with tempfile.TemporaryDirectory(prefix='live-review-asr-') as temporary:
            clip = Path(temporary) / 'clip.wav'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(begin),
                            '-i', str(audio), '-t', str(finish-begin), '-ar', '16000',
                            '-ac', '1', '-y', str(clip)], check=True)
            result = mlx_whisper.transcribe(str(clip), path_or_hf_repo=model,
                                            language='zh', condition_on_previous_text=False,
                                            verbose=False, initial_prompt=prompt)
        temporary_json = path.with_suffix('.tmp')
        temporary_json.write_text(json.dumps({'start': begin, 'end': finish,
            'model': model, 'segments': result['segments'], 'text': result['text']},
            ensure_ascii=False, indent=2), encoding='utf-8')
        temporary_json.replace(path)
        written.append(path)
        print(f'{begin:g} {finish:g}', flush=True)
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--end', type=float)
    parser.add_argument('--model', default='mlx-community/whisper-large-v3-turbo-q4')
    parser.add_argument('--prompt-file', type=Path)
    parser.add_argument('--chunk-seconds', type=float, default=600)
    args = parser.parse_args()
    transcribe_interval(args.root, args.label, args.start, args.end, args.model,
                        args.prompt_file, args.chunk_seconds)


if __name__ == '__main__':
    main()

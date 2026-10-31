"""Per-recording anonymous diarization and observable speech activity measures."""
import argparse
import json
import logging
import math
import time
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def speech_activity_metrics(speech, duration, threshold=10.0):
    """Union VAD intervals and return full non-speech gaps strictly above threshold.

    These are acoustic observations. Recording gaps and other exclusions are
    resolved separately before ``silence_confirmed`` is supplied to scoring.
    This function needs no audio packages or downloaded models.
    """
    for name, value in (("duration", duration), ("threshold", threshold)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite nonnegative number")
    intervals = []
    for item in speech:
        start, end = item['start'], item['end']
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)) or end < start:
            raise ValueError('speech intervals need finite start <= end')
        start, end = max(0.0, start), min(float(duration), end)
        if start < end:
            intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1]['end']:
            merged[-1]['end'] = max(merged[-1]['end'], end)
        else:
            merged.append({'start': start, 'end': end})
    pauses, previous_end = [], 0.0
    for item in merged + [{'start': float(duration), 'end': float(duration)}]:
        gap = item['start'] - previous_end
        if gap > threshold:
            pauses.append({'start': previous_end, 'end': item['start'], 'duration': gap})
        previous_end = item['end']
    return {'speech_intervals': merged,
            'speech_seconds': sum(item['end'] - item['start'] for item in merged),
            'non_speech_windows_gt_10s': pauses,
            'non_speech_seconds_above_threshold': sum(item['duration'] for item in pauses),
            'silence_threshold_seconds': threshold}


def analyze_path(label, step=30, sample_seconds=8, decoded_path=None):
    import numpy as np
    import soundfile as sf
    import torch
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    logging.basicConfig(level=logging.ERROR)
    for name in ['httpx', 'httpcore', 'funasr']:
        logging.getLogger(name).setLevel(logging.ERROR)
    torch.set_num_threads(1)
    folder = ROOT / 'data' / label
    complete = json.loads((folder / 'complete.json').read_text())
    path = Path(decoded_path or complete.get('analysis_audio') or complete.get('wav') or complete['audio'])
    with sf.SoundFile(path) as audio:
        duration = len(audio) / audio.samplerate
        sr = audio.samplerate
    if sr != 16000:
        raise ValueError('Expected 16 kHz analysis audio')
    from silero_vad import load_silero_vad, get_speech_timestamps
    vad_path = folder / 'speech_activity.json'
    began = time.time()
    if vad_path.exists():
        speech = json.loads(vad_path.read_text())
    else:
        model = load_silero_vad()
        speech = []
        with sf.SoundFile(path) as audio:
            for chunk_start in range(0, math.ceil(duration), 600):
                audio.seek(chunk_start * sr)
                chunk = audio.read(600 * sr, dtype='float32')
                stamps = get_speech_timestamps(torch.from_numpy(chunk), model,
                                               sampling_rate=sr, threshold=0.5,
                                               min_silence_duration_ms=500,
                                               speech_pad_ms=100)
                speech.extend([{'start': chunk_start + x['start'] / sr,
                                'end': chunk_start + x['end'] / sr} for x in stamps])
                if chunk_start % 3600 == 0:
                    print(f'{label} VAD {chunk_start}/{duration:.0f}', flush=True)
        merged = []
        for item in speech:
            if merged and item['start'] - merged[-1]['end'] <= 0.1:
                merged[-1]['end'] = max(merged[-1]['end'], item['end'])
            else:
                merged.append(item)
        speech = merged
        vad_path.write_text(json.dumps(speech))
    activity = speech_activity_metrics(speech, duration)
    speech = activity['speech_intervals']
    print(f'{label} VAD complete {time.time()-began:.1f}s', flush=True)
    torch.set_num_threads(2)
    from funasr import AutoModel
    from funasr.models.campplus.utils import extract_feature
    speaker_model = AutoModel(model='funasr/campplus', hub='hf', device='cpu',
                              disable_update=True, disable_pbar=True,
                              disable_log=True)
    vectors, observations = [], []
    pending = {}
    def flush(length):
        batch = pending.pop(length, [])
        if not batch:
            return
        # Equal-length batches avoid zero-padding changing the speaker embedding.
        with torch.inference_mode():
            features, _, _ = extract_feature([torch.from_numpy(x[0]) for x in batch])
            embeddings = speaker_model.model(features).detach().cpu().numpy()
        for (_, observation), embedding in zip(batch, embeddings):
            embedding /= max(np.linalg.norm(embedding), 1e-8)
            vectors.append(embedding)
            observations.append(observation)
    with sf.SoundFile(path) as audio:
        for i, at in enumerate(np.arange(0, duration - sample_seconds, step)):
            options = [(max(at, s['start']), min(at + step, s['end']))
                       for s in speech if s['end'] > at and s['start'] < at + step]
            if not options:
                continue
            lo, hi = max(options, key=lambda x: x[1] - x[0])
            if hi - lo < 3:
                continue
            length = math.floor(min(sample_seconds, hi - lo))
            begin = lo + max(0, (hi - lo - length) / 2)
            audio.seek(int(begin * sr))
            samples = audio.read(int(length * sr), dtype='float32')
            pending.setdefault(length, []).append((samples, {'sample_start': round(begin, 3),
                                                            'sample_end': round(begin + length, 3)}))
            if len(pending[length]) == 4:
                flush(length)
            if i % 120 == 0:
                print(f'{label} speakers {at:.0f}/{duration:.0f}', flush=True)
    for length in list(pending):
        flush(length)
    ordering = sorted(range(len(observations)), key=lambda i: observations[i]['sample_start'])
    observations = [observations[i] for i in ordering]
    X = np.array([vectors[i] for i in ordering])
    if len(X) < 3:
        pauses = activity['non_speech_windows_gt_10s']
        result = {'label': label, 'duration': duration,
                  'speech_seconds': sum(s['end']-s['start'] for s in speech),
                  'method': 'Silero VAD; insufficient speech for anonymous speaker segmentation',
                  'sample_interval_seconds': step, 'choices': [], 'observations': observations,
                  'turns': [], 'boundary_status': 'insufficient_speech_not_ratable',
                  'non_speech_windows_gt_10s': pauses, 'silence_threshold_seconds': 10,
                  'silence_rule': 'strictly greater than 10 seconds; count full interval',
                  'name_mapping': 'Unassigned; insufficient evidence'}
        (folder / 'audio_analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'label': label, 'status': 'insufficient_speech_not_ratable',
                          'duration': duration}), flush=True)
        return
    choices = []
    fitted = {}
    for threshold in (0.25, 0.3, 0.35, 0.4, 0.45, 0.5):
        y = AgglomerativeClustering(n_clusters=None, distance_threshold=threshold,
                                    metric='cosine', linkage='average').fit_predict(X)
        counts = np.bincount(y)
        score = float(silhouette_score(X, y, metric='cosine')) if 1 < len(counts) < len(X) else None
        choices.append({'threshold': threshold, 'clusters': len(counts),
                        'counts': counts.tolist(), 'silhouette': score})
        fitted[threshold] = y
    # This is a starting point for review, not a calibrated identity classifier.
    selected = 0.4
    y = fitted[selected]
    mapping = {}
    for item, cluster in zip(observations, y):
        if int(cluster) not in mapping:
            mapping[int(cluster)] = f'SPEAKER_{len(mapping)+1:02d}'
        item['speaker'] = mapping[int(cluster)]
    # Five-sample local majority estimates the main presenter; preserve raw
    # observations so short off-mic voices are not disguised as confirmed shifts.
    raw_speakers = [item['speaker'] for item in observations]
    for index, item in enumerate(observations):
        neighbors = raw_speakers[max(0, index-2):min(len(raw_speakers), index+3)]
        item['main_presenter_candidate'] = max(dict.fromkeys(neighbors), key=neighbors.count)
    turns = []
    for index, item in enumerate(observations):
        center = (item['sample_start'] + item['sample_end']) / 2
        if index == 0:
            start = 0.0
        else:
            previous = observations[index-1]
            start = (center + (previous['sample_start'] + previous['sample_end']) / 2) / 2
        if turns and turns[-1]['speaker'] == item['main_presenter_candidate']:
            turns[-1]['end'] = duration
        else:
            if turns:
                turns[-1]['end'] = start
            turns.append({'start': start, 'end': duration, 'speaker': item['main_presenter_candidate']})
    pauses = activity['non_speech_windows_gt_10s']
    result = {'label': label, 'duration': duration,
              'speech_seconds': sum(s['end'] - s['start'] for s in speech),
              'method': 'Silero VAD + CAM++ anonymous per-recording clustering',
              'sample_interval_seconds': step, 'selected_distance_threshold': selected,
              'boundary_status': 'candidate boundaries; audit transition neighborhoods',
              'choices': choices, 'observations': observations, 'turns': turns,
              'silence_threshold_seconds': 10,
              'silence_rule': 'strictly greater than 10 seconds; count full interval',
              'non_speech_windows_gt_10s': pauses,
              'name_mapping': 'Names require explicit spoken self-introductions or handover text; no cross-recording biometric identity matching.'}
    (folder / 'audio_analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    # Embeddings are task-local memory only; do not create an identity enrollment store.
    print(json.dumps({'label': label, 'duration': duration,
                      'speech_ratio': result['speech_seconds'] / duration,
                      'choices': choices, 'turns': turns,
                      'elapsed_seconds': time.time() - began}, ensure_ascii=False), flush=True)


def main(label, step=30, sample_seconds=8):
    complete = json.loads((ROOT / 'data' / label / 'complete.json').read_text())
    source = Path(complete.get('analysis_audio') or complete.get('wav') or complete['audio'])
    if source.suffix.lower() == '.mp3':
        # Decode sequentially before random speaker sampling. MP3 bit reservoirs
        # can otherwise cause decoder warnings at isolated random seek points.
        with tempfile.TemporaryDirectory(prefix='live-review-vad-') as temporary:
            decoded = Path(temporary) / 'analysis.wav'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source),
                            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(decoded)], check=True)
            return analyze_path(label, step, sample_seconds, decoded)
    return analyze_path(label, step, sample_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--step', type=int, default=5)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    ROOT=args.root.resolve()
    main(args.label, args.step)

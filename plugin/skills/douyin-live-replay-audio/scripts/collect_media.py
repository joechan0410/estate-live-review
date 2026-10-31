"""Download every segment once; retain audio and embedded subtitle evidence."""
import argparse
import concurrent.futures as cf
import json
import hashlib
import os
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
PATTERN = re.compile(rb'\{"client_llm_agent":.*?"sei_index":\d+\}', re.S)


def parser_playlist_text(text):
    """Accept the observed integral decimal target duration without changing
    any segment URI or EXTINF timing. Preserve the original playlist on disk.
    Nonintegral target durations still fail in the standards-based parser.
    """
    return re.sub(r'(?m)^(#EXT-X-TARGETDURATION:)(\d+)\.0+(?=\r?$)', r'\1\2', text)


def subtitles(blob):
    streams = defaultdict(bytearray)
    for offset in range(0, len(blob) - 187, 188):
        packet = blob[offset:offset + 188]
        if packet[0] != 0x47:
            raise ValueError("TS synchronization failed")
        control = (packet[3] >> 4) & 3
        if control not in (1, 3):
            continue
        pid = ((packet[1] & 31) << 8) | packet[2]
        start = 4 if control == 1 else 5 + packet[4]
        if start < 188:
            streams[pid].extend(packet[start:])
    records = []
    for payload in streams.values():
        for match in PATTERN.finditer(payload):
            try:
                value = json.loads(match.group())
                text = value['client_llm_agent'].get('asr_text', '')
                if text:
                    records.append({'sei_index': value['sei_index'], 'text': text})
            except (ValueError, KeyError):
                continue
    return records


def collect(room, workers=8, audio_bitrate=16):
    import httpx
    import m3u8
    import soundfile as sf

    room_id = room['roomId']
    label = datetime.fromtimestamp(room['start'], TZ).strftime('%m%d-%H%M')
    folder = ROOT / 'data' / label
    folder.mkdir(parents=True, exist_ok=True)
    done_path = folder / 'complete.json'
    if done_path.exists():
        return json.loads(done_path.read_text())
    playlist_path = folder / 'source.m3u8'
    client = httpx.Client(timeout=httpx.Timeout(20, read=15), follow_redirects=True,
                         limits=httpx.Limits(max_connections=workers + 2))
    response = client.get(room['replayUrl'])
    response.raise_for_status()
    playlist_path.write_text(response.text)
    parsed_text = parser_playlist_text(response.text)
    playlist = m3u8.loads(parsed_text, uri=room['replayUrl'])
    # Keep a parser-compatible copy for downstream tools, plus exact raw evidence.
    if parsed_text != response.text:
        (folder / 'source-original.m3u8').write_text(response.text)
        playlist_path.write_text(parsed_text)
        (folder / 'playlist-normalization.json').write_text(json.dumps({
            'change': 'Integral decimal EXT-X-TARGETDURATION normalized to integer',
            'original': 'source-original.m3u8', 'parser_copy': 'source.m3u8',
            'segment_durations_and_uris_unchanged': True
        }, indent=2))
    if playlist.is_variant or not playlist.is_endlist:
        raise ValueError('Expected a complete VOD media playlist')
    if any(k and k.method != 'NONE' for k in playlist.keys):
        raise ValueError('Encrypted HLS: use a compatible HLS demuxer')
    if any(s.byterange or s.init_section for s in playlist.segments):
        raise ValueError('Byte ranges/init segments need an HLS demuxer')
    metadata = []
    elapsed = 0.0
    for i, segment in enumerate(playlist.segments):
        metadata.append({'index': i, 'offset': elapsed,
                         'duration': float(segment.duration),
                         'program_time': segment.program_date_time.isoformat()
                         if segment.program_date_time else None})
        elapsed += float(segment.duration)
    (folder / 'segments.json').write_text(json.dumps(metadata, ensure_ascii=False))
    audio_path = ROOT / 'audio' / f'{label}.mp3'
    log = (ROOT / 'logs' / f'{label}-ffmpeg.log').open('w')
    proc = subprocess.Popen([
        'ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y',
        '-i', 'pipe:0', '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000',
        '-c:a', 'libmp3lame', '-b:a', f'{audio_bitrate}k', '-threads', '1',
        str(audio_path)], stdin=subprocess.PIPE, stderr=log, stdout=subprocess.DEVNULL)
    total_bytes = 0
    subtitle_count = 0
    subtitle_segments = 0
    began = time.time()

    def download(index):
        last = None
        for attempt in range(4):
            try:
                began_segment = time.monotonic()
                chunks = []
                with client.stream('GET', playlist.segments[index].absolute_uri) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes(65536):
                        if time.monotonic() - began_segment > 90:
                            raise TimeoutError('Segment exceeded 90 second transfer budget')
                        chunks.append(chunk)
                blob = b''.join(chunks)
                if not blob or len(blob) % 188:
                    raise ValueError('Incomplete or non-TS segment')
                return index, blob, subtitles(blob)
            except Exception as exc:
                last = exc
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f'Segment {index} failed: {type(last).__name__}')

    try:
        with (folder / 'subtitle_snapshots.jsonl').open('w') as out, cf.ThreadPoolExecutor(max_workers=workers) as pool:
            for first in range(0, len(metadata), 64):
                batch = range(first, min(first + 64, len(metadata)))
                for index, blob, records in pool.map(download, batch):
                    proc.stdin.write(blob)
                    total_bytes += len(blob)
                    if records:
                        subtitle_segments += 1
                    for record in records:
                        record.update(metadata[index])
                        out.write(json.dumps(record, ensure_ascii=False) + '\n')
                        subtitle_count += 1
                out.flush()
                progress = {'roomId': room_id, 'label': label,
                            'segments_done': min(first + 64, len(metadata)),
                            'segments_total': len(metadata), 'bytes': total_bytes,
                            'subtitle_snapshots': subtitle_count,
                            'elapsed_seconds': round(time.time() - began, 1)}
                (folder / 'progress.json').write_text(json.dumps(progress))
                if first % 512 == 0:
                    print(json.dumps(progress), flush=True)
        proc.stdin.close()
        code = proc.wait()
        if code:
            raise RuntimeError(f'ffmpeg exited {code}')
        probe = subprocess.run(['ffprobe', '-v', 'error',
                                '-show_entries', 'format=duration', '-of', 'json',
                                str(audio_path)], capture_output=True, text=True, check=True)
        container_duration = float(json.loads(probe.stdout)['format']['duration'])
        info = sf.info(audio_path)
        actual_duration = info.duration
        if info.samplerate != 16000 or info.channels != 1:
            raise ValueError('MP3 analysis format mismatch')
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-i', str(audio_path),
                        '-f', 'null', '-'], check=True)
        summary = {'roomId': room_id, 'label': label, 'playlist_duration': elapsed,
                   'audio_duration': actual_duration,
                   'duration_difference': actual_duration - elapsed,
                   'segments_total': len(metadata), 'segments_downloaded': len(metadata),
                   'subtitle_segments': subtitle_segments, 'subtitle_snapshots': subtitle_count,
                   'bytes_downloaded': total_bytes, 'audio': str(audio_path),
                   'analysis_audio': str(audio_path), 'container_duration': container_duration,
                   'mp3_archive': {'verified': True, 'status': 'mp3_only',
                                   'format': f'MP3 {audio_bitrate} kbps mono 16 kHz',
                                   'bitrate_kbps': audio_bitrate,
                                   'decoded_seconds': actual_duration,
                                   'mp3_bytes': audio_path.stat().st_size,
                                   'sha256': hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                                   'source_files': [], 'deleted_files': [], 'removed_bytes': 0,
                                   'net_saved_bytes': 0,
                                   'note': 'Encoded directly from complete HLS stream; no persistent WAV/M4A copy'}}
        done_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print('COMPLETE ' + json.dumps(summary), flush=True)
        return summary
    except Exception:
        proc.kill()
        proc.wait()
        raise
    finally:
        client.close()
        log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--session-workers', type=int, default=2)
    parser.add_argument('--download-workers', type=int, default=8)
    parser.add_argument('--audio-bitrate', type=int, choices=(16, 24, 32, 40, 48, 64), default=16,
                        help='MP3 kbps (default: 16, listening-approved); preserve full duration and pauses')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    ROOT=args.root.resolve()
    for sub in ['data','audio','logs']: (ROOT/sub).mkdir(parents=True,exist_ok=True)
    rooms = json.loads(args.manifest.read_text())
    if args.limit:
        rooms = rooms[:args.limit]
    with cf.ThreadPoolExecutor(max_workers=args.session_workers) as pool:
        futures = [pool.submit(collect, room, args.download_workers, args.audio_bitrate) for room in rooms]
        for future in cf.as_completed(futures):
            future.result()

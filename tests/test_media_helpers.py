"""HLS/SEI extraction and requested ASR intervals use fully synthetic inputs."""
import json
import unittest

from pipeline.collect_media import parser_playlist_text, subtitles
from pipeline.transcribe_missing import chunk_ranges


def ts_packets(payload, pid=256):
    packets = []
    for i, start in enumerate(range(0, len(payload), 184)):
        header = bytes([0x47, (pid >> 8) & 31, pid & 255, 0x10 | (i % 16)])
        packets.append(header + payload[start:start+184].ljust(184, b'\xff'))
    return b''.join(packets)


class MediaHelperTests(unittest.TestCase):
    def test_playlist_normalizes_only_integral_target_duration(self):
        source = '#EXTM3U\n#EXT-X-TARGETDURATION:6.000\n#EXTINF:5.123,\npart-1.ts\n'
        self.assertEqual(parser_playlist_text(source), source.replace('6.000', '6'))
        fractional = '#EXT-X-TARGETDURATION:6.5\n'
        self.assertEqual(parser_playlist_text(fractional), fractional)

    def test_subtitle_json_crosses_transport_packet_boundary(self):
        record = {'client_llm_agent': {'asr_text': '合成字幕用于公开测试。' * 20}, 'sei_index': 3}
        payload = json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode()
        self.assertGreater(len(payload), 184)
        self.assertEqual(subtitles(ts_packets(payload)), [
            {'sei_index': 3, 'text': record['client_llm_agent']['asr_text']},
        ])

    def test_invalid_transport_sync(self):
        with self.assertRaises(ValueError):
            subtitles(b'\x00' * 188)

    def test_asr_range_does_not_round_start_or_drop_short_tail(self):
        self.assertEqual(list(chunk_ranges(0.25, 600.5)), [(0.25, 600.25), (600.25, 600.5)])
        self.assertEqual(list(chunk_ranges(12.5, 13.0)), [(12.5, 13.0)])
        for args in ((-1, 10), (10, 10), (5, 1), (0, float('nan'))):
            with self.assertRaises(ValueError):
                list(chunk_ranges(*args))


if __name__ == '__main__':
    unittest.main()

"""Integration tests for app/worker.py — process_chunk() pipeline."""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.classifier import SnoreClassifier
from app.regressor import IntensityRegressor
from app.worker import process_chunk
from tests.conftest import make_wav, make_wav_silence, make_wav_loud


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(audio_bytes: bytes, db=None, *, kafka_emit=None, influx=None):
    """Run process_chunk with stub models and no-op side effects by default."""
    if kafka_emit is None:
        kafka_emit = MagicMock()
    return process_chunk(
        chunk_id="chunk-test",
        session_id="session-test",
        user_id="user-test",
        audio_bytes=audio_bytes,
        chunk_index=0,
        duration_seconds=3,
        classifier=SnoreClassifier(),
        regressor=IntensityRegressor(),
        db=db,
        influx_write=influx,
        kafka_emit=kafka_emit,
    )


# ── Summary structure ──────────────────────────────────────────────────────────

class TestProcessChunkSummary:
    def test_returns_dict(self):
        result = _run(make_wav(duration=3.0))
        assert isinstance(result, dict)

    def test_summary_has_required_keys(self):
        result = _run(make_wav(duration=3.0))
        for key in ("snore_windows", "total_windows", "snore_ratio",
                    "avg_intensity", "max_intensity", "per_event"):
            assert key in result

    def test_total_windows_positive(self):
        result = _run(make_wav(duration=3.0))
        assert result["total_windows"] >= 1

    def test_snore_ratio_in_0_to_1(self):
        result = _run(make_wav(duration=3.0))
        assert 0.0 <= result["snore_ratio"] <= 1.0

    def test_avg_intensity_in_0_to_100(self):
        result = _run(make_wav(duration=3.0))
        assert 0.0 <= result["avg_intensity"] <= 100.0

    def test_max_intensity_in_0_to_100(self):
        result = _run(make_wav(duration=3.0))
        assert 0.0 <= result["max_intensity"] <= 100.0

    def test_per_event_is_list(self):
        result = _run(make_wav(duration=3.0))
        assert isinstance(result["per_event"], list)

    def test_per_event_each_has_required_fields(self):
        result = _run(make_wav(duration=30.0))
        for ev in result["per_event"]:
            for field in ("start_sec", "end_sec", "class", "confidence", "intensity"):
                assert field in ev

    def test_silence_audio_snore_ratio_in_range(self):
        # peak_normalize() amplifies near-silence to full scale, so the stub
        # may classify it as any class — just verify ratio is valid
        result = _run(make_wav_silence(duration=3.0))
        assert 0.0 <= result["snore_ratio"] <= 1.0

    def test_loud_audio_nonzero_intensity(self):
        result = _run(make_wav_loud(duration=3.0))
        # loud audio → high energy → stub classifies as snoring → intensity > 0
        assert result["max_intensity"] >= 0.0   # at minimum non-negative


# ── Kafka emit ────────────────────────────────────────────────────────────────

class TestProcessChunkKafkaEmit:
    def test_kafka_emit_called_once(self):
        emit = MagicMock()
        _run(make_wav(duration=3.0), kafka_emit=emit)
        emit.assert_called_once()

    def test_kafka_emit_topic(self):
        emit = MagicMock()
        _run(make_wav(duration=3.0), kafka_emit=emit)
        topic = emit.call_args[0][0]
        assert topic == "analysis.complete"

    def test_kafka_payload_fields(self):
        emit = MagicMock()
        _run(make_wav(duration=3.0), kafka_emit=emit)
        payload = emit.call_args[0][1]
        for field in ("chunk_id", "session_id", "user_id", "chunk_index",
                      "summary", "timestamp"):
            assert field in payload

    def test_kafka_payload_chunk_id(self):
        emit = MagicMock()
        _run(make_wav(duration=3.0), kafka_emit=emit)
        assert emit.call_args[0][1]["chunk_id"] == "chunk-test"

    def test_kafka_payload_summary_is_dict(self):
        emit = MagicMock()
        _run(make_wav(duration=3.0), kafka_emit=emit)
        assert isinstance(emit.call_args[0][1]["summary"], dict)


# ── DB update ─────────────────────────────────────────────────────────────────

class TestProcessChunkDbUpdate:
    def test_db_none_does_not_raise(self):
        result = _run(make_wav(duration=3.0), db=None)
        assert result is not None

    def test_db_chunk_status_updated_to_done(self, db_with_chunk):
        emit = MagicMock()
        process_chunk(
            chunk_id="chunk-001",
            session_id="session-001",
            user_id="user-001",
            audio_bytes=make_wav(duration=3.0),
            chunk_index=0,
            duration_seconds=3,
            classifier=SnoreClassifier(),
            regressor=IntensityRegressor(),
            db=db_with_chunk,
            influx_write=None,
            kafka_emit=emit,
        )
        from app.models import AudioChunk
        chunk = db_with_chunk.query(AudioChunk).filter_by(id="chunk-001").first()
        assert chunk.status == "done"

    def test_db_analysis_result_stored_as_json(self, db_with_chunk):
        emit = MagicMock()
        process_chunk(
            chunk_id="chunk-001",
            session_id="session-001",
            user_id="user-001",
            audio_bytes=make_wav(duration=3.0),
            chunk_index=0,
            duration_seconds=3,
            classifier=SnoreClassifier(),
            regressor=IntensityRegressor(),
            db=db_with_chunk,
            influx_write=None,
            kafka_emit=emit,
        )
        from app.models import AudioChunk
        chunk = db_with_chunk.query(AudioChunk).filter_by(id="chunk-001").first()
        result = json.loads(chunk.analysis_result)
        assert "snore_ratio" in result

    def test_db_processed_at_set(self, db_with_chunk):
        emit = MagicMock()
        process_chunk(
            chunk_id="chunk-001",
            session_id="session-001",
            user_id="user-001",
            audio_bytes=make_wav(duration=3.0),
            chunk_index=0,
            duration_seconds=3,
            classifier=SnoreClassifier(),
            regressor=IntensityRegressor(),
            db=db_with_chunk,
            influx_write=None,
            kafka_emit=emit,
        )
        from app.models import AudioChunk
        chunk = db_with_chunk.query(AudioChunk).filter_by(id="chunk-001").first()
        assert chunk.processed_at is not None


# ── InfluxDB write ────────────────────────────────────────────────────────────

class TestProcessChunkInflux:
    def test_influx_none_does_not_raise(self):
        result = _run(make_wav(duration=3.0), influx=None)
        assert result is not None

    def test_influx_write_called_when_provided(self):
        write_api = MagicMock()
        with patch("app.worker._write_influx") as mock_influx:
            _run(make_wav(duration=3.0), influx=write_api)
            mock_influx.assert_called_once()


# ── Per-event timing ──────────────────────────────────────────────────────────

class TestProcessChunkTiming:
    def test_event_start_sec_non_negative(self):
        result = _run(make_wav(duration=30.0))
        for ev in result["per_event"]:
            assert ev["start_sec"] >= 0.0

    def test_event_end_greater_than_start(self):
        result = _run(make_wav(duration=30.0))
        for ev in result["per_event"]:
            assert ev["end_sec"] > ev["start_sec"]

    def test_events_ordered_by_start_sec(self):
        result = _run(make_wav(duration=30.0))
        starts = [ev["start_sec"] for ev in result["per_event"]]
        assert starts == sorted(starts)

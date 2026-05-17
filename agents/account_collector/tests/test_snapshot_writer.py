from pathlib import Path

from account_collector.snapshot_writer import read_snapshot, write_snapshot


def test_write_snapshot_roundtrip(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures" / "manual_sample.json"
    snapshot = read_snapshot(fixture)
    output = tmp_path / "snapshots" / "latest.json"

    write_snapshot(snapshot, output)
    reloaded = read_snapshot(output)

    assert output.exists()
    assert reloaded.to_dict() == snapshot.to_dict()

"""Read version/mode provenance from the existing parser's header, not filenames."""
from pathlib import Path

PROVENANCE_VERSION = 2


def read_provenance(path: Path) -> dict:
    from mgz.fast.header import parse
    from mgz.reference import get_dataset
    with path.open('rb') as handle:
        header = parse(handle)
    de = header.get('de') or {}
    dataset_id, _ = get_dataset(header['version'], header.get('mod'))
    metadata_cheats = header.get('metadata', {}).get('cheats')
    de_cheats = de.get('cheats')
    cheats = (True if metadata_cheats is True or de_cheats is True else
              False if metadata_cheats is False and de_cheats is False else None)
    return {
        'provenance_version': PROVENANCE_VERSION, 'source': 'mgz parsed replay header',
        'edition': str(header['version']).split('.')[-1],
        'build_version': de.get('build'), 'game_version': header.get('game_version'),
        'save_version': header.get('save_version'), 'log_version': header.get('log_version'),
        'dataset_id': dataset_id, 'game_type_id': header.get('lobby', {}).get('game_type_id'),
        'reported_mod': de.get('mod') or None, 'rms_mod_id': de.get('rms_mod_id'),
        'all_technologies': de.get('all_technologies'), 'cheats': cheats,
        'metadata_cheats': metadata_cheats, 'de_cheats': de_cheats,
        'mod_compatibility': 'unknown',
        'compatibility_note': 'Build is a knowledge lookup key, not proof of compatible mods/mode. Empty mod metadata does not verify unmodified rules.',
    }

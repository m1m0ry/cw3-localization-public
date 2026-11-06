"""One desktop mutator, including unfinished temporary experiments."""
from contextlib import contextmanager
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def desktop_lock(experiment=None):
    # flock is released on client death. The experiment claim survives, so a
    # subsequent install cannot silently take over files still awaiting recovery.
    import fcntl
    path = ROOT / 'local-only/evidence/dev-install.lock'
    claim = path.with_suffix('.experiment.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another maintenance session is controlling the install; use status')
        try:
            if claim.is_symlink():raise RuntimeError('Experiment ownership record is linked')
            if claim.exists():
                owner = json.loads(claim.read_text())
                if str(experiment) != owner['journal']:
                    raise RuntimeError('Recover the unfinished experiment first: ' + owner['journal'])
            yield claim
        finally:fcntl.flock(handle, fcntl.LOCK_UN)

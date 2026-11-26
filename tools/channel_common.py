"""Release channel layout shared by the repository tools. Pure functions, no I/O."""

CHANNELS = ('stable', 'testing')


def check_channel(channel):
    if channel not in CHANNELS:
        raise ValueError('Unknown channel: %r (use stable or testing)' % (channel,))
    return channel


def repo_name(channel):
    """Pacman repository name; stable keeps the historic name."""
    return 'windoesnot' if check_channel(channel) == 'stable' else 'windoesnot-testing'


def db_names(channel):
    """Database file names (aliases and signatures included), stable names unchanged."""
    base = repo_name(channel)
    names = []
    for kind in ('files', 'db'):
        names += [f'{base}.{kind}.tar.gz', f'{base}.{kind}.tar.gz.sig', f'{base}.{kind}', f'{base}.{kind}.sig']
    return names


def remote_dir(channel):
    """Object-key directory of the repository inside the bucket."""
    return 'repo/x86_64' if check_channel(channel) == 'stable' else 'repo/testing/x86_64'


def default_server(channel):
    return 'https://download.windoesnot.me/' + remote_dir(channel)


def changelog_blocker(entry, current, channel):
    """Return None when the newest changelog entry may be published to the channel, else a reason."""
    check_channel(channel)
    if entry.get('version') != current:
        return f'newest changelog entry {entry.get("version")} does not match {current}'
    if entry.get('unreleased') and channel != 'testing':
        return f'changelog entry {current} is unreleased; it may only go to the testing channel'
    return None

# External Docs Update Drafts

This file contains ready-to-paste updates for external docs that currently reference outdated Amulet Map Editor installation steps.

## amuletmc.com "Install From Source"
Replace the current source install steps with:

1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Clone or download the Amulet-Map-Editor source.
4. Install with pinned constraints:
   `python -m pip install -e . -c constraints.txt`
5. Run the editor:
   `python -m amulet_map_editor`
6. Optional: run tests:
   `python -m unittest discover -v -s tests`
7. Optional: build a wheel:
   `python -m build`

## ReadTheDocs "Getting Started / Installing Amulet Map Editor"
Replace the "install from source" reference with the same steps above, and mention:

- Windows compiled builds are available as a zip; extract and run `amulet_app.exe`.
- Source install uses `constraints.txt` for reproducible installs.

## GitHub README (external)
Ensure the "Running from Source" section matches:

1. Python 3.10+
2. `python -m pip install -e . -c constraints.txt`
3. `python -m amulet_map_editor`
4. `python -m unittest discover -v -s tests`

## PyPI Description
PyPI pulls from README at release time. After the next release, the updated README will reflect:

- Python 3.10+ requirement
- `constraints.txt` usage
- local dev/test/build steps

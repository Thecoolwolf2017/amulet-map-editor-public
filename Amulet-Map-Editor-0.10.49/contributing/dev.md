## Developer Contributing

This is intended for developers wishing to contribute code to the project.

### Branch Naming
A branch must be created in order to contribute code to the project.
Unless you have permissions to create branches in Amulet-Team you will first need to [fork the repository](https://docs.github.com/en/github/getting-started-with-github/fork-a-repo).
You must then create a branch with an identifiable name using the following convention:

* For features, use: `impl-<feature name>`
* For bug fixes, use: `bug-<bug tracker ID>`
* For improvements/rewrites, use: `improv-<feature name>`
* For prototyping, use: `proto-<feature name>`

### Tests
There are a number of tests to make sure that the code behaves correctly.
If you are making changes to the code these should be run before creating the pull request.

### Dependency Constraints
For reproducible installs/builds, use the pinned versions in `constraints.txt`.

Install with:
`python -m pip install -e . -c constraints.txt`

### Code Formatting
For code formatting, we use the formatting utility [black](https://github.com/ambv/black).
To run it on a file, run the following command from your favorite terminal after installing: `black <path to file>`

While formatting is not strictly required for each commit, we ask that after you've finished your
code changes for your Pull Request to run it on every changed file.

The following command will run it on all files. `black .`

### Pull Requests
Once you have added the desired changes and run tests and formatting you will need to [create a pull request](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request). 
We ask that submitted Pull Requests give moderately detailed notes about the changes and explain 
any changes that were made to the program outside of those directly related to the feature/bug-fix.

Once a Pull Request is submitted, we will mark the request for review.
Once that is done, we will review the changes and may provide feedback on things to change.
Once all additional changes have been made, we will merge the request.

The tests and code formatting will be run automatically when the pull request is created to verify that everything is okay.
This can be seen at the bottom of the pull request page.

### Plugin Entry Points
Edit tools and operations can be provided via Python entry points so new functionality can be added without modifying core code.

Supported entry point groups:
* `amulet_map_editor.edit_tools` -> tool classes (subclass of `BaseToolUI`).
* `amulet_map_editor.edit_operations.<group>` -> operation export dicts/modules for a group (eg. `operations`, `export_operations`).

Entry point objects should either:
* return a module with an `export` dict/list, or
* return the `export` dict/list directly.

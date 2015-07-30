## Kipper DEV Branch v1.1.0

This development version is functionally identical to the master branch, but has a revised sequence storage mechanism that makes use of the diff_match_patch library/module: https://code.google.com/p/google-diff-match-patch/wiki/API .  The objective is to reduce the size of the resulting archive in the face of many minor changes to key values.

Where Kipper v1.0.0 would store version changes in multiple text file rows, the new version 1.1.0 has exactly one text line for each key, and the version values are encoded in a (json) array containing for each version, a set of instructions for generating the value from the previous version's value, according to text deletion, inserts, and/or key removal.

Also note that for speed, a natural sort is no longer employed.  Keys are sorted the default way, alphabetically, and case sensitive.

We are testing this version and will release when we are confident of its behavour.

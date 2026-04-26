from core import parse_hunks


def test_single_hunk_diff():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -1,3 +1,3 @@
 line one
-old middle
+new middle
 line three
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.file == "SKILL.md"
    assert h.old_string == "line one\nold middle\nline three\n"
    assert h.new_string == "line one\nnew middle\nline three\n"


def test_multi_hunk_same_file():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -1,3 +1,3 @@
 alpha
-beta
+BETA
 gamma
@@ -10,3 +10,3 @@
 delta
-epsilon
+EPSILON
 zeta
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 2
    assert all(h.file == "SKILL.md" for h in hunks)
    assert hunks[0].old_string == "alpha\nbeta\ngamma\n"
    assert hunks[0].new_string == "alpha\nBETA\ngamma\n"
    assert hunks[1].old_string == "delta\nepsilon\nzeta\n"
    assert hunks[1].new_string == "delta\nEPSILON\nzeta\n"


def test_multi_file_diff():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -1,3 +1,3 @@
 a
-old
+new
 b
--- a/helper.py
+++ b/helper.py
@@ -1,3 +1,3 @@
 import os
-x = 1
+x = 2
 y = 3
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 2
    assert hunks[0].file == "SKILL.md"
    assert hunks[1].file == "helper.py"


def test_hunk_at_top_of_file():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -1,2 +1,2 @@
-old first line
+new first line
 second line
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 1
    assert hunks[0].old_string == "old first line\nsecond line\n"
    assert hunks[0].new_string == "new first line\nsecond line\n"


def test_hunk_at_bottom_of_file():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -2,2 +2,2 @@
 second to last
-old last line
+new last line
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 1
    assert hunks[0].old_string == "second to last\nold last line\n"
    assert hunks[0].new_string == "second to last\nnew last line\n"


def test_no_trailing_newline_marker():
    diff = """\
--- a/SKILL.md
+++ b/SKILL.md
@@ -1,2 +1,2 @@
 keep
-old
\\ No newline at end of file
+new
\\ No newline at end of file
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 1
    assert hunks[0].old_string == "keep\nold"
    assert hunks[0].new_string == "keep\nnew"
